"""Tiling utilities for large rasters.

We tile with overlap and reassemble using a cosine-weighted blend to
eliminate seam artifacts. The tile plan is deterministic given the
input shape and parameters.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterator, Sequence

import numpy as np


@dataclass(frozen=True, slots=True)
class TileSpec:
    """A single tile within a larger raster."""

    index: tuple[int, int]  # (row, col) in the tile grid
    x: int  # top-left x
    y: int  # top-left y
    width: int
    height: int
    full_width: int
    full_height: int
    overlap: int


def tile_raster(
    width: int,
    height: int,
    tile_size: int,
    overlap: int,
) -> list[TileSpec]:
    """Generate tile specs for a raster of `width` x `height`.

    `tile_size` is the per-tile side. `overlap` is the pixel overlap on
    each side. The last tile is right/bottom-aligned to the raster edge.
    """
    if tile_size <= 0:
        raise ValueError("tile_size must be positive")
    if overlap < 0 or overlap >= tile_size:
        raise ValueError("overlap must be in [0, tile_size)")
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")

    stride = tile_size - overlap
    cols = max(1, math.ceil((width - overlap) / stride))
    rows = max(1, math.ceil((height - overlap) / stride))
    specs: list[TileSpec] = []
    for r in range(rows):
        for c in range(cols):
            x = c * stride
            y = r * stride
            w = tile_size
            h = tile_size
            if x + w > width:
                x = max(0, width - tile_size)
                w = min(tile_size, width - x)
            if y + h > height:
                y = max(0, height - tile_size)
                h = min(tile_size, height - y)
            specs.append(
                TileSpec(
                    index=(r, c),
                    x=x,
                    y=y,
                    width=w,
                    height=h,
                    full_width=width,
                    full_height=height,
                    overlap=overlap,
                )
            )
    return specs


def gaussian_weight_map(size: int, sigma_ratio: float = 0.5) -> np.ndarray:
    """Return a 2D Gaussian weight map for blending tiles.

    `sigma_ratio` is sigma/size. We clip negative values to 0.
    """
    sigma = max(1.0, size * sigma_ratio)
    coords = np.arange(size, dtype=np.float32) - (size - 1) / 2.0
    g1d = np.exp(-(coords ** 2) / (2.0 * sigma * sigma))
    g2d = np.outer(g1d, g1d)
    return np.clip(g2d, 0.0, 1.0).astype(np.float32)


def reassemble_tiles(
    tiles: Sequence[tuple[TileSpec, np.ndarray]],
    full_shape: tuple[int, int] | tuple[int, int, int],
    weight_map: np.ndarray | None = None,
) -> np.ndarray:
    """Blend tiles back into a full raster using a weight map.

    `tiles` is a list of `(TileSpec, ndarray)` pairs. `ndarray` shape is
    `(H, W, C)` for a 2D image, or `(H, W)` for a mask. `full_shape` is
    the target output shape `(H, W)` or `(H, W, C)`.
    """
    if not tiles:
        raise ValueError("tiles is empty")
    if len(full_shape) not in (2, 3):
        raise ValueError("full_shape must be (H, W) or (H, W, C)")

    out = np.zeros(full_shape, dtype=np.float32)
    wsum = np.zeros(full_shape[:2], dtype=np.float32)

    first_h, first_w = tiles[0][1].shape[:2]
    if weight_map is None or weight_map.shape != (first_h, first_w):
        weight_map = np.ones((first_h, first_w), dtype=np.float32)

    for spec, tile in tiles:
        if tile.shape[:2] != (spec.height, spec.width):
            raise ValueError(
                f"Tile shape {tile.shape[:2]} does not match spec {(spec.height, spec.width)}"
            )
        x0, y0 = spec.x, spec.y
        x1, y1 = x0 + spec.width, y0 + spec.height
        wm = weight_map[: spec.height, : spec.width]
        if len(full_shape) == 2:
            out[y0:y1, x0:x1] += tile * wm
            wsum[y0:y1, x0:x1] += wm
        else:
            out[y0:y1, x0:x1] += tile * wm[:, :, None]
            wsum[y0:y1, x0:x1] += wm

    wsum = np.maximum(wsum, 1e-6)
    if len(full_shape) == 2:
        return (out / wsum).astype(np.float32)
    return (out / wsum[:, :, None]).astype(np.float32)


def iter_tiles(
    width: int,
    height: int,
    tile_size: int,
    overlap: int,
) -> Iterator[TileSpec]:
    """Iterate over tile specs."""
    return iter(tile_raster(width, height, tile_size, overlap))


__all__ = [
    "TileSpec",
    "tile_raster",
    "iter_tiles",
    "reassemble_tiles",
    "gaussian_weight_map",
]
