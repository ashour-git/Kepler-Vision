"""Triton config.pbtxt generators.

We build config files for the standard 6 MVP models. Each config declares
the input/output tensors, the framework (onnxruntime), and the optimization
profile for dynamic batch sizes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TensorSpec:
    """A Triton input/output tensor spec."""

    name: str
    shape: tuple[int, ...]  # Use -1 for dynamic
    data_type: str  # TYPE_FP32, TYPE_FP16, TYPE_UINT8, etc.
    format: str = "FORMAT_NCHW"  # or FORMAT_HWC, FORMAT_NONE

    def to_pbtxt_lines(self, kind: str) -> list[str]:
        shape = "[" + ",".join(str(d) for d in self.shape) + "]"
        return [
            f'{kind} {{',
            f'  name: "{self.name}"',
            f'  data_type: {self.data_type}',
            f'  format: {self.format}',
            f'  dims: {shape}',
            "}",
        ]


@dataclass(frozen=True, slots=True)
class TritonConfig:
    """A Triton model config builder."""

    name: str
    platform: str
    max_batch_size: int
    inputs: tuple[TensorSpec, ...]
    outputs: tuple[TensorSpec, ...]
    dynamic_batching: bool = True
    preferred_batch_size: tuple[int, ...] = (1, 2, 4, 8, 16, 32)
    max_queue_delay_microseconds: int = 5000
    instance_group: tuple[dict[str, Any], ...] = ({"count": 1, "kind": "KIND_GPU"},)
    optimization: dict[str, Any] | None = None
    version_policy: tuple[dict[str, Any], ...] = ({"latest": {"num_versions": 1}},)

    def to_pbtxt(self) -> str:
        lines: list[str] = [
            f'name: "{self.name}"',
            f'platform: "{self.platform}"',
            f"max_batch_size: {self.max_batch_size}",
        ]
        lines.extend('  ' + l for ts in self.inputs for l in ts.to_pbtxt_lines("input"))
        lines.extend('  ' + l for ts in self.outputs for l in ts.to_pbtxt_lines("output"))
        if self.dynamic_batching:
            lines.extend(
                [
                    "dynamic_batching {",
                    f"  preferred_batch_size: [{', '.join(str(s) for s in self.preferred_batch_size)}]",
                    f"  max_queue_delay_microseconds: {self.max_queue_delay_microseconds}",
                    "}",
                ]
            )
        for ig in self.instance_group:
            count = ig.get("count", 1)
            kind = ig.get("kind", "KIND_GPU")
            lines.append("instance_group [")
            lines.append("  {")
            lines.append(f"    count: {count}")
            lines.append(f"    kind: {kind}")
            lines.append("  }")
            lines.append("]")
        if self.optimization:
            lines.append("optimization {")
            for k, v in self.optimization.items():
                if isinstance(v, list):
                    lines.append(f"  {k}: [{', '.join(str(x) for x in v)}]")
                else:
                    lines.append(f"  {k}: {v}")
            lines.append("}")
        for vp in self.version_policy:
            lines.append("version_policy: { latest: { num_versions: 1 } }")
        return "\n".join(lines) + "\n"


# --- Common tensor spec shorthands ------------------------------------------


FP32_NCHW_INPUT = lambda name, h, w: TensorSpec(  # noqa: E731
    name=name, shape=(-1, -1, -1, h, w), data_type="TYPE_FP32", format="FORMAT_NCHW"
)
FP32_NCHW_OUTPUT = lambda name, h, w: TensorSpec(  # noqa: E731
    name=name, shape=(-1, -1, -1, h, w), data_type="TYPE_FP32", format="FORMAT_NCHW"
)
FP32_SCALAR = lambda name: TensorSpec(name=name, shape=(-1,), data_type="TYPE_FP32", format="FORMAT_NONE")  # noqa: E731
INT64_SCALAR = lambda name: TensorSpec(name=name, shape=(-1,), data_type="TYPE_INT64", format="FORMAT_NONE")  # noqa: E731


# --- 6 MVP model configs ----------------------------------------------------


def build_classification_config(name: str, height: int, width: int, num_classes: int) -> TritonConfig:
    """Scene-level classification (e.g. EuroSAT-style tile classifier)."""
    return TritonConfig(
        name=name,
        platform="onnxruntime_onnx",
        max_batch_size=64,
        inputs=(FP32_NCHW_INPUT("input", height, width),),
        outputs=(TensorSpec(name="logits", shape=(-1, num_classes), data_type="TYPE_FP32", format="FORMAT_NONE"),),
    )


def build_segmentation_config(name: str, height: int, width: int, num_classes: int) -> TritonConfig:
    """Segmentation output as (B, num_classes, H, W)."""
    return TritonConfig(
        name=name,
        platform="onnxruntime_onnx",
        max_batch_size=16,
        inputs=(FP32_NCHW_INPUT("input", height, width),),
        outputs=(FP32_NCHW_OUTPUT("logits", height, width),) if num_classes == 1
        else (
            TensorSpec(
                name="logits",
                shape=(-1, num_classes, -1, -1),
                data_type="TYPE_FP32",
                format="FORMAT_NCHW",
            ),
        ),
    )


def build_detection_config(name: str, height: int, width: int) -> TritonConfig:
    """Object detection output as (B, N, 6) — yxyx, score, class."""
    return TritonConfig(
        name=name,
        platform="onnxruntime_onnx",
        max_batch_size=8,
        inputs=(FP32_NCHW_INPUT("input", height, width),),
        outputs=(
            TensorSpec(
                name="boxes",
                shape=(-1, -1, 6),
                data_type="TYPE_FP32",
                format="FORMAT_NONE",
            ),
            TensorSpec(
                name="scores",
                shape=(-1, -1),
                data_type="TYPE_FP32",
                format="FORMAT_NONE",
            ),
        ),
    )


# --- CLI helper to dump a config --------------------------------------------


def write_config(path: str | "Path", config: TritonConfig) -> None:
    """Write a Triton config.pbtxt to disk."""
    from pathlib import Path

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(config.to_pbtxt(), encoding="utf-8")


__all__ = [
    "TensorSpec",
    "TritonConfig",
    "build_classification_config",
    "build_segmentation_config",
    "build_detection_config",
    "write_config",
]
