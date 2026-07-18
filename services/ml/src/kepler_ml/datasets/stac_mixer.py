"""STAC item mixer: build a tile dataset from STAC search results."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from ..preprocess.tiling import TileSpec, tile_raster


@dataclass(frozen=True, slots=True)
class STACItem:
    """A simplified STAC item (for type-hinting)."""

    id: str
    geometry: dict[str, Any]  # GeoJSON geometry
    properties: dict[str, Any] = field(default_factory=dict)
    assets: dict[str, Any] = field(default_factory=dict)
    bbox: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    datetime: str | None = None
    collection: str | None = None


def fetch_stac_items(
    catalog_url: str,
    *,
    collections: Sequence[str] | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    datetime_range: str | None = None,
    limit: int = 100,
    timeout: float = 30.0,
) -> list[STACItem]:
    """Fetch STAC items from a catalog.

    This is a thin async wrapper around the STAC API. For MVP we return
    an empty list on error and log a warning; production code should
    raise. We avoid a hard dependency on a STAC client library.
    """
    try:
        import httpx
    except ImportError as exc:
        raise ImportError("httpx is required for STAC fetching.") from exc

    url = f"{catalog_url.rstrip('/')}/search"
    body: dict[str, Any] = {"limit": limit}
    if collections:
        body["collections"] = list(collections)
    if bbox:
        body["bbox"] = list(bbox)
    if datetime_range:
        body["datetime"] = datetime_range

    items: list[STACItem] = []
    with httpx.Client(timeout=timeout) as client:
        r = client.post(url, json=body)
        if r.status_code != 200:
            return items
        data = r.json()
        for feat in data.get("features", []):
            try:
                items.append(
                    STACItem(
                        id=str(feat["id"]),
                        geometry=feat.get("geometry", {}),
                        properties=feat.get("properties", {}),
                        assets=feat.get("assets", {}),
                        bbox=tuple(feat.get("bbox", (0, 0, 0, 0))),
                        datetime=feat.get("properties", {}).get("datetime"),
                        collection=feat.get("collection"),
                    )
                )
            except Exception:  # noqa: BLE001 - skip malformed items
                continue
    return items


def cache_stac_items(items: Sequence[STACItem], path: Path | str) -> Path:
    """Persist a list of STAC items to a JSON file (for offline experiments)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    serialized = [
        {
            "id": it.id,
            "geometry": it.geometry,
            "properties": it.properties,
            "assets": it.assets,
            "bbox": list(it.bbox),
            "datetime": it.datetime,
            "collection": it.collection,
        }
        for it in items
    ]
    p.write_text(json.dumps(serialized, indent=2, default=str), encoding="utf-8")
    return p


__all__ = ["STACItem", "fetch_stac_items", "cache_stac_items", "TileSpec", "tile_raster"]
