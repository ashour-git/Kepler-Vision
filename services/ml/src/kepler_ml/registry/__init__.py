"""Model registry glue and Triton model configs."""

from .registry import (
    ModelRegistry,
    ModelNotFoundError,
    ModelAlreadyExistsError,
    get_default_registry,
    reset_default_registry,
)
from .triton_config import (
    TensorSpec,
    TritonConfig,
    build_classification_config,
    build_detection_config,
    build_segmentation_config,
    write_config,
)

__all__ = [
    "ModelRegistry",
    "ModelNotFoundError",
    "ModelAlreadyExistsError",
    "get_default_registry",
    "reset_default_registry",
    "TensorSpec",
    "TritonConfig",
    "build_classification_config",
    "build_segmentation_config",
    "build_detection_config",
    "write_config",
]
