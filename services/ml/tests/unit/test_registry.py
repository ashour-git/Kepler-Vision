"""Unit tests for the model registry."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kepler_ml.domain import (
    License,
    ModelCard,
    ModelFramework,
    ModelStatus,
    ModelTask,
    ModelVersion,
)
from kepler_ml.registry import (
    ModelAlreadyExistsError,
    ModelNotFoundError,
    ModelRegistry,
)


def _make_version(name: str = "def_test", version: str = "0.1.0") -> ModelVersion:
    return ModelVersion(
        model_id="def_test",
        name=name,
        task=ModelTask.CHANGE_DETECTION,
        version=version,
        framework=ModelFramework.ONNX,
        card=ModelCard(intended_use="internal", license=License.PROPRIETARY),
    )


def test_register_and_retrieve(tmp_path: Path) -> None:
    reg = ModelRegistry(root=tmp_path)
    v = _make_version()
    reg.register_version(v)
    assert reg.has_model("def_test")
    assert reg.has_version("def_test", "0.1.0")
    out = reg.get_version("def_test", "0.1.0")
    assert out.model_id == "def_test"
    assert out.task == ModelTask.CHANGE_DETECTION


def test_duplicate_registration_raises(tmp_path: Path) -> None:
    reg = ModelRegistry(root=tmp_path)
    reg.register_version(_make_version())
    with pytest.raises(ModelAlreadyExistsError):
        reg.register_version(_make_version())


def test_get_latest_ga(tmp_path: Path) -> None:
    reg = ModelRegistry(root=tmp_path)
    reg.register_version(_make_version(version="0.1.0"))
    v2 = _make_version(version="0.2.0")
    v2.status = ModelStatus.GA
    reg.register_version(v2)
    latest = reg.get_latest_ga("def_test")
    assert latest.version == "0.2.0"


def test_set_status_promotes_to_ga(tmp_path: Path) -> None:
    reg = ModelRegistry(root=tmp_path)
    reg.register_version(_make_version(version="0.1.0"))
    reg.set_status("def_test", "0.1.0", ModelStatus.GA)
    out = reg.get_latest_ga("def_test")
    assert out.version == "0.1.0"
    assert out.status == ModelStatus.GA


def test_get_nonexistent_raises(tmp_path: Path) -> None:
    reg = ModelRegistry(root=tmp_path)
    with pytest.raises(ModelNotFoundError):
        reg.get_version("missing", "0.1.0")


def test_search_by_task(tmp_path: Path) -> None:
    reg = ModelRegistry(root=tmp_path)
    reg.register_version(_make_version())
    water = _make_version()
    water.model_id = "water"
    water.task = ModelTask.WATER_DETECTION
    water.version = "0.1.0"
    reg.register_version(water)
    results = reg.search(task=ModelTask.WATER_DETECTION)
    assert len(results) == 1
    assert results[0].model_id == "water"


def test_content_hash_is_deterministic() -> None:
    from datetime import datetime
    from kepler_ml.domain import License, ModelCard, ModelFramework, ModelTask, ModelVersion

    fixed_time = datetime(2026, 1, 1, 0, 0, 0)
    card1 = ModelCard(intended_use="internal", license=License.PROPRIETARY, created_at=fixed_time)
    v1 = ModelVersion(
        model_id="def_test",
        name="def_test",
        task=ModelTask.CHANGE_DETECTION,
        version="0.1.0",
        framework=ModelFramework.ONNX,
        card=card1,
        created_at=fixed_time,
        released_at=fixed_time,
    )
    card2 = ModelCard(intended_use="internal", license=License.PROPRIETARY, created_at=fixed_time)
    v2 = ModelVersion(
        model_id="def_test",
        name="def_test",
        task=ModelTask.CHANGE_DETECTION,
        version="0.1.0",
        framework=ModelFramework.ONNX,
        card=card2,
        created_at=fixed_time,
        released_at=fixed_time,
    )
    assert v1.content_hash == v2.content_hash
    v2.card.intended_use = "different"
    assert v1.content_hash != v2.content_hash


def test_artifact_round_trip(tmp_path: Path) -> None:
    reg = ModelRegistry(root=tmp_path)
    artifact_path = tmp_path / "model.onnx"
    artifact_path.write_bytes(b"fake-onnx")
    v = _make_version()
    reg.register_version(v, artifact_paths=[artifact_path])
    artifacts = list(reg.iter_artifacts("def_test", "0.1.0"))
    assert any(p.name == "model.onnx" for p in artifacts)
