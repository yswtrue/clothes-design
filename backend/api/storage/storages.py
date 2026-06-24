import io
import mimetypes
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import BinaryIO, Protocol, TypedDict, cast

import boto3
from botocore.config import Config
from botocore.exceptions import (
    ClientError,
    ConnectionClosedError,
    EndpointConnectionError,
    ReadTimeoutError,
    SSLError,
)
from fastapi_storages import FileSystemStorage, S3Storage
from fastapi_storages.utils import secure_filename

from config import get_settings


def _without_url_scheme(url: str) -> str:
    return url.removeprefix("https://").removeprefix("http://").rstrip("/")


class LocalStorageBackend(Protocol):
    def get_name(self, name: str) -> str: ...

    def open(self, name: str) -> BinaryIO: ...

    def write(self, file: BinaryIO, name: str) -> str: ...

    def get_url(self, name: str) -> str: ...


class S3StorageBackend(Protocol):
    def get_name(self, name: str) -> str: ...

    def get_path(self, name: str) -> str: ...

    def open(self, name: str, mode: str = "rb") -> BinaryIO: ...

    def write(self, file: BinaryIO, name: str) -> str: ...

    def get_url(self, name: str) -> str: ...


class S3Client(Protocol):
    def put_object(
        self,
        Body: bytes,
        Bucket: str,
        Key: str,
        **kwargs: str,
    ) -> None: ...

    def get_object(self, Bucket: str, Key: str) -> "S3GetObjectResponse": ...


class S3ObjectBody(Protocol):
    def read(self) -> bytes: ...

    def close(self) -> None: ...


class S3GetObjectResponse(TypedDict):
    Body: S3ObjectBody


class S3ClientKwargs(TypedDict, total=False):
    endpoint_url: str
    use_ssl: bool
    aws_access_key_id: str
    aws_secret_access_key: str
    region_name: str
    config: Config


class LocalStorageMixin:
    def get_url(self: LocalStorageBackend, name: str) -> str:
        relative_path = self.get_name(name)
        base_url = get_settings().storage.api_base_url.rstrip("/")
        return f"{base_url}/api/files/{relative_path}"

    async def download(self: LocalStorageBackend, name: str) -> bytes:
        filename = Path(name).name
        full_name = self.get_name(filename)
        with self.open(full_name) as f:
            return f.read()

    async def upload(self: LocalStorageBackend, data: bytes | BinaryIO, name: str) -> str:
        if isinstance(data, bytes):
            data = io.BytesIO(data)
        self.write(data, name)
        return self.get_url(name)


class S3StorageMixin:
    def get_url(self: S3StorageBackend, name: str) -> str:
        return self.get_path(name)

    async def download(self: S3StorageBackend, name: str) -> bytes:
        filename = Path(name).name
        full_name = self.get_name(filename)
        with self.open(full_name, "rb") as f:
            return f.read()

    async def upload(self: S3StorageBackend, data: bytes | BinaryIO, name: str) -> str:
        if isinstance(data, bytes):
            data = io.BytesIO(data)
        self.write(data, name)
        return self.get_url(name)


class PrefixedLocalStorage(LocalStorageMixin, FileSystemStorage):
    def __init__(self, path: str, prefix: str = ""):
        self.prefix = prefix
        super().__init__(path=path)

    def get_name(self, name: str) -> str:
        filename = secure_filename(Path(name).name)
        if self.prefix:
            return f"{self.prefix}/{filename}"
        return filename


class PrefixedS3Storage(S3StorageMixin, S3Storage):
    prefix: str = ""
    _s3: S3Client
    _upload_attempts = 3

    def __init__(self, prefix: str = ""):
        settings = get_settings().storage
        self.AWS_ACCESS_KEY_ID = settings.aws_access_key_id
        self.AWS_SECRET_ACCESS_KEY = settings.aws_secret_access_key
        self.AWS_S3_BUCKET_NAME = settings.aws_s3_bucket
        self.AWS_S3_ENDPOINT_URL = _without_url_scheme(settings.aws_s3_endpoint_url)
        self.AWS_S3_CUSTOM_DOMAIN = _without_url_scheme(settings.aws_s3_custom_domain)
        self.AWS_S3_USE_SSL = settings.aws_s3_use_ssl
        self.AWS_DEFAULT_ACL = settings.aws_default_acl if settings.aws_default_acl else None
        self.AWS_QUERYSTRING_AUTH = settings.aws_querystring_auth
        self.prefix = prefix
        self._init_s3_client(region_name=settings.s3_region_name)

    def _init_s3_client(self, region_name: str) -> None:
        assert not self.AWS_S3_ENDPOINT_URL.startswith("http"), "URL should not contain protocol"

        self._http_scheme = "https" if self.AWS_S3_USE_SSL else "http"
        self._url = f"{self._http_scheme}://{self.AWS_S3_ENDPOINT_URL}"
        client_kwargs: S3ClientKwargs = {
            "endpoint_url": self._url,
            "use_ssl": self.AWS_S3_USE_SSL,
            "aws_access_key_id": self.AWS_ACCESS_KEY_ID,
            "aws_secret_access_key": self.AWS_SECRET_ACCESS_KEY,
            "config": Config(
                connect_timeout=10,
                read_timeout=120,
                retries={"max_attempts": 5, "mode": "standard"},
                s3={"addressing_style": "path"},
            ),
        }
        if region_name:
            client_kwargs["region_name"] = region_name
        self._s3 = cast(S3Client, boto3.client("s3", **client_kwargs))

    def get_name(self, name: str) -> str:
        filename = secure_filename(Path(name).name)
        if self.prefix:
            return f"{self.prefix}/{filename}"
        return filename

    def _open_from_custom_domain(self, name: str) -> BinaryIO | None:
        if not self.AWS_S3_CUSTOM_DOMAIN:
            return None

        try:
            with urllib.request.urlopen(self.get_path(name), timeout=30) as response:
                return io.BytesIO(response.read())
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
            return None

    def open(self, name: str, mode: str = "rb") -> BinaryIO:
        if mode not in ("rb", "r"):
            raise ValueError("S3 storage only supports read mode")

        custom_domain_file = self._open_from_custom_domain(name)
        if custom_domain_file is not None:
            return custom_domain_file

        key = self.get_name(name)
        try:
            response = self._s3.get_object(Bucket=self.AWS_S3_BUCKET_NAME, Key=key)
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") != "NoSuchKey":
                raise

            legacy_key = f"{self.AWS_S3_BUCKET_NAME}/{key}"
            if key.startswith(f"{self.AWS_S3_BUCKET_NAME}/"):
                raise
            response = self._s3.get_object(Bucket=self.AWS_S3_BUCKET_NAME, Key=legacy_key)

        body = response["Body"]
        try:
            return io.BytesIO(body.read())
        finally:
            body.close()

    def write(self, file: BinaryIO, name: str) -> str:
        file.seek(0, 0)
        key = self.get_name(name)
        content_type, _ = mimetypes.guess_type(key)
        params = {"ContentType": content_type or self.default_content_type}
        if self.AWS_DEFAULT_ACL:
            params["ACL"] = self.AWS_DEFAULT_ACL

        body = file.read()
        for attempt in range(1, self._upload_attempts + 1):
            try:
                self._s3.put_object(
                    Body=body,
                    Bucket=self.AWS_S3_BUCKET_NAME,
                    Key=key,
                    **params,
                )
                break
            except (ConnectionClosedError, EndpointConnectionError, ReadTimeoutError, SSLError):
                if attempt == self._upload_attempts:
                    raise
                time.sleep(2 ** (attempt - 1))
            except ClientError as e:
                status_code = e.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0)
                if not isinstance(status_code, int) or status_code < 500:
                    raise
                if attempt == self._upload_attempts:
                    raise
                time.sleep(2 ** (attempt - 1))
        return key


def _create_storage(prefix: str):
    settings = get_settings().storage

    if settings.storage_type == "s3":
        return PrefixedS3Storage(prefix=prefix)

    base_path = settings.local_storage_path
    full_path = os.path.join(base_path, prefix)
    os.makedirs(full_path, exist_ok=True)
    return PrefixedLocalStorage(path=base_path, prefix=prefix)


prj_storage = _create_storage("prj_templates")
preview_storage = _create_storage("prj_previews")
material_storage = _create_storage("materials")
generated_image_storage = _create_storage("generated")
thumbnail_storage = _create_storage("thumbnails")
upscaled_storage = _create_storage("upscaled")
vector_storage = _create_storage("vectors")
output_tif_storage = _create_storage("outputs")
template_preview_storage = _create_storage("template_previews")
model_preview_storage = _create_storage("model_previews")
poster_storage = _create_storage("posters")
clo3d_project_storage = _create_storage("clo3d_projects")
clo3d_render_storage = _create_storage("clo3d_renders")
fabric_patch_storage = _create_storage("fabric_patches")
