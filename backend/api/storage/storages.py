import os
from pathlib import Path

from fastapi_storages import FileSystemStorage, S3Storage
from fastapi_storages.utils import secure_filename

from config import get_settings


class PrefixedS3Storage(S3Storage):
    prefix: str = ""

    def __init__(self, prefix: str = ""):
        settings = get_settings().storage
        self.AWS_ACCESS_KEY_ID = settings.aws_access_key_id
        self.AWS_SECRET_ACCESS_KEY = settings.aws_secret_access_key
        self.AWS_S3_BUCKET_NAME = settings.aws_s3_bucket
        self.AWS_S3_ENDPOINT_URL = settings.aws_s3_endpoint_url
        self.AWS_S3_USE_SSL = settings.aws_s3_use_ssl
        self.AWS_DEFAULT_ACL = settings.aws_default_acl
        self.AWS_QUERYSTRING_AUTH = settings.aws_querystring_auth
        self.prefix = prefix
        super().__init__()

    def get_name(self, name: str) -> str:
        filename = secure_filename(Path(name).name)
        if self.prefix:
            return f"{self.prefix}/{filename}"
        return filename


def _create_storage(prefix: str):
    settings = get_settings().storage

    if settings.storage_type == "s3":
        return PrefixedS3Storage(prefix=prefix)

    return FileSystemStorage(path=os.path.join(settings.local_storage_path, prefix))


prj_storage = _create_storage("prj_templates")
preview_storage = _create_storage("prj_previews")
material_storage = _create_storage("materials")
generated_image_storage = _create_storage("generated")
thumbnail_storage = _create_storage("thumbnails")
output_tif_storage = _create_storage("outputs")
