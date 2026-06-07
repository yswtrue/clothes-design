import io
from typing import Any

import pytest
from botocore.exceptions import SSLError

import api.storage.storages as storages_module
import config
from api.storage.storages import PrefixedS3Storage, S3GetObjectResponse

assert config.get_settings


class RecordingS3Client:
    def __init__(self, failures: int = 0) -> None:
        self.failures = failures
        self.calls: list[dict[str, Any]] = []

    def put_object(self, Body: bytes, Bucket: str, Key: str, **kwargs: str) -> None:
        self.calls.append({"Body": Body, "Bucket": Bucket, "Key": Key, **kwargs})
        if len(self.calls) <= self.failures:
            raise SSLError(endpoint_url="https://r2.example", error="unexpected eof")

    def get_object(self, Bucket: str, Key: str) -> S3GetObjectResponse:
        raise NotImplementedError


def make_storage(client: RecordingS3Client) -> PrefixedS3Storage:
    storage = PrefixedS3Storage.__new__(PrefixedS3Storage)
    storage.prefix = "upscaled"
    storage.AWS_S3_BUCKET_NAME = "cloth"
    storage.AWS_DEFAULT_ACL = None
    storage.default_content_type = "application/octet-stream"
    storage._s3 = client
    return storage


def test_prefixed_s3_write_retries_transient_ssl_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(storages_module.time, "sleep", lambda delay: None)
    client = RecordingS3Client(failures=2)
    storage = make_storage(client)

    key = storage.write(io.BytesIO(b"png-bytes"), "design.png")

    assert key == "upscaled/design.png"
    assert len(client.calls) == 3
    assert client.calls[-1]["Body"] == b"png-bytes"
    assert client.calls[-1]["Bucket"] == "cloth"
    assert client.calls[-1]["Key"] == "upscaled/design.png"
    assert client.calls[-1]["ContentType"] == "image/png"
