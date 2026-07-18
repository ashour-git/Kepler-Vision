"""Cloud / SNOW / shadow masking.

We expose a deterministic, band-only cloud-mask function. For production
quality, this is replaced by an ensemble of `s2cloudless` + a custom ViT.
The interface here is what downstream code depends on.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

BandOrder = Literal["rgb_nir_swir"]


@dataclass(frozen=True, slots=True)
class CloudMaskResult:
    """Boolean masks per category. Each is HW."""

    cloud: np.ndarray  # dtype=bool
    snow: np.ndarray
    shadow: np.ndarray

    @property
    def any_mask(self) -> np.ndarray:
        return self.cloud | self.snow | self.shadow


def compute_simple_cloud_mask(
    image: np.ndarray,
    *,
    band_order: BandOrder = "rgb_nir_swir",
    cloud_threshold: float = 0.18,
    snow_threshold: float = 0.30,
    shadow_brightness_quantile: float = 0.08,
) -> CloudMaskResult:
    """Compute a simple band-only cloud mask.

    Assumes Sentinel-2 L2A surface reflectance in [0, 1] with the
    channel order configured by `band_order`. This is a cheap prior;
    production code should use a learned model.
    """
    if image.ndim != 3:
        raise ValueError("image must be CHW")
    if band_order != "rgb_nir_swir":
        raise NotImplementedError(f"band_order {band_order} not supported")

    rgb_brightness = image[:3].mean(axis=0)
    nir = image[3]
    swir = image[4] if image.shape[0] > 4 else nir

    # Cloud: bright in visible, bright in SWIR, low NDVI
    ndvi = (nir - image[0]) / (nir + image[0] + 1e-6)
    cloud = (rgb_brightness > cloud_threshold) & (swir > cloud_threshold) & (ndvi < 0.2)

    # Snow: very bright, even higher NIR
    snow = (rgb_brightness > snow_threshold) & (nir > 0.35) & (ndvi < 0.1)

    # Shadow: very dark, low brightness
    brightness_threshold = np.quantile(rgb_brightness, shadow_brightness_quantile)
    shadow = (rgb_brightness < brightness_threshold) & (nir < 0.08)

    return CloudMaskResult(
        cloud=cloud.astype(bool),
        snow=snow.astype(bool),
        shadow=shadow.astype(bool),
    )


__all__ = ["CloudMaskResult", "compute_simple_cloud_mask", "BandOrder"]
