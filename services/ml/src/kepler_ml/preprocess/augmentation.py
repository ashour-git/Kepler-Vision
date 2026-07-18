"""Augmentation pipelines using albumentations 2.x.

We expose a `build_train_augmentation` for training (with flips, rotations,
brightness, gaussian noise) and `build_eval_augmentation` for evaluation
(no random transforms). We accept numpy arrays in CHW format.
"""

from __future__ import annotations

from typing import Any

import numpy as np

try:  # albumentations is required at runtime, optional at import for type-checking
    import albumentations as A
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "albumentations is required for augmentation pipelines. "
        "Install with `pip install albumentations`."
    ) from exc


def _to_hwc(image: np.ndarray) -> np.ndarray:
    """Convert CHW → HWC for albumentations."""
    if image.ndim == 3 and image.shape[0] in (1, 3, 4, 6, 8, 12):
        return np.transpose(image, (1, 2, 0))
    return image


def _to_chw(image: np.ndarray) -> np.ndarray:
    """Convert HWC → CHW after augmentation."""
    if image.ndim == 3 and image.shape[-1] in (1, 3, 4, 6, 8, 12):
        return np.transpose(image, (2, 0, 1))
    return image


def build_train_augmentation(
    *,
    max_rotate_deg: int = 90,
    brightness_contrast: bool = True,
    gauss_noise: bool = True,
    coarse_dropout: bool = True,
    p: float = 0.5,
) -> Any:
    """Build a training augmentation pipeline (HWC image + mask input).

    albumentations 2.x dropped the `Flip` / `Rotate` classes in favor of
    functional names like `HorizontalFlip`, `Affine`, etc. We use the
    2.x names.
    """
    transforms: list[Any] = [
        A.HorizontalFlip(p=p),
        A.VerticalFlip(p=p),
        A.Affine(
            rotate=(-max_rotate_deg, max_rotate_deg),
            translate_percent={"x": (-0.05, 0.05), "y": (-0.05, 0.05)},
            p=p,
            border_mode=0,
        ),
    ]
    if brightness_contrast:
        transforms.append(A.RandomBrightnessContrast(brightness_limit=0.1, contrast_limit=0.1, p=p))
    if gauss_noise:
        transforms.append(A.GaussNoise(p=p))
    if coarse_dropout:
        transforms.append(
            A.CoarseDropout(
                num_holes_range=(1, 4),
                hole_height_range=(8, 32),
                hole_width_range=(8, 32),
                p=p,
            )
        )
    return A.Compose(transforms)


def build_eval_augmentation() -> Any:
    """Identity pipeline (no augmentation) for evaluation."""
    return A.Compose([])


def apply_train(
    image_chw: np.ndarray,
    mask_hw: np.ndarray | None,
    pipeline: Any,
) -> tuple[np.ndarray, np.ndarray | None]:
    """Apply a training pipeline to a CHW image and optional HW mask."""
    image_hwc = _to_hwc(image_chw)
    if mask_hw is not None:
        result = pipeline(image=image_hwc, mask=mask_hw)
        return _to_chw(result["image"]), result["mask"]
    result = pipeline(image=image_hwc)
    return _to_chw(result["image"]), None


__all__ = [
    "build_train_augmentation",
    "build_eval_augmentation",
    "apply_train",
]
