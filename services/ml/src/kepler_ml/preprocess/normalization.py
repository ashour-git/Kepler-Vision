"""Per-band normalization statistics and transforms."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np


@dataclass(frozen=True, slots=True)
class BandStats:
    """Per-channel mean/std computed on a training corpus."""

    mean: tuple[float, ...]
    std: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.mean) != len(self.std):
            raise ValueError("mean and std must have the same length")
        if not self.std or any(s <= 0 for s in self.std):
            raise ValueError("std values must be positive")

    def __len__(self) -> int:
        return len(self.mean)


def compute_band_stats(samples: Sequence[np.ndarray]) -> BandStats:
    """Compute per-channel mean/std from a list of CHW arrays."""
    if not samples:
        raise ValueError("samples is empty")
    means: list[float] = []
    stds: list[float] = []
    n_channels = samples[0].shape[0]
    for c in range(n_channels):
        flat = np.concatenate([np.asarray(s[c], dtype=np.float32).ravel() for s in samples])
        means.append(float(flat.mean()))
        stds.append(float(flat.std() + 1e-6))
    return BandStats(mean=tuple(means), std=tuple(stds))


def normalize_image(image: np.ndarray, stats: BandStats) -> np.ndarray:
    """Normalize a CHW image: (x - mean) / std, clipped to ±10."""
    if image.ndim != 3:
        raise ValueError("image must be CHW")
    if image.shape[0] != len(stats):
        raise ValueError("channel count mismatch")
    mean = np.asarray(stats.mean, dtype=np.float32).reshape(-1, 1, 1)
    std = np.asarray(stats.std, dtype=np.float32).reshape(-1, 1, 1)
    out = (image.astype(np.float32) - mean) / std
    return np.clip(out, -10.0, 10.0).astype(np.float32)


def denormalize_image(image: np.ndarray, stats: BandStats) -> np.ndarray:
    """Reverse normalize: x * std + mean."""
    if image.ndim != 3:
        raise ValueError("image must be CHW")
    mean = np.asarray(stats.mean, dtype=np.float32).reshape(-1, 1, 1)
    std = np.asarray(stats.std, dtype=np.float32).reshape(-1, 1, 1)
    return (image.astype(np.float32) * std + mean).astype(np.float32)


__all__ = [
    "BandStats",
    "compute_band_stats",
    "normalize_image",
    "denormalize_image",
]
