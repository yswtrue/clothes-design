from shared.export_settings import (
    export_settings_match,
    get_export_settings,
    merge_export_settings,
    normalize_export_settings,
)


def test_export_settings_match_requires_content_type_and_sharpen() -> None:
    settings = normalize_export_settings(
        export_format="tif",
        target_resolution=12000,
        color_space="CMYK",
        content_type="pattern",
        sharpen=True,
        upscaled_filename="gen_1_upscaled.png",
        output_filename="gen_1_CMYK.tif",
    )

    assert export_settings_match(
        settings,
        export_format="tif",
        target_resolution=12000,
        color_space="CMYK",
        content_type="pattern",
        sharpen=True,
    )
    assert not export_settings_match(
        settings,
        export_format="tif",
        target_resolution=12000,
        color_space="CMYK",
        content_type="line-art",
        sharpen=True,
    )
    assert not export_settings_match(
        settings,
        export_format="tif",
        target_resolution=12000,
        color_space="CMYK",
        content_type="pattern",
        sharpen=False,
    )


def test_merge_export_settings_preserves_existing_generation_params() -> None:
    settings = normalize_export_settings(
        export_format="tif",
        target_resolution=12000,
        color_space="CMYK",
        content_type="line-art",
        sharpen=False,
        upscaled_filename="gen_1_upscaled.png",
        output_filename="gen_1_CMYK.tif",
    )

    merged = merge_export_settings({"strength": 0.7}, settings)

    assert merged["strength"] == 0.7
    assert get_export_settings(merged, "tif") == settings
