"""Training pipeline: PyTorch Lightning trainer + common heads."""

from .trainer import (
    TrainingConfig,
    SegmentationTrainer,
    fit_segmentation_model,
)
from .heads import SegmentationHead, UPerNetHead

__all__ = [
    "TrainingConfig",
    "SegmentationTrainer",
    "fit_segmentation_model",
    "SegmentationHead",
    "UPerNetHead",
]
