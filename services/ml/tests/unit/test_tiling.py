"""Unit tests for the tiling utilities."""

from __future__ import annotations

import numpy as np
import pytest

from kepler_ml.preprocess.tiling import (
    TileSpec,
    gaussian_weight_map,
    iter_tiles,
    reassemble_tiles,
    tile_raster,
)


def test_tile_raster_covers_image() -> None:
    specs = tile_raster(width=1024, height=768, tile_size=256, overlap=64)
    assert specs, "should produce at least one tile"
    # The union of tiles should cover the full image.
    xs = [s.x for s in specs]
    ys = [s.y for s in specs]
    assert min(xs) == 0
    assert min(ys) == 0
    assert max(s.x + s.width for s in specs) == 1024
    assert max(s.y + s.height for s in specs) == 768


def test_tile_raster_invalid_inputs() -> None:
    with pytest.raises(ValueError):
        tile_raster(width=0, height=100, tile_size=64, overlap=0)
    with pytest.raises(ValueError):
        tile_raster(width=100, height=100, tile_size=64, overlap=64)
    with pytest.raises(ValueError):
        tile_raster(width=100, height=100, tile_size=0, overlap=0)


def test_tile_raster_single_tile() -> None:
    specs = tile_raster(width=128, height=128, tile_size=256, overlap=0)
    assert len(specs) == 1
    assert specs[0].width == 128
    assert specs[0].height == 128


def test_iter_tiles_yields_specs() -> None:
    specs = list(iter_tiles(512, 512, 256, 64))
    assert all(isinstance(s, TileSpec) for s in specs)
    assert len(specs) > 1


def test_gaussian_weight_map_positive() -> None:
    w = gaussian_weight_map(64, sigma_ratio=0.5)
    assert w.shape == (64, 64)
    assert (w >= 0).all()
    assert w.max() <= 1.0 + 1e-6


def test_reassemble_roundtrip() -> None:
    width, height = 256, 256
    image = np.random.rand(3, height, width).astype(np.float32)
    specs = tile_raster(width, height, tile_size=128, overlap=32)
    weight_map = gaussian_weight_map(128)
    tiles: list[tuple[TileSpec, np.ndarray]] = []
    for spec in specs:
        tile = image[:, spec.y: spec.y + spec.height, spec.x: spec.x + spec.width]
        tiles.append((spec, tile.transpose(1, 2, 0)))
    out = reassemble_tiles(tiles, full_shape=(height, width, 3), weight_map=weight_map)
    assert out.shape == (height, width, 3)
    np.testing.assert_allclose(out, image.transpose(1, 2, 0), atol=1e-4)


def test_reassemble_empty_raises() -> None:
    with pytest.raises(ValueError):
        reassemble_tiles([], full_shape=(10, 10))
