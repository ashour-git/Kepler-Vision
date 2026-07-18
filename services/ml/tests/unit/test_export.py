"""Unit tests for ONNX export and parity validation."""

from __future__ import annotations

import numpy as np
import pytest

from kepler_ml.export import (
    OnnxExportSpec,
    ParityResult,
    build_artifact,
    compare_outputs,
    export_onnx,
    validate_onnx,
)


def test_compare_outputs_match() -> None:
    a = {"logits": np.array([[1.0, 2.0, 3.0]], dtype=np.float32)}
    b = {"logits": np.array([[1.0, 2.0, 3.0]], dtype=np.float32)}
    res: ParityResult = compare_outputs(a, b)
    assert res.passed is True
    assert res.max_abs_diff == 0.0


def test_compare_outputs_mismatch_above_tolerance() -> None:
    a = {"logits": np.array([[1.0]], dtype=np.float32)}
    b = {"logits": np.array([[2.0]], dtype=np.float32)}
    res = compare_outputs(a, b)
    assert res.passed is False
    assert res.max_abs_diff == pytest.approx(1.0)


def test_compare_outputs_different_keys() -> None:
    a = {"x": np.array([1.0])}
    b = {"y": np.array([1.0])}
    res = compare_outputs(a, b)
    assert res.passed is False
    assert "differ" in res.notes


def test_validate_onnx_missing_input(tmp_path) -> None:
    """validate_onnx should produce a parity result even without PyTorch."""
    sample = np.random.rand(1, 3, 32, 32).astype(np.float32)
    # We can't easily create an ONNX file without torch, so we test the
    # error path on a nonexistent file.
    with pytest.raises(Exception):
        validate_onnx(tmp_path / "missing.onnx", sample)


def test_build_artifact_metadata() -> None:
    metadata = {"path": "model.trt", "size_bytes": 1024, "sha256": "0" * 64, "fp16": True, "int8": False}
    from kepler_ml.domain import ModelFramework

    a = build_artifact(metadata, ModelFramework.TENSORRT)
    assert a.uri == "model.trt"
    assert a.precision == "fp16"
    assert a.framework == ModelFramework.TENSORRT


def test_export_onnx_requires_torch(tmp_path, monkeypatch) -> None:
    """When torch is unavailable, export_onnx raises a clear error."""
    import sys

    monkeypatch.setitem(sys.modules, "torch", None)
    spec = OnnxExportSpec(model=None, sample_input=np.zeros((1, 3, 32, 32)), output_path=tmp_path / "x.onnx")
    with pytest.raises(ImportError):
        export_onnx(spec)
