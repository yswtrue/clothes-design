"""S3-compatible storage implementation."""

import asyncio
import os
from typing import Any

import boto3
from botocore.exceptions import ClientError

from storage.base import StorageService
from storage.exceptions import (
    StorageDeleteError,
    StorageDownloadError,
    StorageUploadError,
    StorageURLError,
)


class S3Storage(StorageService):
    """Storage implementation using S3 or S3-compatible storage."""

    def __init__(
        self,
        bucket_name: str | None = None,
        endpoint_url: str | None = None,
        region_name: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
    ):
        """Initialize S3 storage.

        Args:
            bucket_name: S3 bucket name. Defaults to AWS_S3_BUCKET env var
            endpoint_url: S3 endpoint URL (for MinIO/LocalStack). Defaults to AWS_S3_ENDPOINT env var
            region_name: AWS region. Defaults to AWS_REGION env var
            access_key: AWS access key. Defaults to AWS_ACCESS_KEY_ID env var
            secret_key: AWS secret key. Defaults to AWS_SECRET_ACCESS_KEY env var
        """
        self.bucket_name = bucket_name or os.getenv("AWS_S3_BUCKET", "clothes-design-dev")
        self.endpoint_url = endpoint_url or os.getenv("AWS_S3_ENDPOINT")
        self.region_name = region_name or os.getenv("AWS_REGION", "us-east-1")
        self.access_key = access_key or os.getenv("AWS_ACCESS_KEY_ID", "minioadmin")
        self.secret_key = secret_key or os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin")

        # Determine if using path-style URLs (for MinIO/LocalStack)
        use_path_style = os.getenv("AWS_S3_USE_PATH_STYLE", "true").lower() == "true"

        self._client: Any = None
        self._client_config = {
            "service_name": "s3",
            "region_name": self.region_name,
            "aws_access_key_id": self.access_key,
            "aws_secret_access_key": self.secret_key,
            "use_ssl": self.endpoint_url and self.endpoint_url.startswith("https"),
        }
        if self.endpoint_url:
            self._client_config["endpoint_url"] = self.endpoint_url
        if use_path_style:
            self._client_config["config"] = boto3.session.Config(s3={"addressing_style": "path"})

    def _get_client(self) -> Any:
        """Get or create S3 client."""
        if self._client is None:
            self._client = boto3.client(**self._client_config)  # type: ignore
        return self._client

    async def upload(self, file: bytes, key: str) -> str:
        """Upload file to S3.

        Args:
            file: File bytes to upload
            key: S3 object key

        Returns:
            S3 URL to the uploaded file

        Raises:
            StorageUploadError: If upload fails
        """
        try:
            loop = asyncio.get_event_loop()
            client = self._get_client()
            await loop.run_in_executor(
                None,
                lambda: client.put_object(Bucket=self.bucket_name, Key=key, Body=file),
            )
            # Return URL in format: s3://bucket/key or https://endpoint/bucket/key
            if self.endpoint_url:
                return f"{self.endpoint_url}/{self.bucket_name}/{key}"
            return f"s3://{self.bucket_name}/{key}"
        except ClientError as e:
            raise StorageUploadError(f"Failed to upload file {key}: {e}") from e
        except Exception as e:
            raise StorageUploadError(f"Failed to upload file {key}: {e}") from e

    async def download(self, key: str) -> bytes:
        """Download file from S3.

        Args:
            key: S3 object key

        Returns:
            File bytes

        Raises:
            StorageDownloadError: If download fails
        """
        try:
            loop = asyncio.get_event_loop()
            client = self._get_client()

            def _download() -> bytes:
                response = client.get_object(Bucket=self.bucket_name, Key=key)
                return response["Body"].read()

            data = await loop.run_in_executor(None, _download)
            return data
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                raise StorageDownloadError(f"File not found: {key}") from e
            raise StorageDownloadError(f"Failed to download file {key}: {e}") from e
        except Exception as e:
            raise StorageDownloadError(f"Failed to download file {key}: {e}") from e

    async def delete(self, key: str) -> bool:
        """Delete file from S3.

        Args:
            key: S3 object key

        Returns:
            True if successful, False otherwise

        Raises:
            StorageDeleteError: If deletion fails
        """
        try:
            loop = asyncio.get_event_loop()
            client = self._get_client()
            await loop.run_in_executor(
                None,
                lambda: client.delete_object(Bucket=self.bucket_name, Key=key),
            )
            return True
        except ClientError as e:
            raise StorageDeleteError(f"Failed to delete file {key}: {e}") from e
        except Exception as e:
            raise StorageDeleteError(f"Failed to delete file {key}: {e}") from e

    async def get_url(self, key: str, expires: int = 3600) -> str:
        """Get signed URL for S3 object.

        Args:
            key: S3 object key
            expires: URL expiration time in seconds

        Returns:
            Signed S3 URL

        Raises:
            StorageURLError: If URL generation fails
        """
        try:
            loop = asyncio.get_event_loop()
            client = self._get_client()

            def _get_signed_url() -> str:
                url = client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.bucket_name, "Key": key},
                    ExpiresIn=expires,
                )
                return url

            url = await loop.run_in_executor(None, _get_signed_url)
            return url
        except ClientError as e:
            raise StorageURLError(f"Failed to generate URL for {key}: {e}") from e
        except Exception as e:
            raise StorageURLError(f"Failed to generate URL for {key}: {e}") from e
