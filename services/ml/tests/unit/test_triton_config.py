"""Unit tests for Triton config generation."""

from __future__ import annotations

from pathlib import Path

from kepler_ml.registry import (
    TritonConfig,
    build_classification_config,
    build_detection_config,
    build_segmentation_config,
    write_config,
)


def test_classification_config_format() -> None:
    cfg = build_classification_config("eurosat", height=64, width=64, num_classes=10)
    assert cfg.name == "eurosat"
    text = cfg.to_pbtxt()
    assert 'name: "eurosat"' in text
    assert "input" in text
    assert "output" in text
    assert "dynamic_batching" in text


def test_segmentation_config_binary() -> None:
    cfg = build_segmentation_config("cloud_mask", height=256, width=256, num_classes=1)
    text = cfg.to_pbtxt()
    assert "logits" in text
    assert "max_batch_size: 16" in text


def test_segmentation_config_multiclass() -> None:
    cfg = build_segmentation_config("vegetation", height=256, width=256, num_classes=5)
    text = cfg.to_pbtxt()
    assert "logits" in text


def test_detection_config_format() -> None:
    cfg = build_detection_config("ship_detect", height=256, width=256)
    text = cfg.to_pbtxt()
    assert "boxes" in text
    assert "scores" in text


def test_write_config_to_disk(tmp_path: Path) -> None:
    cfg = build_classification_config("eurosat", height=64, width=64, num_classes=10)
    target = tmp_path / "eurosat" / "config.pbtxt"
    write_config(target, cfg)
    assert target.exists()
    text = target.read_text(encoding="utf-8")
    assert "eurosat" in text


def test_triton_config_disables_dynamic_batching() -> None:
    cfg = TritonConfig(
        name="x",
        platform="onnxruntime_onnx",
        max_batch_size=1,
        inputs=(),
        outputs=(),
        dynamic_batching=False,
    )
    text = cfg.to_pbtxt()
    assert "dynamic_batching" not in text
