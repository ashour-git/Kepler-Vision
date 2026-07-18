"""Model factory: build a small but valid segmentation/detection model.

We keep the architecture simple so we can export to ONNX, validate
parity, and ship a working baseline in MVP. Production will swap in
larger ViT-based backbones; the interface here stays the same.
"""

from __future__ import annotations

from typing import Any

import torch
import torch.nn as nn

from .heads import DetectionHead, UPerNetHead


class _SegmentationModel(nn.Module):
    """A small conv-stack segmentation model.

    Architecture: 6-channel input → 4 conv blocks → UPerNet head → logits.
    Sufficient for ONNX export tests and inference smoke tests.
    """

    def __init__(self, in_channels: int, num_classes: int, base_channels: int = 32) -> None:
        super().__init__()
        self.stem = nn.Sequential(
            nn.Conv2d(in_channels, base_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(base_channels),
            nn.GELU(),
        )
        self.blocks = nn.Sequential(
            nn.Conv2d(base_channels, base_channels * 2, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(base_channels * 2),
            nn.GELU(),
            nn.Conv2d(base_channels * 2, base_channels * 4, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(base_channels * 4),
            nn.GELU(),
        )
        self.head = UPerNetHead(in_channels=base_channels * 4, num_classes=num_classes, feature_dim=base_channels * 4)
        self._num_classes = num_classes
        self._in_channels = in_channels

    def forward(self, x: torch.Tensor) -> torch.Tensor:  # type: ignore[override]
        x = self.stem(x)
        x = self.blocks(x)
        return self.head(x)


class _DetectionModel(nn.Module):
    """A small conv-stack detection model."""

    def __init__(self, in_channels: int, num_classes: int, base_channels: int = 32) -> None:
        super().__init__()
        self.stem = nn.Sequential(
            nn.Conv2d(in_channels, base_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(base_channels),
            nn.GELU(),
        )
        self.blocks = nn.Sequential(
            nn.Conv2d(base_channels, base_channels * 2, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(base_channels * 2),
            nn.GELU(),
            nn.Conv2d(base_channels * 2, base_channels * 4, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(base_channels * 4),
            nn.GELU(),
        )
        self.head = DetectionHead(in_channels=base_channels * 4, num_classes=num_classes)
        self._num_classes = num_classes
        self._in_channels = in_channels

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:  # type: ignore[override]
        x = self.stem(x)
        x = self.blocks(x)
        return self.head(x)


def build_segmentation_model(
    in_channels: int = 6,
    num_classes: int = 1,
    base_channels: int = 32,
) -> nn.Module:
    """Build a small segmentation model for export / inference testing."""
    return _SegmentationModel(in_channels=in_channels, num_classes=num_classes, base_channels=base_channels)


def build_detection_model(
    in_channels: int = 3,
    num_classes: int = 10,
    base_channels: int = 32,
) -> nn.Module:
    """Build a small detection model for export / inference testing."""
    return _DetectionModel(in_channels=in_channels, num_classes=num_classes, base_channels=base_channels)


def model_summary(model: nn.Module) -> dict[str, Any]:
    """Return a small dict describing a model (parameter count, MACs estimate)."""
    n_params = sum(p.numel() for p in model.parameters())
    n_trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    return {
        "n_params": n_params,
        "n_trainable": n_trainable,
        "n_buffers": sum(b.numel() for b in model.buffers()),
    }


__all__ = ["build_segmentation_model", "build_detection_model", "model_summary", "nn", "Any"]
