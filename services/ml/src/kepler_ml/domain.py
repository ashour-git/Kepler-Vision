"""ML domain types — pure Pydantic models."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ModelStatus(StrEnum):
    EXPERIMENTAL = "experimental"
    STAGING = "staging"
    GA = "ga"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


class ModelFramework(StrEnum):
    PYTORCH = "pytorch"
    TENSORFLOW = "tensorflow"
    ONNX = "onnx"
    TENSORRT = "tensorrt"


class ModelTask(StrEnum):
    CHANGE_DETECTION = "change_detection"
    SEMANTIC_SEGMENTATION = "semantic_segmentation"
    OBJECT_DETECTION = "object_detection"
    CLASSIFICATION = "classification"
    BUILDING_DETECTION = "building_detection"
    ROAD_DETECTION = "road_detection"
    WATER_DETECTION = "water_detection"
    VEGETATION_DETECTION = "vegetation_detection"
    LAND_COVER = "land_cover"


class License(StrEnum):
    MIT = "mit"
    APACHE_2 = "apache-2"
    PROPRIETARY = "proprietary"
    CC_BY_4 = "cc-by-4"
    INTERNAL = "internal"


class BoundingBox(BaseModel):
    """Axis-aligned bounding box in (x, y, w, h) pixel space."""

    x: float
    y: float
    w: float
    h: float

    @property
    def area(self) -> float:
        return max(0.0, self.w) * max(0.0, self.h)


class OrientedBox(BaseModel):
    """Oriented bounding box (4 corners)."""

    points: tuple[tuple[float, float], ...]

    @field_validator("points")
    @classmethod
    def _validate_points(cls, v: tuple[tuple[float, float], ...]) -> tuple[tuple[float, float], ...]:
        if len(v) != 4:
            raise ValueError("OrientedBox requires exactly 4 points")
        return v


class Detection(BaseModel):
    """An object detection result."""

    class_name: str
    score: float = Field(ge=0.0, le=1.0)
    bbox: BoundingBox | OrientedBox
    metadata: dict[str, Any] = Field(default_factory=dict)


class SegmentationMask(BaseModel):
    """A segmentation mask (single channel) plus metadata."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    width: int
    height: int
    num_classes: int
    data: bytes  # raw uint8 / int16 / float32 buffer
    dtype: str = "uint8"  # uint8 | int16 | float32
    class_names: list[str] = Field(default_factory=list)


class ChangeDetectionResult(BaseModel):
    """Output of a change detection model."""

    width: int
    height: int
    score: float = Field(ge=0.0, le=1.0)
    change_mask: SegmentationMask
    changes: list[Detection] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)  # scene IDs


class ModelArtifact(BaseModel):
    """Pointer to a model artifact on object storage."""

    uri: str  # e.g. gs://bucket/models/cloud_mask/v1/model.trt
    sha256: str
    size_bytes: int
    framework: ModelFramework
    precision: str  # fp32, fp16, int8


class ModelCard(BaseModel):
    """A model card, structured per the AI plan."""

    model_config = ConfigDict(extra="forbid")

    intended_use: str
    limitations: list[str] = Field(default_factory=list)
    training_data_summary: str = ""
    eval_summary: str = ""
    license: License = License.PROPRIETARY
    allowed_uses: list[str] = Field(default_factory=list)
    restricted_uses: list[str] = Field(default_factory=list)
    contact: str | None = None
    version: str = "0.1.0"
    created_at: datetime = Field(default_factory=lambda: datetime.utcnow())


class ModelVersion(BaseModel):
    """An immutable, content-addressed model version."""

    model_id: str
    name: str
    task: ModelTask
    version: str  # semver
    status: ModelStatus = ModelStatus.EXPERIMENTAL
    framework: ModelFramework
    artifacts: list[ModelArtifact] = Field(default_factory=list)
    card: ModelCard
    eval_uri: str | None = None
    replaces_version: str | None = None
    released_at: datetime = Field(default_factory=lambda: datetime.utcnow())
    lineage: dict[str, Any] = Field(default_factory=dict)
    # Provenance: deterministic replay
    code_commit: str | None = None
    dataset_hash: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    random_seed: int | None = None

    @property
    def content_hash(self) -> str:
        """A deterministic hash of the version's identity."""
        canonical = json.dumps(
            {
                "model_id": self.model_id,
                "name": self.name,
                "task": self.task.value,
                "version": self.version,
                "framework": self.framework.value,
                "artifacts": [
                    {"uri": a.uri, "sha256": a.sha256, "framework": a.framework.value}
                    for a in self.artifacts
                ],
                "card": self.card.model_dump(),
                "code_commit": self.code_commit,
                "dataset_hash": self.dataset_hash,
            },
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class EvalResult(BaseModel):
    """Per-version evaluation results."""

    model_id: str
    version: str
    dataset_id: str
    metrics: dict[str, float]  # e.g. {"iou_mean": 0.91, "f1_macro": 0.88}
    per_class: dict[str, dict[str, float]] = Field(default_factory=dict)
    per_region: dict[str, dict[str, float]] = Field(default_factory=dict)
    confusion_matrix_uri: str | None = None
    reliability_diagram_uri: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.utcnow())


def sha256_file(path: Path) -> str:
    """Compute SHA-256 of a file."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


__all__ = [
    "ModelStatus",
    "ModelFramework",
    "ModelTask",
    "License",
    "BoundingBox",
    "OrientedBox",
    "Detection",
    "SegmentationMask",
    "ChangeDetectionResult",
    "ModelArtifact",
    "ModelCard",
    "ModelVersion",
    "EvalResult",
    "sha256_file",
]
