"""Storage service exceptions."""


class StorageException(Exception):
    """Base exception for storage operations."""

    pass


class StorageUploadError(StorageException):
    """Exception raised when file upload fails."""

    pass


class StorageDownloadError(StorageException):
    """Exception raised when file download fails."""

    pass


class StorageDeleteError(StorageException):
    """Exception raised when file deletion fails."""

    pass


class StorageURLError(StorageException):
    """Exception raised when generating signed URL fails."""

    pass
