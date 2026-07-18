"""Segmentation and detection heads (PyTorch nn.Modules).

We define simple, deterministic heads. Real model implementations
(vision transformer backbones, deformable attention, etc.) live in
sibling files and are imported lazily.
"""

from __future__ import annotations

from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F


class SegmentationHead(nn.Module):
    """A simple 1x1 conv head over feature maps."""

    def __init__(self, in_channels: int, num_classes: int) -> None:
        super().__init__()
        self.conv = nn.Conv2d(in_channels, num_classes, kernel_size=1, bias=True)

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        return self.conv(features)


class UPerNetHead(nn.Module):
    """A simplified UPerNet head.

    The real implementation uses PSP + FPN lateral connections; for MVP
    we provide a workable approximation that supports ONNX export.
    """

    def __init__(self, in_channels: int, num_classes: int, feature_dim: int = 256) -> None:
        super().__init__()
        self.proj = nn.Conv2d(in_channels, feature_dim, kernel_size=1, bias=False)
        self.psp = nn.ModuleList(
            [
                nn.Sequential(
                    nn.AdaptiveAvgPool2d(s),
                    nn.Conv2d(in_channels, feature_dim, kernel_size=1, bias=False),
                    nn.Upsample(scale_factor=s, mode="bilinear", align_corners=False),
                )
                for s in (1, 2, 3, 6)
            ]
        )
        self.fpn_convs = nn.ModuleList(
            [nn.Conv2d(feature_dim, feature_dim, kernel_size=3, padding=1, bias=False) for _ in range(2)]
        )
        self.fpn_ups = nn.ModuleList(
            [nn.Upsample(scale_factor=2.0, mode="bilinear", align_corners=False) for _ in range(1)]
        )
        self.classifier = nn.Conv2d(feature_dim, num_classes, kernel_size=1)

    def forward(self, features: torch.Tensor) -> torch.Tensor:  # type: ignore[override]
        x = self.proj(features)
        psp_out = x
        for psp in self.psp:
            psp_out = psp_out + psp(features)
        # FPN: for MVP we use the PSP output and a single 3x3 refine
        f = self.fpn_convs[0](psp_out)
        f = self.fpn_convs[1](f)
        return self.classifier(f)


class DetectionHead(nn.Module):
    """A simple detection head producing class logits + box deltas.

    Anchors are not used here; this is a minimal head for export tests.
    """

    def __init__(self, in_channels: int, num_classes: int, num_anchors: int = 1) -> None:
        super().__init__()
        self.cls_logits = nn.Conv2d(in_channels, num_anchors * num_classes, kernel_size=1)
        self.bbox_pred = nn.Conv2d(in_channels, num_anchors * 4, kernel_size=1)

    def forward(self, features: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:  # type: ignore[override]
        cls = self.cls_logits(features)
        box = self.bbox_pred(features)
        return cls, box


__all__ = ["SegmentationHead", "UPerNetHead", "DetectionHead", "F", "Any"]
