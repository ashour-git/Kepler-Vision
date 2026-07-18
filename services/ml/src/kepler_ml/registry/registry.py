"""Model registry.

The registry manages content-addressed model versions. It is intentionally
minimal: a JSON index per model plus artifact files. Production
deployments back this with object storage; the default path is a local
directory for development.
"""

from __future__ import annotations

import json
import shutil
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator

from ..domain import (
    EvalResult,
    License,
    ModelArtifact,
    ModelCard,
    ModelFramework,
    ModelStatus,
    ModelTask,
    ModelVersion,
)


class ModelNotFoundError(LookupError):
    """Raised when a model or version does not exist."""


class ModelAlreadyExistsError(ValueError):
    """Raised when registering a duplicate (model_id, version)."""


@dataclass
class ModelRegistry:
    """A file-backed model registry.

    Layout on disk:
        <root>/<model_id>/
            meta.json                 # latest pointer + history
            versions/<version>/
                meta.json             # ModelVersion
                card.json             # ModelCard
                eval.json             # EvalResult (optional)
                artifacts/<sha256>    # binary artifacts
    """

    root: Path

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    # ------------------------------------------------------------------ CRUD

    def _model_dir(self, model_id: str) -> Path:
        return self.root / model_id

    def _version_dir(self, model_id: str, version: str) -> Path:
        return self._model_dir(model_id) / "versions" / version

    def _read_json(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_json(self, path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    def has_model(self, model_id: str) -> bool:
        return (self._model_dir(model_id) / "meta.json").exists()

    def has_version(self, model_id: str, version: str) -> bool:
        return (self._version_dir(model_id, version) / "meta.json").exists()

    def register_version(
        self,
        model_version: ModelVersion,
        artifact_paths: list[Path] | None = None,
    ) -> Path:
        """Register `model_version` and (optionally) copy artifacts into the registry."""
        with self._lock:
            if not self.has_model(model_version.model_id):
                self._model_dir(model_version.model_id).mkdir(parents=True, exist_ok=True)
            if self.has_version(model_version.model_id, model_version.version):
                raise ModelAlreadyExistsError(
                    f"Version {model_version.version} already exists for model {model_version.model_id}"
                )

            vdir = self._version_dir(model_version.model_id, model_version.version)
            vdir.mkdir(parents=True, exist_ok=True)

            self._write_json(vdir / "meta.json", model_version.model_dump())
            self._write_json(vdir / "card.json", model_version.card.model_dump())

            if artifact_paths:
                adir = vdir / "artifacts"
                adir.mkdir(parents=True, exist_ok=True)
                for src in artifact_paths:
                    src = Path(src)
                    if not src.exists():
                        raise FileNotFoundError(src)
                    shutil.copy2(src, adir / src.name)

            # Update the model-level meta
            meta_path = self._model_dir(model_version.model_id) / "meta.json"
            if meta_path.exists():
                meta = self._read_json(meta_path)
            else:
                meta = {
                    "model_id": model_version.model_id,
                    "task": model_version.task.value,
                    "framework": model_version.framework.value,
                    "versions": [],
                    "latest_ga": None,
                }
            meta.setdefault("versions", []).append(
                {
                    "version": model_version.version,
                    "status": model_version.status.value,
                    "released_at": model_version.released_at.isoformat(),
                    "content_hash": model_version.content_hash,
                }
            )
            if model_version.status == ModelStatus.GA:
                meta["latest_ga"] = model_version.version
            self._write_json(meta_path, meta)
            return vdir

    def attach_eval(self, model_id: str, version: str, eval_result: EvalResult) -> None:
        """Attach (or replace) eval results for a model version."""
        with self._lock:
            if not self.has_version(model_id, version):
                raise ModelNotFoundError(f"{model_id}:{version}")
            path = self._version_dir(model_id, version) / "eval.json"
            self._write_json(path, eval_result.model_dump())

    def set_status(self, model_id: str, version: str, status: ModelStatus) -> None:
        """Update the status of a version."""
        with self._lock:
            if not self.has_version(model_id, version):
                raise ModelNotFoundError(f"{model_id}:{version}")
            meta_path = self._version_dir(model_id, version) / "meta.json"
            data = self._read_json(meta_path)
            data["status"] = status.value
            self._write_json(meta_path, data)
            # Update latest pointer
            model_meta_path = self._model_dir(model_id) / "meta.json"
            if model_meta_path.exists():
                mm = self._read_json(model_meta_path)
                for v in mm.get("versions", []):
                    if v.get("version") == version:
                        v["status"] = status.value
                if status == ModelStatus.GA:
                    mm["latest_ga"] = version
                self._write_json(model_meta_path, mm)

    def get_version(self, model_id: str, version: str) -> ModelVersion:
        with self._lock:
            path = self._version_dir(model_id, version) / "meta.json"
            if not path.exists():
                raise ModelNotFoundError(f"{model_id}:{version}")
            data = self._read_json(path)
            return ModelVersion.model_validate(data)

    def get_latest_ga(self, model_id: str) -> ModelVersion:
        with self._lock:
            mm_path = self._model_dir(model_id) / "meta.json"
            if not mm_path.exists():
                raise ModelNotFoundError(model_id)
            mm = self._read_json(mm_path)
            latest = mm.get("latest_ga")
            if not latest:
                raise ModelNotFoundError(f"No GA version for {model_id}")
            return self.get_version(model_id, latest)

    def list_models(self) -> list[dict]:
        with self._lock:
            out: list[dict] = []
            for p in sorted(self.root.iterdir()):
                if p.is_dir() and (p / "meta.json").exists():
                    out.append(self._read_json(p / "meta.json"))
            return out

    def list_versions(self, model_id: str) -> list[dict]:
        with self._lock:
            mm_path = self._model_dir(model_id) / "meta.json"
            if not mm_path.exists():
                raise ModelNotFoundError(model_id)
            return list(self._read_json(mm_path).get("versions", []))

    def iter_artifacts(self, model_id: str, version: str) -> Iterator[Path]:
        adir = self._version_dir(model_id, version) / "artifacts"
        if not adir.exists():
            return iter([])
        return iter(sorted(adir.iterdir()))

    # -------------------------------------------------------------- search

    def search(
        self,
        task: ModelTask | None = None,
        framework: ModelFramework | None = None,
        status: ModelStatus | None = None,
    ) -> list[ModelVersion]:
        """Find model versions matching the given filters."""
        out: list[ModelVersion] = []
        for p in sorted(self.root.iterdir()):
            if not p.is_dir() or not (p / "meta.json").exists():
                continue
            versions_dir = p / "versions"
            if not versions_dir.exists():
                continue
            for vd in sorted(versions_dir.iterdir()):
                if not (vd / "meta.json").exists():
                    continue
                data = self._read_json(vd / "meta.json")
                mv = ModelVersion.model_validate(data)
                if task is not None and mv.task != task:
                    continue
                if framework is not None and mv.framework != framework:
                    continue
                if status is not None and mv.status != status:
                    continue
                out.append(mv)
        return out


_default_registry: ModelRegistry | None = None


def get_default_registry() -> ModelRegistry:
    """Return the process-wide default registry (root: ./models)."""
    global _default_registry
    if _default_registry is None:
        _default_registry = ModelRegistry(root=Path("./models"))
    return _default_registry


def reset_default_registry() -> None:
    """Reset the default registry (tests)."""
    global _default_registry
    _default_registry = None


__all__ = [
    "ModelRegistry",
    "ModelNotFoundError",
    "ModelAlreadyExistsError",
    "get_default_registry",
    "reset_default_registry",
    "License",
    "ModelCard",
    "ModelArtifact",
    "ModelFramework",
    "ModelStatus",
    "ModelTask",
    "ModelVersion",
    "EvalResult",
    "datetime",
]
