"""Async HTTP client for the Triton Inference Server.

We use only the HTTP/REST endpoint for portability; production should
swap to gRPC. The client is dependency-free (httpx).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import httpx
import numpy as np


class TritonError(RuntimeError):
    """Raised when Triton returns an error."""


@dataclass(frozen=True, slots=True)
class TritonInferRequest:
    """A single inference request to Triton."""

    model_name: str
    inputs: dict[str, np.ndarray]
    outputs: tuple[str, ...] = ()
    request_id: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TritonInferResult:
    """The result of a Triton inference call."""

    model_name: str
    outputs: dict[str, np.ndarray]
    raw_response: dict[str, Any]


def _np_to_triton_input(name: str, array: np.ndarray) -> dict[str, Any]:
    """Encode a numpy array as a Triton v2 input tensor."""
    if array.dtype == np.float32:
        dtype = "FP32"
    elif array.dtype == np.float16:
        dtype = "FP16"
    elif array.dtype == np.int64:
        dtype = "INT64"
    elif array.dtype == np.int32:
        dtype = "INT32"
    elif array.dtype == np.uint8:
        dtype = "UINT8"
    elif array.dtype == np.bool_:
        dtype = "BOOL"
    else:
        raise ValueError(f"Unsupported dtype for Triton: {array.dtype}")
    return {
        "name": name,
        "shape": list(array.shape),
        "datatype": dtype,
        "parameters": {"binary_data_size": array.nbytes},
        "data": array.flatten().tolist(),
    }


def _triton_to_np(output: dict[str, Any]) -> np.ndarray:
    """Decode a Triton v2 output tensor to a numpy array."""
    raw = output.get("data") or output.get("raw") or []
    if isinstance(raw, dict):
        # Some Triton backends return a dict with binary_data or raw_data
        if "raw_data" in raw:
            arr = np.frombuffer(raw["raw_data"], dtype=_dtype_for(output.get("datatype", "FP32")))
        else:
            arr = np.asarray(raw.get("values", []), dtype=_dtype_for(output.get("datatype", "FP32")))
    else:
        arr = np.asarray(raw, dtype=_dtype_for(output.get("datatype", "FP32")))
    return arr.reshape(output.get("shape", [arr.size]))


def _dtype_for(name: str) -> np.dtype:
    return {
        "FP32": np.float32,
        "FP16": np.float16,
        "INT64": np.int64,
        "INT32": np.int32,
        "UINT8": np.uint8,
        "BOOL": np.bool_,
    }.get(name, np.float32)


class TritonClient:
    """Async client for the Triton Inference Server (HTTP/REST)."""

    def __init__(self, base_url: str = "http://localhost:8000", timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=timeout)

    async def __aenter__(self) -> "TritonClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    async def is_ready(self) -> bool:
        try:
            r = await self._client.get(f"{self.base_url}/v2/health/ready", timeout=2.0)
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    async def is_model_ready(self, model_name: str) -> bool:
        try:
            r = await self._client.get(
                f"{self.base_url}/v2/models/{model_name}/ready", timeout=2.0
            )
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    async def infer(self, req: TritonInferRequest) -> TritonInferResult:
        url = f"{self.base_url}/v2/models/{req.model_name}/infer"
        body: dict[str, Any] = {
            "inputs": [_np_to_triton_input(name, arr) for name, arr in req.inputs.items()],
        }
        if req.outputs:
            body["outputs"] = [{"name": name} for name in req.outputs]
        if req.request_id:
            body["id"] = req.request_id
        if req.parameters:
            body["parameters"] = req.parameters

        try:
            response = await self._client.post(
                url,
                content=json.dumps(body),
                headers={"Content-Type": "application/json"},
            )
        except httpx.HTTPError as exc:
            raise TritonError(f"Triton request failed: {exc}") from exc

        if response.status_code != 200:
            raise TritonError(
                f"Triton returned {response.status_code}: {response.text[:500]}"
            )

        data = response.json()
        outputs = {o["name"]: _triton_to_np(o) for o in data.get("outputs", [])}
        return TritonInferResult(
            model_name=req.model_name,
            outputs=outputs,
            raw_response=data,
        )


__all__ = [
    "TritonClient",
    "TritonInferRequest",
    "TritonInferResult",
    "TritonError",
]
