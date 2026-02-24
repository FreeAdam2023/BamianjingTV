"""Tests for LofiImagePool service."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from app.models.lofi import (
    ImageSource,
    ImageStatus,
    LofiPoolImage,
    LofiTheme,
)
from app.services.lofi_image_pool import LofiImagePool


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def pool(temp_dir):
    with patch("app.services.lofi_image_pool.get_config") as mock_config:
        mock_config.return_value.lofi_images_dir = temp_dir
        return LofiImagePool()


def _make_image(**kwargs) -> LofiPoolImage:
    defaults = {
        "filename": "test.jpg",
        "source": ImageSource.UPLOAD,
    }
    defaults.update(kwargs)
    return LofiPoolImage(**defaults)


class TestAddAndGet:
    def test_add_image(self, pool):
        img = _make_image()
        result = pool.add_image(img)
        assert result.id == img.id
        assert pool.get_image(img.id) is not None

    def test_get_nonexistent(self, pool):
        assert pool.get_image("nonexistent") is None

    def test_persists_to_disk(self, pool, temp_dir):
        img = _make_image()
        pool.add_image(img)
        pool_file = temp_dir / "pool.json"
        assert pool_file.exists()
        data = json.loads(pool_file.read_text())
        assert len(data) == 1
        assert data[0]["id"] == img.id


class TestListImages:
    def test_empty(self, pool):
        assert pool.list_images() == []

    def test_returns_all(self, pool):
        pool.add_image(_make_image(filename="a.jpg"))
        pool.add_image(_make_image(filename="b.jpg"))
        assert len(pool.list_images()) == 2

    def test_filter_by_status(self, pool):
        img1 = _make_image(filename="a.jpg", status=ImageStatus.PENDING)
        img2 = _make_image(filename="b.jpg", status=ImageStatus.APPROVED)
        pool.add_image(img1)
        pool.add_image(img2)
        result = pool.list_images(status=ImageStatus.APPROVED)
        assert len(result) == 1
        assert result[0].id == img2.id

    def test_filter_by_theme(self, pool):
        img1 = _make_image(filename="a.jpg", themes=[LofiTheme.JAZZ])
        img2 = _make_image(filename="b.jpg", themes=[LofiTheme.RAIN])
        pool.add_image(img1)
        pool.add_image(img2)
        result = pool.list_images(theme=LofiTheme.JAZZ)
        assert len(result) == 1
        assert result[0].id == img1.id

    def test_filter_by_source(self, pool):
        img1 = _make_image(filename="a.jpg", source=ImageSource.UPLOAD)
        img2 = _make_image(filename="b.jpg", source=ImageSource.PIXABAY)
        pool.add_image(img1)
        pool.add_image(img2)
        result = pool.list_images(source=ImageSource.PIXABAY)
        assert len(result) == 1
        assert result[0].id == img2.id

    def test_sorted_by_created_at_desc(self, pool):
        from datetime import datetime, timedelta
        img1 = _make_image(filename="a.jpg")
        img1.created_at = datetime.now() - timedelta(hours=1)
        img2 = _make_image(filename="b.jpg")
        pool.add_image(img1)
        pool.add_image(img2)
        result = pool.list_images()
        assert result[0].id == img2.id


class TestUpdateStatus:
    def test_update(self, pool):
        img = _make_image()
        pool.add_image(img)
        result = pool.update_status(img.id, ImageStatus.APPROVED)
        assert result is not None
        assert result.status == ImageStatus.APPROVED

    def test_not_found(self, pool):
        assert pool.update_status("nonexistent", ImageStatus.APPROVED) is None


class TestUpdateThemes:
    def test_update(self, pool):
        img = _make_image()
        pool.add_image(img)
        result = pool.update_themes(img.id, [LofiTheme.JAZZ, LofiTheme.PIANO])
        assert result is not None
        assert result.themes == [LofiTheme.JAZZ, LofiTheme.PIANO]

    def test_not_found(self, pool):
        assert pool.update_themes("nonexistent", []) is None


class TestDeleteImage:
    def test_delete_with_file(self, pool, temp_dir):
        # Create a real file
        (temp_dir / "test.jpg").write_bytes(b"fake image")
        img = _make_image(filename="test.jpg")
        pool.add_image(img)

        result = pool.delete_image(img.id)
        assert result is True
        assert pool.get_image(img.id) is None
        assert not (temp_dir / "test.jpg").exists()

    def test_delete_without_file(self, pool):
        img = _make_image(filename="nonexistent.jpg")
        pool.add_image(img)
        result = pool.delete_image(img.id)
        assert result is True

    def test_delete_not_found(self, pool):
        assert pool.delete_image("nonexistent") is False


class TestGetRandomApproved:
    def test_no_approved(self, pool):
        pool.add_image(_make_image(status=ImageStatus.PENDING))
        assert pool.get_random_approved() is None

    def test_returns_approved(self, pool):
        img = _make_image(status=ImageStatus.APPROVED)
        pool.add_image(img)
        result = pool.get_random_approved()
        assert result is not None
        assert result.id == img.id

    def test_with_theme_filter(self, pool):
        img1 = _make_image(filename="a.jpg", status=ImageStatus.APPROVED, themes=[LofiTheme.JAZZ])
        img2 = _make_image(filename="b.jpg", status=ImageStatus.APPROVED, themes=[LofiTheme.RAIN])
        pool.add_image(img1)
        pool.add_image(img2)

        # Should return themed image when theme matches
        for _ in range(20):
            result = pool.get_random_approved(LofiTheme.JAZZ)
            assert result.id == img1.id

    def test_theme_fallback(self, pool):
        img = _make_image(status=ImageStatus.APPROVED, themes=[LofiTheme.JAZZ])
        pool.add_image(img)
        # No RAIN images, but should still return JAZZ image
        result = pool.get_random_approved(LofiTheme.RAIN)
        assert result is not None
        assert result.id == img.id


class TestSyncFromDisk:
    def test_adds_new_files(self, pool, temp_dir):
        (temp_dir / "sunset.jpg").write_bytes(b"fake")
        (temp_dir / "rain.png").write_bytes(b"fake")
        added = pool.sync_from_disk()
        assert added == 2
        assert len(pool.list_images()) == 2

    def test_skips_known_files(self, pool, temp_dir):
        (temp_dir / "existing.jpg").write_bytes(b"fake")
        img = _make_image(filename="existing.jpg")
        pool.add_image(img)

        added = pool.sync_from_disk()
        assert added == 0
        assert len(pool.list_images()) == 1

    def test_skips_non_image_files(self, pool, temp_dir):
        (temp_dir / "pool.json").write_text("{}")
        (temp_dir / "readme.txt").write_text("hello")
        added = pool.sync_from_disk()
        assert added == 0

    def test_handles_empty_dir(self, pool, temp_dir):
        added = pool.sync_from_disk()
        assert added == 0


class TestPersistence:
    def test_load_after_save(self, temp_dir):
        with patch("app.services.lofi_image_pool.get_config") as mock_config:
            mock_config.return_value.lofi_images_dir = temp_dir

            pool1 = LofiImagePool()
            img = _make_image(status=ImageStatus.APPROVED, themes=[LofiTheme.JAZZ])
            pool1.add_image(img)

            pool2 = LofiImagePool()
            loaded = pool2.get_image(img.id)
            assert loaded is not None
            assert loaded.status == ImageStatus.APPROVED
            assert loaded.themes == [LofiTheme.JAZZ]

    def test_handles_corrupt_file(self, temp_dir):
        pool_file = temp_dir / "pool.json"
        pool_file.write_text("not json")

        with patch("app.services.lofi_image_pool.get_config") as mock_config:
            mock_config.return_value.lofi_images_dir = temp_dir
            pool = LofiImagePool()
        assert len(pool.list_images()) == 0
