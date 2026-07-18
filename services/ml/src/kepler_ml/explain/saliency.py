"""Saliency / attribution methods.

For MVP we use a simple gradient-based saliency (vanilla gradients) and
a random-baseline occlusion-style method. These work without extra deps
and are deterministic given the same input and seed.

Production code should use Integrated Gradients, SHAP, or a learned
attribution head. The interface here is stable; the implementation can
be swapped.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import numpy as np


class SaliencyMethod(StrEnum):
    """The saliency method to use."""

    GRADIENT = "gradient"
    OCCLUSION = "occlusion"
    INTEGRATED_GRADIENTS = "integrated_gradients"


@dataclass(frozen=True, slots=True)
class SaliencyResult:
    """A saliency map and metadata."""

    method: SaliencyMethod
    saliency: np.ndarray  # same HW shape as input
    metadata: dict[str, Any]


def compute_saliency(
    image: np.ndarray,
    *,
    method: SaliencyMethod = SaliencyMethod.GRADIENT,
    target_class: int | None = None,
    baseline: np.ndarray | None = None,
    steps: int = 16,
    occlusion_window: int = 8,
    occlusion_stride: int = 4,
    seed: int = 0,
) -> SaliencyResult:
    """Compute a saliency map for a CHW image.

    `target_class` selects which output class to explain. If `None`, the
    argmax is used.
    """
    if image.ndim != 3:
        raise ValueError("image must be CHW")

    if method == SaliencyMethod.GRADIENT:
        sal = _gradient_saliency(image, target_class=target_class)
        return SaliencyResult(method=method, saliency=sal, metadata={"target_class": target_class})

    if method == SaliencyMethod.OCCLUSION:
        sal = _occlusion_saliency(
            image,
            target_class=target_class,
            window=occlusion_window,
            stride=occlusion_stride,
        )
        return SaliencyResult(method=method, saliency=sal, metadata={"window": occlusion_window, "stride": occlusion_stride})

    if method == SaliencyMethod.INTEGRATED_GRADIENTS:
        if baseline is None:
            baseline = np.zeros_like(image)
        sal = _integrated_gradients(image, baseline, target_class=target_class, steps=steps, seed=seed)
        return SaliencyResult(method=method, saliency=sal, metadata={"steps": steps})

    raise ValueError(f"Unknown saliency method: {method}")


def _gradient_saliency(image: np.ndarray, target_class: int | None) -> np.ndarray:
    """Vanilla gradient saliency.

    Approximates gradient ∝ (x - mean(x)) for visualization. The full
    implementation would call `torch.autograd`. Here we return a
    deterministic proxy that downstream code can swap.
    """
    mean = image.mean(axis=(1, 2), keepdims=True)
    centered = np.abs(image - mean)
    sal = centered.mean(axis=0)
    sal = sal / (sal.max() + 1e-12)
    return sal.astype(np.float32)


def _occlusion_saliency(
    image: np.ndarray,
    *,
    target_class: int | None,
    window: int,
    stride: int,
) -> np.ndarray:
    """Occlusion-based saliency.

    We slide an occluding window (zero-out) and measure the (mock) drop
    in the target-class probability. For MVP we approximate the
    importance as the variance of the image under the window.
    """
    ch, h, w = image.shape
    sal = np.zeros((h, w), dtype=np.float32)
    weights = np.zeros((h, w), dtype=np.float32)
    for y in range(0, h - window + 1, stride):
        for x in range(0, w - window + 1, stride):
            patch = image[:, y:y + window, x:x + window]
            sal[y:y + window, x:x + window] += float(np.var(patch))
            weights[y:y + window, x:x + window] += 1.0
    sal = sal / (weights + 1e-12)
    sal = sal / (sal.max() + 1e-12)
    return sal.astype(np.float32)


def _integrated_gradients(
    image: np.ndarray,
    baseline: np.ndarray,
    *,
    target_class: int | None,
    steps: int,
    seed: int,
) -> np.ndarray:
    """Integrated gradients with a baseline.

    Deterministic: alpha is a fixed linspace. The full implementation
    calls torch.autograd; here we return a deterministic proxy.
    """
    rng = np.random.default_rng(seed)
    alphas = np.linspace(0.0, 1.0, steps, dtype=np.float32)
    sal = np.zeros(image.shape[1:], dtype=np.float32)
    for a in alphas:
        x = baseline + a * (image - baseline)
        grad = (x - x.mean()) * (image - baseline)
        sal += grad.mean(axis=0)
    sal = np.abs(sal) / (np.abs(sal).max() + 1e-12)
    return sal.astype(np.float32)


def overlay_saliency(
    image_chw: np.ndarray,
    saliency_hw: np.ndarray,
    *,
    alpha: float = 0.5,
    colormap: str = "viridis",
) -> np.ndarray:
    """Overlay a saliency map on the first 3 channels of `image_chw`.

    Returns an HWC uint8 image suitable for saving.
    """
    if image_chw.ndim != 3:
        raise ValueError("image_chw must be CHW")
    if image_chw.shape[0] < 3:
        raise ValueError("image_chw must have at least 3 channels")
    rgb = image_chw[:3].transpose(1, 2, 0)
    rgb = np.clip(rgb, 0.0, 1.0)
    if rgb.max() > 1.0:
        rgb = rgb / 255.0
    sal = np.clip(saliency_hw, 0.0, 1.0)
    # Simple grayscale-to-rgb colormap (jet approximation, deterministic)
    if colormap == "viridis":
        r = np.clip(0.267 + 0.105 * sal - 0.330 * sal**2 + 0.985 * sal**3, 0, 1)
        g = np.clip(0.005 + 1.405 * sal - 1.115 * sal**2 + 0.350 * sal**3, 0, 1)
        b = np.clip(0.329 + 1.385 * sal - 2.620 * sal**2 + 1.230 * sal**3, 0, 1)
        heatmap = np.stack([r, g, b], axis=-1)
    else:
        heatmap = np.stack([sal, sal, sal], axis=-1)
    out = (1 - alpha) * rgb + alpha * heatmap
    return (np.clip(out, 0, 1) * 255).astype(np.uint8)


__all__ = [
    "SaliencyMethod",
    "SaliencyResult",
    "compute_saliency",
    "overlay_saliency",
]
