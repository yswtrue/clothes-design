from pydantic import BaseModel, Field


class StyleAnalysis(BaseModel):
    """Result of AI style analysis on an image."""

    style_description: str = Field(..., description="Natural language description of the style")
    color_palette: list[str] = Field(
        default_factory=list, description="List of hex color codes extracted"
    )
    pattern_type: str = Field(
        ...,
        description="Pattern type: seamless|standalone|full",
        pattern="^(seamless|standalone|full)$",
    )
    suggested_params: dict = Field(
        default_factory=dict,
        description="Suggested generation parameters for this style",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "style_description": "Minimalist geometric with sharp lines",
                "color_palette": ["#FF6B6B", "#4ECDC4", "#FFFFFF"],
                "pattern_type": "seamless",
                "suggested_params": {"tiling": "reflect", "scale": 0.8},
            }
        }


class GenerationParams(BaseModel):
    """Parameters for pattern generation."""

    style: str = Field(..., description="Style name or description")
    tiling: str = Field(
        default="tile",
        description="Tiling mode: tile|clamp|reflect|wrap",
        pattern="^(tile|clamp|reflect|wrap)$",
    )
    width: int = Field(default=512, ge=64, le=2048, description="Pattern width")
    height: int = Field(default=512, ge=64, le=2048, description="Pattern height")
    seed: int = Field(default=42, ge=0, description="Random seed for reproducibility")
    init_image_b64: str | None = Field(default=None, description="Base64 encoded source image for img2img")
    strength: float = Field(default=0.75, ge=0.0, le=1.0, description="img2img strength (0=keep original, 1=ignore original)")

    class Config:
        json_schema_extra = {
            "example": {
                "style": "floral_minimal",
                "tiling": "tile",
                "width": 1024,
                "height": 1024,
                "seed": 42,
            }
        }


class Position(BaseModel):
    """Position and transformation parameters for compositing."""

    x: float = Field(default=0, description="X coordinate on template")
    y: float = Field(default=0, description="Y coordinate on template")
    scale: float = Field(default=1.0, ge=0.1, le=10.0, description="Scale factor")
    rotation: float = Field(default=0, ge=0, le=360, description="Rotation angle in degrees")
    opacity: float = Field(default=1.0, ge=0.0, le=1.0, description="Opacity value 0-1")

    class Config:
        json_schema_extra = {
            "example": {
                "x": 100,
                "y": 150,
                "scale": 1.5,
                "rotation": 0,
                "opacity": 0.9,
            }
        }
