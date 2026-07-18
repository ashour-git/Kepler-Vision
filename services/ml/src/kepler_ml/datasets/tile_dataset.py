"""Tile dataset: in-memory chip dataset for training and evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

import numpy as np


@dataclass(frozen=True, slots=True)
class TileSample:
    """A single training sample: (image, mask, metadata)."""

    image: np.ndarray  # CHW
    mask: np.ndarray | None  # HW
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TileDatasetConfig:
    """Configuration for `TileDataset`."""

    chip_size: int = 256
    in_channels: int = 6
    num_classes: int = 1
    include_mask: bool = True
    cache_in_memory: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


class TileDataset:
    """An in-memory dataset of `TileSample`s.

    For MVP we support two construction modes:

    1. From an explicit list of samples (used in tests and small experiments).
    2. From a directory of `image.npy` and `mask.npy` files (one per sample).
    """

    def __init__(
        self,
        samples: Sequence[TileSample] | None = None,
        *,
        directory: Path | str | None = None,
        config: TileDatasetConfig | None = None,
    ) -> None:
        self.config = config or TileDatasetConfig()
        self._samples: list[TileSample] = []
        if samples is not None:
            self._samples.extend(samples)
        if directory is not None:
            self._load_directory(Path(directory))

    def _load_directory(self, directory: Path) -> None:
        """Load a directory of `.npy` files. Each `id.npy` may have `id_mask.npy`."""
        if not directory.exists():
            raise FileNotFoundError(directory)
        for img_path in sorted(directory.glob("*_img.npy")):
            stem = img_path.stem.removesuffix("_img")
            image = np.load(img_path).astype(np.float32)
            mask_path = directory / f"{stem}_mask.npy"
            mask: np.ndarray | None = None
            if mask_path.exists() and self.config.include_mask:
                mask = np.load(mask_path)
            self._samples.append(TileSample(image=image, mask=mask))

    def __len__(self) -> int:
        return len(self._samples)

    def __getitem__(self, idx: int) -> TileSample:
        return self._samples[idx]

    def add(self, sample: TileSample) -> None:
        self._samples.append(sample)

    def extend(self, samples: Sequence[TileSample]) -> None:
        self._samples.extend(samples)

    def get_metadata(self) -> dict[str, Any]:
        return {"num_samples": len(self._samples), **self.config.metadata}


__all__ = ["TileDataset", "TileSample", "TileDatasetConfig"]
