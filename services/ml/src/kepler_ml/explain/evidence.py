"""Evidence linking: tie every output to its source scenes."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class EvidenceLink:
    """A reference from a model output back to source data."""

    source_id: str  # scene ID
    source_kind: str  # scene | tile | aoi
    role: str  # input | context | t1 | t2
    weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


def build_evidence_links(
    source_scenes: list[dict[str, Any]],
    *,
    role: str = "input",
) -> list[EvidenceLink]:
    """Build evidence links for an output from a list of source scene dicts.

    Each source dict must contain at least `id`; may also contain `weight`
    and arbitrary metadata.
    """
    links: list[EvidenceLink] = []
    for src in source_scenes:
        sid = str(src.get("id") or src.get("scene_id") or "")
        if not sid:
            continue
        meta = {k: v for k, v in src.items() if k not in {"id", "scene_id", "weight"}}
        links.append(
            EvidenceLink(
                source_id=sid,
                source_kind=src.get("kind", "scene"),
                role=str(src.get("role", role)),
                weight=float(src.get("weight", 1.0)),
                metadata=meta,
            )
        )
    return links


def evidence_digest(links: list[EvidenceLink]) -> str:
    """Compute a deterministic digest of the evidence list (for STAC items)."""
    canonical = "|".join(
        f"{l.source_id}:{l.source_kind}:{l.role}:{l.weight:.6f}" for l in sorted(links, key=lambda x: x.source_id)
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


__all__ = ["EvidenceLink", "build_evidence_links", "evidence_digest"]
