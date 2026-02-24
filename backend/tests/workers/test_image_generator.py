"""Tests for AI image generator worker."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from app.models.lofi import LofiTheme
from app.workers.image_generator import (
    generate_lofi_image,
    _theme_to_image_prompt,
    IMAGE_PROMPTS,
)


class TestThemeToImagePrompt:
    def test_all_themes_have_prompts(self):
        for theme in LofiTheme:
            prompt = _theme_to_image_prompt(theme)
            assert isinstance(prompt, str)
            assert len(prompt) > 10

    def test_specific_theme(self):
        prompt = _theme_to_image_prompt(LofiTheme.JAZZ)
        assert "jazz" in prompt.lower()


class TestGenerateLofiImage:
    @pytest.mark.asyncio
    async def test_no_image_model_raises(self):
        with patch("app.workers.image_generator.settings") as mock_settings:
            mock_settings.image_model = ""
            mock_settings.llm_api_key = "test"
            with pytest.raises(ValueError, match="image_model not configured"):
                await generate_lofi_image(LofiTheme.JAZZ)

    @pytest.mark.asyncio
    async def test_no_api_key_raises(self):
        with patch("app.workers.image_generator.settings") as mock_settings:
            mock_settings.image_model = "dall-e-3"
            mock_settings.llm_api_key = ""
            with pytest.raises(ValueError, match="llm_api_key not configured"):
                await generate_lofi_image(LofiTheme.JAZZ)

    @pytest.mark.asyncio
    async def test_url_response(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            with patch("app.workers.image_generator.settings") as mock_settings:
                mock_settings.image_model = "dall-e-3"
                mock_settings.llm_api_key = "test-key"
                mock_settings.llm_base_url = "https://api.test.com/v1"
                mock_settings.lofi_images_dir = temp_path

                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.raise_for_status = MagicMock()
                mock_response.json.return_value = {
                    "data": [{"url": "https://example.com/image.png"}],
                }

                mock_img_response = MagicMock()
                mock_img_response.status_code = 200
                mock_img_response.raise_for_status = MagicMock()
                mock_img_response.content = b"fake png data"

                mock_client = AsyncMock()
                mock_client.post.return_value = mock_response
                mock_client.get.return_value = mock_img_response
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock()

                with patch("app.workers.image_generator.httpx.AsyncClient", return_value=mock_client):
                    result = await generate_lofi_image(LofiTheme.JAZZ)

                assert result.exists()
                assert result.read_bytes() == b"fake png data"
                assert result.parent == temp_path
                assert "jazz" in result.name

    @pytest.mark.asyncio
    async def test_b64_response(self):
        import base64

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            with patch("app.workers.image_generator.settings") as mock_settings:
                mock_settings.image_model = "dall-e-3"
                mock_settings.llm_api_key = "test-key"
                mock_settings.llm_base_url = "https://api.test.com/v1"
                mock_settings.lofi_images_dir = temp_path

                b64_data = base64.b64encode(b"fake png data").decode()
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.raise_for_status = MagicMock()
                mock_response.json.return_value = {
                    "data": [{"b64_json": b64_data}],
                }

                mock_client = AsyncMock()
                mock_client.post.return_value = mock_response
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock()

                with patch("app.workers.image_generator.httpx.AsyncClient", return_value=mock_client):
                    result = await generate_lofi_image(LofiTheme.RAIN, custom_prompt="rainy night")

                assert result.exists()
                assert result.read_bytes() == b"fake png data"

    @pytest.mark.asyncio
    async def test_custom_prompt_used(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            with patch("app.workers.image_generator.settings") as mock_settings:
                mock_settings.image_model = "dall-e-3"
                mock_settings.llm_api_key = "test-key"
                mock_settings.llm_base_url = "https://api.test.com/v1"
                mock_settings.lofi_images_dir = temp_path

                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.raise_for_status = MagicMock()
                mock_response.json.return_value = {
                    "data": [{"url": "https://example.com/image.png"}],
                }

                mock_img_response = MagicMock()
                mock_img_response.raise_for_status = MagicMock()
                mock_img_response.content = b"img"

                mock_client = AsyncMock()
                mock_client.post.return_value = mock_response
                mock_client.get.return_value = mock_img_response
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock()

                with patch("app.workers.image_generator.httpx.AsyncClient", return_value=mock_client):
                    await generate_lofi_image(LofiTheme.JAZZ, custom_prompt="my custom scene")

                # Check that the custom prompt was passed
                call_args = mock_client.post.call_args
                body = call_args.kwargs.get("json", {})
                assert body["prompt"] == "my custom scene"
