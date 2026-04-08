from abc import ABC, abstractmethod

from ai.schemas import GenerationParams, Position, StyleAnalysis


class AIProvider(ABC):
    """Abstract base class for AI service providers."""

    @abstractmethod
    async def analyze_style(self, image: bytes) -> StyleAnalysis:
        """Analyze image style using AI vision model.

        Args:
            image: Image bytes to analyze

        Returns:
            StyleAnalysis object containing style information
        """
        pass

    @abstractmethod
    async def generate_pattern(self, style: StyleAnalysis, params: GenerationParams) -> bytes:
        """Generate pattern based on style analysis and parameters.

        Args:
            style: StyleAnalysis object from analyze_style
            params: GenerationParams with dimensions and configuration

        Returns:
            Generated pattern as bytes
        """
        pass

    @abstractmethod
    async def upscale_image(self, image: bytes, target_size: int) -> bytes:
        """Upscale image to target size using super-resolution.

        Args:
            image: Image bytes to upscale
            target_size: Target width/height in pixels

        Returns:
            Upscaled image as bytes
        """
        pass

    @abstractmethod
    async def vectorize(self, image: bytes, color_space: str = "rgb") -> bytes:
        """Convert raster image to vector format.

        Args:
            image: Raster image bytes
            color_space: Color space for vectorization (rgb|cmyk|lab)

        Returns:
            Vectorized image as bytes (SVG format)
        """
        pass

    @abstractmethod
    async def composite_mockup(self, pattern: bytes, template: bytes, position: Position) -> bytes:
        """Composite pattern onto template mockup.

        Args:
            pattern: Pattern image bytes
            template: Template/mockup image bytes
            position: Position and transformation parameters

        Returns:
            Composited mockup as bytes
        """
        pass
