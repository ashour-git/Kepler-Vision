"""Unit tests for explainability helpers."""

from __future__ import annotations

import numpy as np
import pytest

from kepler_ml.explain.evidence import build_evidence_links, evidence_digest
from kepler_ml.explain.saliency import SaliencyMethod, compute_saliency, overlay_saliency


def test_saliency_gradient_shape() -> None:
    image = np.random.rand(6, 64, 64).astype(np.float32)
    res = compute_saliency(image, method=SaliencyMethod.GRADIENT)
    assert res.saliency.shape == (64, 64)
    assert res.saliency.min() >= 0.0
    assert res.saliency.max() <= 1.0 + 1e-6


def test_saliency_occlusion_shape() -> None:
    image = np.random.rand(3, 64, 64).astype(np.float32)
    res = compute_saliency(image, method=SaliencyMethod.OCCLUSION, occlusion_window=16, occlusion_stride=8)
    assert res.saliency.shape == (64, 64)


def test_saliency_integrated_gradients_shape() -> None:
    image = np.random.rand(3, 64, 64).astype(np.float32)
    res = compute_saliency(image, method=SaliencyMethod.INTEGRATED_GRADIENTS, steps=4, seed=0)
    assert res.saliency.shape == (64, 64)


def test_saliency_invalid_method() -> None:
    with pytest.raises(ValueError):
        compute_saliency(np.zeros((3, 8, 8)), method="not-a-method")  # type: ignore[arg-type]


def test_overlay_saliency_shape() -> None:
    image = np.random.rand(3, 32, 32).astype(np.float32)
    sal = np.random.rand(32, 32).astype(np.float32)
    out = overlay_saliency(image, sal)
    assert out.shape == (32, 32, 3)
    assert out.dtype.name == "uint8"


def test_evidence_links_build_and_digest() -> None:
    sources = [
        {"id": "scene-1", "role": "t1"},
        {"id": "scene-2", "role": "t2", "weight": 0.5},
    ]
    links = build_evidence_links(sources)
    assert len(links) == 2
    digest1 = evidence_digest(links)
    digest2 = evidence_digest(list(reversed(links)))
    assert digest1 == digest2  # digest is order-independent


def test_evidence_links_skip_missing_id() -> None:
    sources = [{"id": "scene-1"}, {"role": "context"}]
    links = build_evidence_links(sources)
    assert len(links) == 1
