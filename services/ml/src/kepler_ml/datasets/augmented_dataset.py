"""Augmented tile dataset: wraps `TileDataset` with on-the-fly augmentation."""

from __future__ import annotations

from typing import Any, Iterator

import numpy as np

from ..preprocess.augmentation import apply_train, build_train_augmentation
from .tile_dataset import TileDataset, TileSample


class AugmentedTileDataset:
    """Wraps a `TileDataset` and applies a training augmentation pipeline."""

    def __init__(self, base: TileDataset, *, augmentation: Any | None = None, seed: int = 0) -> None:
        self._base = base
        self._aug = augmentation or build_train_augmentation()
        self._seed = int(seed)

    def __len__(self) -> int:
        return len(self._base)

    def __getitem__(self, idx: int) -> TileSample:
        sample = self._base[idx]
        rng = np.random.default_rng(self._seed + idx)
        image, mask = apply_train(sample.image, sample.mask, self._aug)
        return TileSample(
            image=image,
            mask=mask if mask is not None else sample.mask,
            metadata={**sample.metadata, "augmented": True, "seed": self._seed + int(idx)},
        )

    def __iter__(self) -> Iterator[TileSample]:
        for i in range(len(self)):
            yield self[i]


__all__ = ["AugmentedTileDataset"]
