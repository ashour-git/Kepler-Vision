"""Evaluation harness: metrics, datasets, run loop."""

from .metrics import (
    ClassificationMetrics,
    SegmentationMetrics,
    DetectionMetrics,
    ChangeDetectionMetrics,
    compute_classification,
    compute_segmentation,
    compute_detection,
    compute_change_detection,
)
from .runner import EvalRunner, EvalConfig, EvalOutput

__all__ = [
    "ClassificationMetrics",
    "SegmentationMetrics",
    "DetectionMetrics",
    "ChangeDetectionMetrics",
    "compute_classification",
    "compute_segmentation",
    "compute_detection",
    "compute_change_detection",
    "EvalRunner",
    "EvalConfig",
    "EvalOutput",
]
