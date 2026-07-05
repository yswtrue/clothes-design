from typing import Any, Literal, TypedDict

ExportContentType = Literal["line-art", "pattern"]
ExportFormat = Literal["tif"]

EXPORT_SETTINGS_KEY = "export_settings"


class ExportSettings(TypedDict, total=False):
    format: ExportFormat
    target_resolution: int
    color_space: str
    content_type: ExportContentType
    sharpen: bool
    upscaled_filename: str
    output_filename: str


def normalize_content_type(value: object) -> ExportContentType:
    return "line-art" if value == "line-art" else "pattern"


def normalize_export_settings(
    *,
    export_format: ExportFormat,
    target_resolution: int,
    color_space: str,
    content_type: str,
    sharpen: bool,
    upscaled_filename: str | None = None,
    output_filename: str | None = None,
) -> ExportSettings:
    settings: ExportSettings = {
        "format": export_format,
        "target_resolution": target_resolution,
        "color_space": color_space,
        "content_type": normalize_content_type(content_type),
        "sharpen": bool(sharpen),
    }
    if upscaled_filename:
        settings["upscaled_filename"] = upscaled_filename
    if output_filename:
        settings["output_filename"] = output_filename
    return settings


def get_export_settings(
    generation_params: dict[str, Any] | None,
    export_format: ExportFormat,
) -> ExportSettings | None:
    if not generation_params:
        return None
    export_settings = generation_params.get(EXPORT_SETTINGS_KEY)
    if not isinstance(export_settings, dict):
        return None
    format_settings = export_settings.get(export_format)
    if not isinstance(format_settings, dict):
        return None
    return ExportSettings(**format_settings)


def export_settings_match(
    settings: ExportSettings | None,
    *,
    export_format: ExportFormat,
    target_resolution: int,
    color_space: str,
    content_type: str,
    sharpen: bool,
) -> bool:
    if settings is None:
        return False
    return (
        settings.get("format") == export_format
        and settings.get("target_resolution") == target_resolution
        and settings.get("color_space") == color_space
        and settings.get("content_type") == normalize_content_type(content_type)
        and settings.get("sharpen") == bool(sharpen)
    )


def merge_export_settings(
    generation_params: dict[str, Any] | None,
    settings: ExportSettings,
) -> dict[str, Any]:
    export_format = settings.get("format")
    if export_format is None:
        raise ValueError("Export settings must include a format")

    params = dict(generation_params or {})
    export_settings = params.get(EXPORT_SETTINGS_KEY)
    if not isinstance(export_settings, dict):
        export_settings = {}
    params[EXPORT_SETTINGS_KEY] = {
        **export_settings,
        export_format: dict(settings),
    }
    return params
