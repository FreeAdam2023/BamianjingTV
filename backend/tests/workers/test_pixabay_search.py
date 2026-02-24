"""Tests for Pixabay search worker."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.workers.pixabay_search import search_pixabay, download_pixabay_image


class TestSearchPixabay:
    @pytest.mark.asyncio
    async def test_no_api_key_raises(self):
        with patch("app.workers.pixabay_search.settings") as mock_settings:
            mock_settings.pixabay_api_key = ""
            with pytest.raises(ValueError, match="PIXABAY_API_KEY not configured"):
                await search_pixabay("test query")

    @pytest.mark.asyncio
    async def test_returns_parsed_results(self):
        with patch("app.workers.pixabay_search.settings") as mock_settings:
            mock_settings.pixabay_api_key = "test-key"

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {
                "totalHits": 2,
                "hits": [
                    {
                        "id": 12345,
                        "webformatURL": "https://pixabay.com/preview_12345.jpg",
                        "largeImageURL": "https://pixabay.com/large_12345.jpg",
                        "tags": "cozy, room, night",
                        "imageWidth": 4000,
                        "imageHeight": 2250,
                    },
                    {
                        "id": 67890,
                        "webformatURL": "https://pixabay.com/preview_67890.jpg",
                        "largeImageURL": "https://pixabay.com/large_67890.jpg",
                        "tags": "rain, window",
                        "imageWidth": 3840,
                        "imageHeight": 2160,
                    },
                ],
            }

            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()

            with patch("app.workers.pixabay_search.httpx.AsyncClient", return_value=mock_client):
                results = await search_pixabay("cozy room")

        assert len(results) == 2
        assert results[0]["id"] == "12345"
        assert results[0]["preview_url"] == "https://pixabay.com/preview_12345.jpg"
        assert results[0]["large_url"] == "https://pixabay.com/large_12345.jpg"
        assert results[0]["tags"] == "cozy, room, night"
        assert results[0]["width"] == 4000
        assert results[0]["height"] == 2250

    @pytest.mark.asyncio
    async def test_empty_results(self):
        with patch("app.workers.pixabay_search.settings") as mock_settings:
            mock_settings.pixabay_api_key = "test-key"

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {"totalHits": 0, "hits": []}

            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()

            with patch("app.workers.pixabay_search.httpx.AsyncClient", return_value=mock_client):
                results = await search_pixabay("qwertyuiop")

        assert results == []


class TestDownloadPixabayImage:
    @pytest.mark.asyncio
    async def test_download_success(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("app.workers.pixabay_search.settings") as mock_settings:
                mock_settings.lofi_images_dir = Path(temp_dir)

                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.raise_for_status = MagicMock()
                mock_response.content = b"fake image data"

                mock_client = AsyncMock()
                mock_client.get.return_value = mock_response
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock()

                with patch("app.workers.pixabay_search.httpx.AsyncClient", return_value=mock_client):
                    result = await download_pixabay_image(
                        pixabay_id="12345",
                        url="https://pixabay.com/large_12345.jpg",
                    )

            assert result.exists()
            assert result.read_bytes() == b"fake image data"
            assert "pixabay_12345" in result.name

    @pytest.mark.asyncio
    async def test_custom_filename(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("app.workers.pixabay_search.settings") as mock_settings:
                mock_settings.lofi_images_dir = Path(temp_dir)

                mock_response = MagicMock()
                mock_response.raise_for_status = MagicMock()
                mock_response.content = b"data"

                mock_client = AsyncMock()
                mock_client.get.return_value = mock_response
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock()

                with patch("app.workers.pixabay_search.httpx.AsyncClient", return_value=mock_client):
                    result = await download_pixabay_image(
                        pixabay_id="123",
                        url="https://example.com/img.png",
                        filename="custom.png",
                    )

            assert result.name == "custom.png"
