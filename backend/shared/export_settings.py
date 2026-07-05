from typing import Any, Literal, TypedDict

ExportContentType = Literal["line-art", "pattern"]
ExportFormat = Literal["tif"]
ExportUpscaleMode = Literal["progressive", "oneshot"]

EXPORT_SETTINGS_KEY = "export_settings"

DEFAULT_UPSCALE_MODE: ExportUpscaleMode = "progressive"


def normalize_upscale_mode(value: object) -> ExportUpscaleMode:
    return "oneshot" if value == "oneshot" else "progressive"


class ExportSettings(TypedDict, total=False):
    format: ExportFormat
    target_resolution: int
    color_space: str
    content_type: ExportContentType
    sharpen: bool
    upscale_model: str
    upscale_mode: ExportUpscaleMode
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
    upscale_model: str | None = None,
    upscale_mode: ExportUpscaleMode | str | None = None,
    upscaled_filename: str | None = None,
    output_filename: str | None = None,
) -> ExportSettings:
    settings: ExportSettings = {
        "format": export_format,
        "target_resolution": target_resolution,
        "color_space": color_space,
        "content_type": normalize_content_type(content_type),
        "sharpen": bool(sharpen),
        "upscale_mode": normalize_upscale_mode(upscale_mode),
    }
    if upscale_model:
        settings["upscale_model"] = upscale_model
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
    upscale_model: str | None = None,
    upscale_mode: ExportUpscaleMode | str | None = None,
) -> bool:
    if settings is None:
        return False
    mode_match = settings.get("upscale_mode", "progressive") == normalize_upscale_mode(upscale_mode)
    stored_model = settings.get("upscale_model")
    model_match = True
    if stored_model is not None and upscale_model is not None:
        model_match = stored_model == upscale_model
    return (
        settings.get("format") == export_format
        and settings.get("target_resolution") == target_resolution
        and settings.get("color_space") == color_space
        and settings.get("content_type") == normalize_content_type(content_type)
        and settings.get("sharpen") == bool(sharpen)
        and mode_match
        and model_match
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
