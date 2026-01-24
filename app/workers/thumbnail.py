"""Thumbnail generation worker using Stable Diffusion."""

from pathlib import Path
from typing import Optional, List
from loguru import logger

from app.config import settings


class ThumbnailWorker:
    """Worker for generating video thumbnails using SDXL."""

    def __init__(self):
        self.pipe = None
        self.device = settings.tts_device  # Reuse TTS device setting

    def _load_model(self):
        """Lazy load the SDXL model."""
        if self.pipe is None:
            import torch
            from diffusers import StableDiffusionXLPipeline, DPMSolverMultistepScheduler

            logger.info("Loading SDXL model for thumbnail generation...")

            self.pipe = StableDiffusionXLPipeline.from_pretrained(
                "stabilityai/stable-diffusion-xl-base-1.0",
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                variant="fp16" if self.device == "cuda" else None,
                use_safetensors=True,
            )

            # Use faster scheduler
            self.pipe.scheduler = DPMSolverMultistepScheduler.from_config(
                self.pipe.scheduler.config
            )

            if self.device == "cuda":
                self.pipe = self.pipe.to("cuda")
                self.pipe.enable_model_cpu_offload()

            logger.info("SDXL model loaded")

    async def generate(
        self,
        prompt: str,
        output_path: Path,
        negative_prompt: Optional[str] = None,
        width: int = 1280,
        height: int = 720,
        num_inference_steps: int = 25,
        guidance_scale: float = 7.5,
    ) -> Path:
        """
        Generate a thumbnail image.

        Args:
            prompt: Text description for the image
            output_path: Path to save the generated image
            negative_prompt: What to avoid in the image
            width: Image width (default 1280 for YouTube)
            height: Image height (default 720 for YouTube)
            num_inference_steps: Number of diffusion steps
            guidance_scale: How closely to follow the prompt

        Returns:
            Path to generated image
        """
        self._load_model()

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Default negative prompt for better quality
        if negative_prompt is None:
            negative_prompt = (
                "blurry, low quality, distorted, ugly, bad anatomy, "
                "watermark, signature, text, logo, worst quality"
            )

        logger.info(f"Generating thumbnail: {prompt[:50]}...")

        # Generate image
        image = self.pipe(
            prompt=prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            num_inference_steps=num_inference_steps,
            guidance_scale=guidance_scale,
        ).images[0]

        # Save image
        image.save(output_path, quality=95)
        logger.info(f"Thumbnail saved to: {output_path}")

        return output_path

    async def generate_from_summary(
        self,
        title: str,
        summary: str,
        keywords: List[str],
        output_path: Path,
        style: str = "modern",
    ) -> Path:
        """
        Generate thumbnail from video content summary.

        Args:
            title: Video title
            summary: Brief video summary
            keywords: Key topics/themes
            output_path: Path to save image
            style: Visual style (modern, cinematic, minimal, dramatic)

        Returns:
            Path to generated image
        """
        # Build prompt based on content
        style_prompts = {
            "modern": "modern digital art style, clean design, vibrant colors",
            "cinematic": "cinematic lighting, dramatic composition, film still quality",
            "minimal": "minimalist design, simple shapes, elegant composition",
            "dramatic": "dramatic lighting, high contrast, intense atmosphere",
            "tech": "futuristic, technology theme, digital aesthetic, neon accents",
        }

        style_desc = style_prompts.get(style, style_prompts["modern"])

        # Construct the prompt
        keyword_str = ", ".join(keywords[:5]) if keywords else ""

        prompt = (
            f"YouTube video thumbnail, {style_desc}, "
            f"topic: {title}, themes: {keyword_str}, "
            f"professional quality, eye-catching, 4K resolution, "
            f"suitable for video platform thumbnail"
        )

        return await self.generate(
            prompt=prompt,
            output_path=output_path,
        )

    async def extract_frame_thumbnail(
        self,
        video_path: Path,
        output_path: Path,
        timestamp: float = None,
    ) -> Path:
        """
        Extract a frame from video as thumbnail (fallback method).

        Args:
            video_path: Path to video file
            timestamp: Time in seconds (auto-select if None)
            output_path: Path to save thumbnail

        Returns:
            Path to extracted thumbnail
        """
        import subprocess

        video_path = Path(video_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # If no timestamp, extract from 10% into the video
        if timestamp is None:
            # Get video duration
            cmd = [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(video_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            duration = float(result.stdout.strip())
            timestamp = duration * 0.1  # 10% into video

        # Extract frame
        cmd = [
            "ffmpeg",
            "-ss", str(timestamp),
            "-i", str(video_path),
            "-vframes", "1",
            "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2",
            "-y",
            str(output_path),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Frame extraction failed: {result.stderr}")

        logger.info(f"Frame thumbnail extracted to: {output_path}")
        return output_path

    async def add_text_overlay(
        self,
        image_path: Path,
        text: str,
        output_path: Path,
        position: str = "bottom",
        font_size: int = 48,
    ) -> Path:
        """
        Add text overlay to thumbnail.

        Args:
            image_path: Source image path
            text: Text to overlay
            output_path: Output path
            position: Text position (top, center, bottom)
            font_size: Font size in pixels

        Returns:
            Path to image with overlay
        """
        from PIL import Image, ImageDraw, ImageFont

        image_path = Path(image_path)
        output_path = Path(output_path)

        # Load image
        img = Image.open(image_path)
        draw = ImageDraw.Draw(img)

        # Try to load a Chinese-supporting font
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", font_size)
        except OSError:
            try:
                font = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", font_size)
            except OSError:
                font = ImageFont.load_default()

        # Calculate text position
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        x = (img.width - text_width) // 2

        if position == "top":
            y = 20
        elif position == "center":
            y = (img.height - text_height) // 2
        else:  # bottom
            y = img.height - text_height - 40

        # Draw text with shadow for visibility
        shadow_offset = 2
        draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill="black")
        draw.text((x, y), text, font=font, fill="white")

        # Save
        img.save(output_path, quality=95)
        logger.info(f"Text overlay added: {output_path}")

        return output_path
