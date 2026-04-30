from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class StorageSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    storage_type: Literal["local", "s3"] = Field(default="local", alias="STORAGE_TYPE")
    local_storage_path: str = Field(default="./uploads", alias="LOCAL_STORAGE_PATH")

    aws_access_key_id: str = Field(default="", alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str = Field(default="", alias="AWS_SECRET_ACCESS_KEY")
    aws_s3_bucket: str = Field(default="", alias="AWS_S3_BUCKET")
    aws_s3_endpoint_url: str = Field(default="", alias="AWS_S3_ENDPOINT_URL")
    aws_s3_use_ssl: bool = Field(default=True, alias="AWS_S3_USE_SSL")
    aws_default_acl: str = Field(default="", alias="AWS_DEFAULT_ACL")
    aws_querystring_auth: bool = Field(default=False, alias="AWS_QUERYSTRING_AUTH")


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    url: str = Field(
        default="postgresql://postgres:postgres@127.0.0.1:5432/clothes_design_dev",
        alias="DATABASE_URL",
    )
    pool_size: int = Field(default=5, alias="DB_POOL_SIZE")
    max_overflow: int = Field(default=10, alias="DB_MAX_OVERFLOW")
    pool_recycle: int = Field(default=3600, alias="DB_POOL_RECYCLE")

    @computed_field
    @property
    def async_url(self) -> str:
        if "sqlite" in self.url:
            if "+aiosqlite" in self.url:
                return self.url
            return self.url.replace("sqlite://", "sqlite+aiosqlite://")
        if "+asyncpg" in self.url:
            return self.url
        return self.url.replace("postgresql://", "postgresql+asyncpg://")


class RedisSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    queue_url: str | None = Field(default=None, alias="REDIS_QUEUE_URL")
    max_connections: int = Field(default=10, alias="REDIS_MAX_CONNECTIONS")

    @computed_field
    @property
    def broker_url(self) -> str:
        return self.queue_url or self.url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    storage: StorageSettings = Field(default_factory=StorageSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)


@lru_cache
def get_settings() -> Settings:
    return Settings()
