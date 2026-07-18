"""Mask-to-vector conversion.

We use scikit-image's `findContours` (when available) and Shapely for
geometry construction and simplification. Pure-Python, no GDAL needed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Sequence

import numpy as np

try:
    from skimage import measure as _measure  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover
    _measure = None

try:
    from shapely.geometry import Polygon, mapping as shapely_mapping
    from shapely.geometry.base import BaseGeometry
    from shapely.validation import make_valid as _shapely_make_valid
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "shapely is required for vectorization. "
        "Install with `pip install shapely`."
    ) from exc


@dataclass(frozen=True, slots=True)
class VectorizeOptions:
    """Options for mask-to-vector conversion."""

    min_area_pixels: int = 4
    simplify_tolerance: float = 0.5  # pixel units
    target_class: int | None = None  # if None, vectorize all non-zero classes
    transform: tuple[float, float, float, float, float, float] | None = None
    # (a, b, c, d, e, f) for affine: x' = a*x + b*y + c, y' = d*x + e*y + f
    crs: str | None = None


@dataclass(slots=True)
class VectorFeature:
    """A single vectorized feature."""

    class_id: int
    class_name: str
    geometry: BaseGeometry
    area_pixels: int
    properties: dict[str, Any] = field(default_factory=dict)

    def to_geojson_feature(self) -> dict[str, Any]:
        return {
            "type": "Feature",
            "geometry": shapely_mapping(self.geometry),
            "properties": {
                "class_id": self.class_id,
                "class_name": self.class_name,
                "area_pixels": self.area_pixels,
                **self.properties,
            },
        }


def _pixel_to_world(
    coords: Sequence[Sequence[float]],
    transform: tuple[float, float, float, float, float, float] | None,
) -> list[list[float]]:
    if transform is None:
        return [[float(c[0]), float(c[1])] for c in coords]
    a, b, c, d, e, f = transform
    out: list[list[float]] = []
    for x, y in coords:
        out.append([a * x + b * y + c, d * x + e * y + f])
    return out


def _geometry_to_world(geom: BaseGeometry, transform: tuple[float, ...] | None) -> BaseGeometry:
    if transform is None:
        return geom
    from shapely.affinity import affine_transform

    a, b, c, d, e, f = transform
    # shapely affine_transform: matrix is (a, b, d, e, xoff, yoff) where
    # x' = a*x + b*y + xoff, y' = d*x + e*y + yoff
    return affine_transform(geom, matrix=(a, b, d, e, c, f))


def vectorize_mask(
    mask: np.ndarray,
    class_names: list[str] | None = None,
    options: VectorizeOptions | None = None,
) -> list[VectorFeature]:
    """Convert a HW integer mask into vector features per class.

    For each class id present in the mask (other than 0), we extract
    contours, build polygons, simplify, and filter by area.
    """
    if _measure is None:  # pragma: no cover
        raise RuntimeError("scikit-image is required for vectorize_mask")
    if mask.ndim != 2:
        raise ValueError("mask must be HW")
    if class_names is None:
        class_names = []
    if options is None:
        options = VectorizeOptions()

    features: list[VectorFeature] = []
    classes: list[int]
    if options.target_class is not None:
        classes = [options.target_class]
    else:
        classes = sorted(int(c) for c in np.unique(mask) if c != 0)

    for class_id in classes:
        binary = (mask == class_id).astype(np.uint8)
        if binary.sum() < options.min_area_pixels:
            continue
        contours = _measure.find_contours(binary, level=0.5)
        for contour in contours:
            if len(contour) < 3:
                continue
            # skimage returns (row, col); shapely wants (x, y) = (col, row)
            coords = [(float(c), float(r)) for r, c in contour]
            world = _pixel_to_world(coords, options.transform)
            try:
                poly = Polygon(world)
            except Exception:  # noqa: BLE001 - shapely raises various
                continue
            if not poly.is_valid:
                poly = _shapely_make_valid(poly)
            if poly.is_empty:
                continue
            poly = poly.simplify(options.simplify_tolerance, preserve_topology=True)
            if poly.area <= 0 or len(list(poly.exterior.coords)) < 3:
                continue
            area_pixels = int(binary[
                max(0, int(min(c[1] for c in contour))): max(0, int(max(c[1] for c in contour)) + 1),
                max(0, int(min(c[0] for c in contour))): max(0, int(max(c[0] for c in contour)) + 1),
            ].sum())
            if area_pixels < options.min_area_pixels:
                continue
            class_name = class_names[class_id] if 0 <= class_id < len(class_names) else f"class_{class_id}"
            features.append(
                VectorFeature(
                    class_id=class_id,
                    class_name=class_name,
                    geometry=poly,
                    area_pixels=area_pixels,
                )
            )
    return features


def vectorize_with_overlap_blend(
    mask: np.ndarray,
    overlap_features_per_tile: list[tuple[tuple[int, int, int, int], list[VectorFeature]]],
    options: VectorizeOptions | None = None,
) -> list[VectorFeature]:
    """Combine features from multiple tiles, keeping the largest in overlap regions.

    Each tile is identified by `(x_offset, y_offset, width, height)`. The
    features are already in world coordinates; we keep them and filter
    duplicates in overlap by area.
    """
    if options is None:
        options = VectorizeOptions()
    all_features: list[VectorFeature] = []
    for _tile, features in overlap_features_per_tile:
        all_features.extend(features)
    # Deduplicate near-identical features: keep one with max area per buffer
    merged: list[VectorFeature] = []
    used: set[int] = set()
    for i, f in enumerate(all_features):
        if i in used:
            continue
        cluster = [f]
        for j in range(i + 1, len(all_features)):
            if j in used:
                continue
            if f.geometry.intersects(all_features[j].geometry) and f.class_id == all_features[j].class_id:
                cluster.append(all_features[j])
                used.add(j)
        cluster.sort(key=lambda x: x.area_pixels, reverse=True)
        winner = cluster[0]
        # Union the cluster for completeness
        if len(cluster) > 1:
            try:
                u = cluster[0].geometry
                for other in cluster[1:]:
                    u = u.union(other.geometry)
                winner = VectorFeature(
                    class_id=winner.class_id,
                    class_name=winner.class_name,
                    geometry=u if u.area > 0 else winner.geometry,
                    area_pixels=int(winner.area_pixels),
                    properties=winner.properties,
                )
            except Exception:  # noqa: BLE001
                pass
        merged.append(winner)
        used.add(i)
    return merged


def simplify_geometry(geom: BaseGeometry, tolerance: float) -> BaseGeometry:
    """Simplify a geometry preserving topology."""
    return geom.simplify(tolerance, preserve_topology=True)


def features_to_geojson(features: list[VectorFeature]) -> dict[str, Any]:
    """Return a GeoJSON FeatureCollection."""
    return {
        "type": "FeatureCollection",
        "features": [f.to_geojson_feature() for f in features],
    }


def features_to_geojson_string(features: list[VectorFeature]) -> str:
    """Convenience: return a JSON string."""
    return json.dumps(features_to_geojson(features))


__all__ = [
    "vectorize_mask",
    "vectorize_with_overlap_blend",
    "simplify_geometry",
    "features_to_geojson",
    "features_to_geojson_string",
]
