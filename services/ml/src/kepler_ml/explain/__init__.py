"""Explainability: saliency, evidence linking, model cards."""

from .saliency import (
    SaliencyMethod,
    compute_saliency,
    overlay_saliency,
    SaliencyResult,
)
from .evidence import (
    EvidenceLink,
    build_evidence_links,
)

__all__ = [
    "SaliencyMethod",
    "compute_saliency",
    "overlay_saliency",
    "SaliencyResult",
    "EvidenceLink",
    "build_evidence_links",
]
