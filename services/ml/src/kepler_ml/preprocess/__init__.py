"""Raster preprocessing: tiling, normalization, augmentation, cloud masking."""

from .tiling import (
    TileSpec,
    tile_raster,
    reassemble_tiles,
    gaussian_weight_map,
)
from .normalization import (
    BandStats,
    compute_band_stats,
    normalize_image,
    denormalize_image,
)
from .augmentation import (
    build_train_augmentation,
    build_eval_augmentation,
)
from .cloud_mask import (
    CloudMaskResult,
    compute_simple_cloud_mask,
)

__all__ = [
    "TileSpec",
    "tile_raster",
    "reassemble_tiles",
    "gaussian_weight_map",
    "BandStats",
    "compute_band_stats",
    "normalize_image",
    "denormalize_image",
    "build_train_augmentation",
    "build_eval_augmentation",
    "CloudMaskResult",
    "compute_simple_cloud_mask",
]
