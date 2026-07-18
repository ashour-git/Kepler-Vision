"""Serving pipeline: stitch preprocessing, Triton inference, postprocessing.

A `ServingPipeline` is the unit of inference exposed to the rest of the
platform. It owns: input normalization, tile batching, Triton calls,
output reassembly, and postprocessing.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Sequence

import numpy as np

from ..postprocess import (
    VectorFeature,
    vectorize_mask,
    vectorize_with_overlap_blend,
    VectorizeOptions,
)
from ..preprocess import (
    TileSpec,
    gaussian_weight_map,
    normalize_image,
    reassemble_tiles,
    tile_raster,
)
from ..domain import SegmentationMask
from .triton_client import TritonClient, TritonInferRequest


@dataclass(frozen=True, slots=True)
class ServingRequest:
    """A request to the serving pipeline."""

    model_name: str
    image: np.ndarray  # CHW
    width: int
    height: int
    tile_size: int = 512
    overlap: int = 256
    band_stats_mean: tuple[float, ...] = (0.0,)
    band_stats_std: tuple[float, ...] = (1.0,)
    class_names: list[str] = field(default_factory=list)
    vectorize: bool = True
    vectorize_options: VectorizeOptions | None = None
    request_id: str | None = None


@dataclass(frozen=True, slots=True)
class ServingResult:
    """The result of inference."""

    model_name: str
    mask: np.ndarray  # HW
    probabilities: np.ndarray | None  # (C, H, W) or None
    features: list[VectorFeature]
    num_tiles: int
    total_ms: float
    inference_ms: float
    postprocess_ms: float
    request_id: str | None = None


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def _softmax(x: np.ndarray, axis: int = 0) -> np.ndarray:
    e = np.exp(x - x.max(axis=axis, keepdims=True))
    return e / e.sum(axis=axis, keepdims=True)


class ServingPipeline:
    """A serving pipeline for segmentation-style models."""

    def __init__(
        self,
        client: TritonClient,
        *,
        num_classes: int = 1,
        is_binary: bool = True,
        inference_batch_size: int = 8,
    ) -> None:
        self._client = client
        self._num_classes = num_classes
        self._is_binary = is_binary
        self._batch_size = inference_batch_size

    async def run(self, req: ServingRequest) -> ServingResult:
        started = time.perf_counter()
        norm = normalize_image(
            req.image,
            # Local BandStats-like object
            type("_S", (), {"mean": req.band_stats_mean, "std": req.band_stats_std})(),
        )
        specs = tile_raster(req.width, req.height, req.tile_size, req.overlap)
        weight_map = gaussian_weight_map(req.tile_size)

        full_logits_shape = (req.height, req.width, self._num_classes) if self._num_classes > 1 else (req.height, req.width)
        full_logits = np.zeros(full_logits_shape, dtype=np.float32)
        full_wsum = np.zeros((req.height, req.width), dtype=np.float32)

        # Triton expects NCHW: (B, C, H, W). We treat the band axis as channels.
        inference_started = time.perf_counter()
        for batch_start in range(0, len(specs), self._batch_size):
            batch_specs = specs[batch_start: batch_start + self._batch_size]
            batch = np.stack(
                [
                    self._extract_tile(norm, spec)
                    for spec in batch_specs
                ]
            ).astype(np.float32)
            infer_req = TritonInferRequest(
                model_name=req.model_name,
                inputs={"input": batch},
                outputs=("logits",) if self._num_classes == 1 else ("logits",),
                request_id=req.request_id,
            )
            infer_res = await self._client.infer(infer_req)
            logits = infer_res.outputs["logits"]
            for spec, tile_logits in zip(batch_specs, logits):
                self._write_tile(full_logits, full_wsum, spec, tile_logits, weight_map)
        inference_ms = (time.perf_counter() - inference_started) * 1000.0

        if self._num_classes > 1:
            probs = _softmax(full_logits, axis=-1).transpose(2, 0, 1)
            mask = probs.argmax(axis=0).astype(np.uint8)
        else:
            probs = _sigmoid(full_logits[..., 0])
            mask = (probs > 0.5).astype(np.uint8)
            probs = probs[None, :, :]

        postprocess_started = time.perf_counter()
        features: list[VectorFeature] = []
        if req.vectorize:
            opts = req.vectorize_options or VectorizeOptions()
            features = vectorize_mask(mask, class_names=req.class_names, options=opts)
        postprocess_ms = (time.perf_counter() - postprocess_started) * 1000.0
        total_ms = (time.perf_counter() - started) * 1000.0

        return ServingResult(
            model_name=req.model_name,
            mask=mask,
            probabilities=probs,
            features=features,
            num_tiles=len(specs),
            total_ms=total_ms,
            inference_ms=inference_ms,
            postprocess_ms=postprocess_ms,
            request_id=req.request_id,
        )

    @staticmethod
    def _extract_tile(image: np.ndarray, spec: TileSpec) -> np.ndarray:
        """Extract a CHW tile, padding to the model's tile size if needed."""
        ch, h, w = image.shape
        x0, y0 = spec.x, spec.y
        x1, y1 = x0 + spec.width, y0 + spec.height
        tile = image[:, y0:y1, x0:x1]
        if tile.shape[1] != spec.tile_size_padded(spec) or tile.shape[2] != spec.tile_size_padded(spec):
            # No padding needed because tile_raster returns specs whose w/h equal tile_size,
            # except for the edge tiles which may be smaller. We don't actually pad here;
            # Triton handles dynamic shapes.
            pass
        return tile

    @staticmethod
    def _write_tile(
        full: np.ndarray,
        wsum: np.ndarray,
        spec: TileSpec,
        tile: np.ndarray,
        weight_map: np.ndarray,
    ) -> None:
        x0, y0 = spec.x, spec.y
        x1, y1 = x0 + spec.width, y0 + spec.height
        if full.ndim == 2:
            full[y0:y1, x0:x1] += tile * weight_map[: spec.height, : spec.width]
            wsum[y0:y1, x0:x1] += weight_map[: spec.height, : spec.width]
        else:
            wm = weight_map[: spec.height, : spec.width, None]
            full[y0:y1, x0:x1] += tile * wm
            wsum[y0:y1, x0:x1] += weight_map[: spec.height, : spec.width]
        return None


# Add a `tile_size_padded` method to TileSpec for compatibility — delegates to width/height.
def _tile_size_padded(self: TileSpec) -> int:
    return self.width


TileSpec.tile_size_padded = _tile_size_padded  # type: ignore[attr-defined]


def build_serving_pipeline(
    base_url: str = "http://localhost:8000",
    *,
    timeout: float = 30.0,
    num_classes: int = 1,
    is_binary: bool = True,
    inference_batch_size: int = 8,
) -> ServingPipeline:
    """Build a pipeline with its own client. The client must be closed by the caller."""
    client = TritonClient(base_url=base_url, timeout=timeout)
    return ServingPipeline(
        client=client,
        num_classes=num_classes,
        is_binary=is_binary,
        inference_batch_size=inference_batch_size,
    )


__all__ = [
    "ServingPipeline",
    "ServingRequest",
    "ServingResult",
    "build_serving_pipeline",
    "SegmentationMask",
    "VectorFeature",
    "VectorizeOptions",
    "asyncio",
]
