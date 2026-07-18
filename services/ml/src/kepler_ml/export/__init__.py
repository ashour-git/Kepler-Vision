"""ONNX and TensorRT export with parity validation.

The export pipeline is GPU-agnostic: ONNX export is pure-Python, and
TensorRT export is wrapped in a try/except so the import doesn't fail
on CPU-only machines.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np

from ..domain import ModelArtifact, ModelFramework


# --- Parity test harness ----------------------------------------------------


@dataclass(frozen=True, slots=True)
class ParityResult:
    """The result of a parity check between two inference runs."""

    pytorch_outputs: dict[str, np.ndarray]
    onnx_outputs: dict[str, np.ndarray]
    max_abs_diff: float
    max_rel_diff: float
    passed: bool
    tolerance_atol: float
    tolerance_rtol: float
    notes: str = ""


def _max_diff(
    a: np.ndarray, b: np.ndarray, atol: float, rtol: float
) -> tuple[float, float, bool]:
    a32 = a.astype(np.float32)
    b32 = b.astype(np.float32)
    diff = np.abs(a32 - b32)
    abs_tol = atol + rtol * np.abs(b32)
    passed = bool(np.all(diff <= abs_tol))
    return float(diff.max()) if diff.size else 0.0, float(diff.max() / (np.abs(b32).max() + 1e-12)) if diff.size else 0.0, passed


def compare_outputs(
    a: dict[str, np.ndarray],
    b: dict[str, np.ndarray],
    *,
    atol: float = 1e-3,
    rtol: float = 1e-3,
) -> ParityResult:
    """Compare two sets of named outputs."""
    if set(a) != set(b):
        return ParityResult(
            pytorch_outputs=a,
            onnx_outputs=b,
            max_abs_diff=float("inf"),
            max_rel_diff=float("inf"),
            passed=False,
            tolerance_atol=atol,
            tolerance_rtol=rtol,
            notes=f"Output sets differ: {set(a) ^ set(b)}",
        )
    overall_pass = True
    worst_abs = 0.0
    worst_rel = 0.0
    for name in a:
        a_diff, a_rel, ok = _max_diff(a[name], b[name], atol, rtol)
        worst_abs = max(worst_abs, a_diff)
        worst_rel = max(worst_rel, a_rel)
        overall_pass = overall_pass and ok
    return ParityResult(
        pytorch_outputs=a,
        onnx_outputs=b,
        max_abs_diff=worst_abs,
        max_rel_diff=worst_rel,
        passed=overall_pass,
        tolerance_atol=atol,
        tolerance_rtol=rtol,
    )


# --- ONNX export ------------------------------------------------------------


@dataclass
class OnnxExportSpec:
    """Spec for exporting a PyTorch model to ONNX."""

    model: Any  # torch.nn.Module (kept untyped to avoid hard torch dep)
    sample_input: np.ndarray
    input_names: tuple[str, ...] = ("input",)
    output_names: tuple[str, ...] = ("output",)
    dynamic_axes: dict[str, dict[int, str]] = field(
        default_factory=lambda: {"input": {0: "batch", 2: "height", 3: "width"}, "output": {0: "batch"}}
    )
    opset: int = 19
    output_path: Path = Path("model.onnx")
    simplify: bool = True


def export_onnx(spec: OnnxExportSpec) -> tuple[Path, dict[str, Any]]:
    """Export a PyTorch model to ONNX. Returns (path, metadata).

    This requires torch. We import it lazily so the module is importable
    on CPU-only machines.
    """
    try:
        import torch
    except ImportError as exc:
        raise ImportError("PyTorch is required for ONNX export. Install torch.") from exc

    spec.output_path = Path(spec.output_path)
    spec.output_path.parent.mkdir(parents=True, exist_ok=True)
    model = spec.model.eval()
    sample = torch.from_numpy(np.ascontiguousarray(spec.sample_input)).float()
    started = time.perf_counter()

    with torch.no_grad():
        torch.onnx.export(
            model,
            sample,
            str(spec.output_path),
            input_names=list(spec.input_names),
            output_names=list(spec.output_names),
            dynamic_axes={k: dict(v) for k, v in spec.dynamic_axes.items()},
            opset_version=spec.opset,
            do_constant_folding=True,
        )

    elapsed = time.perf_counter() - started
    size = spec.output_path.stat().st_size
    sha256 = hashlib.sha256(spec.output_path.read_bytes()).hexdigest()

    simplified = False
    if spec.simplify:
        try:
            import onnxslim  # type: ignore[import-untyped]

            simplified_path = spec.output_path.with_suffix(".simplified.onnx")
            onnxslim.slim(str(spec.output_path), str(simplified_path))
            if simplified_path.exists() and simplified_path.stat().st_size > 0:
                shutil.move(str(simplified_path), str(spec.output_path))
                simplified = True
        except Exception:  # noqa: BLE001 - simplification is best-effort
            pass

    metadata = {
        "path": str(spec.output_path),
        "size_bytes": spec.output_path.stat().st_size,
        "sha256": hashlib.sha256(spec.output_path.read_bytes()).hexdigest(),
        "simplified": simplified,
        "elapsed_seconds": elapsed,
        "previous_sha256": sha256,
        "opset": spec.opset,
    }
    return spec.output_path, metadata


def validate_onnx(
    onnx_path: Path,
    sample_input: np.ndarray,
    *,
    atol: float = 1e-3,
    rtol: float = 1e-3,
) -> ParityResult:
    """Validate an ONNX model: load + run on the sample input. Returns ParityResult with only the ONNX side populated."""
    try:
        import onnxruntime as ort
    except ImportError as exc:
        raise ImportError("onnxruntime is required for ONNX validation.") from exc

    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    feeds = {session.get_inputs()[0].name: sample_input.astype(np.float32)}
    outputs = {o.name: out for o, out in zip(session.get_outputs(), session.run(None, feeds))}
    return ParityResult(
        pytorch_outputs={},
        onnx_outputs=outputs,
        max_abs_diff=0.0,
        max_rel_diff=0.0,
        passed=True,
        tolerance_atol=atol,
        tolerance_rtol=rtol,
        notes="onnx-only validation",
    )


# --- TensorRT export --------------------------------------------------------


@dataclass
class TrtExportSpec:
    """Spec for compiling an ONNX model to a TensorRT engine."""

    onnx_path: Path
    output_path: Path = Path("model.trt")
    fp16: bool = True
    int8: bool = False
    calibration_cache: Path | None = None
    workspace_gb: int = 4
    dynamic_shapes: dict[str, dict[str, tuple[int, int, int]]] | None = None
    # name -> {"min": (B,H,W,C), "opt": ..., "max": ...}
    trtexec_path: str = "trtexec"


def is_trtexec_available(trtexec_path: str = "trtexec") -> bool:
    """Return True if `trtexec` is on PATH (or at `trtexec_path`)."""
    from shutil import which

    return which(trtexec_path) is not None


def export_tensorrt(spec: TrtExportSpec) -> tuple[Path, dict[str, Any]]:
    """Build a TensorRT engine from an ONNX model using `trtexec`."""
    if not is_trtexec_available(spec.trtexec_path):
        raise RuntimeError("trtexec is not on PATH; install TensorRT or set trt_export_spec.trtexec_path")

    spec.output_path = Path(spec.output_path)
    spec.output_path.parent.mkdir(parents=True, exist_ok=True)
    spec.onnx_path = Path(spec.onnx_path)
    if not spec.onnx_path.exists():
        raise FileNotFoundError(spec.onnx_path)

    cmd: list[str] = [
        spec.trtexec_path,
        f"--onnx={spec.onnx_path}",
        f"--saveEngine={spec.output_path}",
        f"--workspace={spec.workspace_gb * 1024}",
    ]
    if spec.fp16:
        cmd.append("--fp16")
    if spec.int8:
        cmd.append("--int8")
        if spec.calibration_cache is not None:
            cmd.append(f"--calib={spec.calibration_cache}")
    if spec.dynamic_shapes:
        for name, profile in spec.dynamic_shapes.items():
            for k, shape in profile.items():
                cmd.append(f"--{k}={name}:{','.join(str(d) for d in shape)}")

    started = time.perf_counter()
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    elapsed = time.perf_counter() - started

    if result.returncode != 0:
        raise RuntimeError(f"trtexec failed: {result.stderr}\nstdout: {result.stdout}")

    if not spec.output_path.exists():
        raise RuntimeError("trtexec did not produce an engine file")

    return spec.output_path, {
        "path": str(spec.output_path),
        "size_bytes": spec.output_path.stat().st_size,
        "sha256": hashlib.sha256(spec.output_path.read_bytes()).hexdigest(),
        "elapsed_seconds": elapsed,
        "fp16": spec.fp16,
        "int8": spec.int8,
    }


# --- Artifact helpers --------------------------------------------------------


def build_artifact(metadata: dict[str, Any], framework: ModelFramework) -> ModelArtifact:
    """Build a `ModelArtifact` from export metadata."""
    return ModelArtifact(
        uri=metadata["path"],
        sha256=metadata["sha256"],
        size_bytes=metadata["size_bytes"],
        framework=framework,
        precision=(
            "int8" if metadata.get("int8") else "fp16" if metadata.get("fp16") else "fp32"
        ),
    )


__all__ = [
    "ParityResult",
    "compare_outputs",
    "OnnxExportSpec",
    "export_onnx",
    "validate_onnx",
    "TrtExportSpec",
    "is_trtexec_available",
    "export_tensorrt",
    "build_artifact",
    "json",
]
