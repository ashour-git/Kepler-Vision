"""Model architectures: backbones, segmentation heads, detection heads.

We keep these PyTorch-free at the module level so the package can be
imported without torch. Actual definitions are deferred.
"""

from .heads import SegmentationHead, UPerNetHead, DetectionHead
from .factory import build_segmentation_model, build_detection_model

__all__ = [
    "SegmentationHead",
    "UPerNetHead",
    "DetectionHead",
    "build_segmentation_model",
    "build_detection_model",
]
