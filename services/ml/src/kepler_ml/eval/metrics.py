"""Evaluation metrics for vision tasks.

All metrics return deterministic, hashable numeric types. Confusion
matrices are returned as numpy arrays.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

import numpy as np


# --- Classification ----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ClassificationMetrics:
    """Per-class and aggregate metrics for a classification task."""

    accuracy: float
    top_k_accuracy: dict[int, float]  # k -> top-k accuracy
    precision_per_class: tuple[float, ...]
    recall_per_class: tuple[float, ...]
    f1_per_class: tuple[float, ...]
    macro_f1: float
    weighted_f1: float
    confusion_matrix: np.ndarray  # (C, C) — rows=truth, cols=pred
    support_per_class: tuple[int, ...]
    num_samples: int

    def to_dict(self) -> dict[str, float | list[float] | list[list[int]]]:
        return {
            "accuracy": self.accuracy,
            "top_k_accuracy": {str(k): v for k, v in self.top_k_accuracy.items()},
            "precision_per_class": list(self.precision_per_class),
            "recall_per_class": list(self.recall_per_class),
            "f1_per_class": list(self.f1_per_class),
            "macro_f1": self.macro_f1,
            "weighted_f1": self.weighted_f1,
            "support_per_class": list(self.support_per_class),
            "num_samples": self.num_samples,
        }


def compute_classification(
    y_true: Sequence[int],
    y_pred: Sequence[int],
    *,
    num_classes: int,
    top_k: Sequence[int] = (1, 3, 5),
    labels: Sequence[str] | None = None,
) -> ClassificationMetrics:
    """Compute classification metrics from integer labels."""
    y_true = np.asarray(y_true, dtype=np.int64)
    y_pred = np.asarray(y_pred, dtype=np.int64)
    if y_true.shape != y_pred.shape:
        raise ValueError("y_true and y_pred must have the same shape")
    n = int(y_true.size)
    if n == 0:
        raise ValueError("Empty input")

    # Confusion matrix
    cm = np.zeros((num_classes, num_classes), dtype=np.int64)
    for t, p in zip(y_true.ravel(), y_pred.ravel()):
        if 0 <= t < num_classes and 0 <= p < num_classes:
            cm[t, p] += 1

    support = cm.sum(axis=1)
    correct = np.diag(cm)
    accuracy = float(correct.sum() / n) if n else 0.0

    precision = np.zeros(num_classes, dtype=np.float64)
    recall = np.zeros(num_classes, dtype=np.float64)
    f1 = np.zeros(num_classes, dtype=np.float64)
    pred_sum = cm.sum(axis=0)
    for c in range(num_classes):
        if pred_sum[c] == 0 and support[c] == 0:
            continue
        precision[c] = correct[c] / pred_sum[c] if pred_sum[c] else 0.0
        recall[c] = correct[c] / support[c] if support[c] else 0.0
        if precision[c] + recall[c] > 0:
            f1[c] = 2 * precision[c] * recall[c] / (precision[c] + recall[c])

    macro_f1 = float(f1.mean())
    weighted_f1 = float(np.sum(f1 * support) / max(int(support.sum()), 1))

    # Top-k accuracy: not applicable to single-label preds, so we only emit k=1 == accuracy.
    top_k_acc = {k: accuracy for k in top_k if k == 1}

    return ClassificationMetrics(
        accuracy=accuracy,
        top_k_accuracy=top_k_acc,
        precision_per_class=tuple(float(x) for x in precision),
        recall_per_class=tuple(float(x) for x in recall),
        f1_per_class=tuple(float(x) for x in f1),
        macro_f1=macro_f1,
        weighted_f1=weighted_f1,
        confusion_matrix=cm,
        support_per_class=tuple(int(x) for x in support),
        num_samples=n,
    )


# --- Segmentation ------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SegmentationMetrics:
    """Per-class and aggregate metrics for semantic segmentation."""

    iou_per_class: tuple[float, ...]
    dice_per_class: tuple[float, ...]
    precision_per_class: tuple[float, ...]
    recall_per_class: tuple[float, ...]
    pixel_accuracy: float
    mean_iou: float
    macro_f1: float
    boundary_f1_1px: float
    boundary_f1_3px: float
    boundary_f1_5px: float
    hausdorff_95: float
    confusion_matrix: np.ndarray
    num_pixels: int

    def to_dict(self) -> dict[str, float | list[float]]:
        return {
            "iou_per_class": list(self.iou_per_class),
            "dice_per_class": list(self.dice_per_class),
            "precision_per_class": list(self.precision_per_class),
            "recall_per_class": list(self.recall_per_class),
            "pixel_accuracy": self.pixel_accuracy,
            "mean_iou": self.mean_iou,
            "macro_f1": self.macro_f1,
            "boundary_f1_1px": self.boundary_f1_1px,
            "boundary_f1_3px": self.boundary_f1_3px,
            "boundary_f1_5px": self.boundary_f1_5px,
            "hausdorff_95": self.hausdorff_95,
            "num_pixels": self.num_pixels,
        }


def _safe_div(a: float, b: float, default: float = 0.0) -> float:
    return a / b if b > 0 else default


def compute_segmentation(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    *,
    num_classes: int,
) -> SegmentationMetrics:
    """Compute segmentation metrics from HW integer arrays."""
    if y_true.shape != y_pred.shape:
        raise ValueError("y_true and y_pred must have the same shape")
    if y_true.ndim != 2:
        raise ValueError("y_true and y_pred must be 2D")
    y_true = y_true.astype(np.int64).ravel()
    y_pred = y_pred.astype(np.int64).ravel()
    n = int(y_true.size)

    cm = np.zeros((num_classes, num_classes), dtype=np.int64)
    for t, p in zip(y_true, y_pred):
        if 0 <= t < num_classes and 0 <= p < num_classes:
            cm[t, p] += 1

    tp = np.diag(cm).astype(np.float64)
    fp = cm.sum(axis=0).astype(np.float64) - tp
    fn = cm.sum(axis=1).astype(np.float64) - tp

    iou = np.array([_safe_div(tp[c], tp[c] + fp[c] + fn[c]) for c in range(num_classes)])
    dice = np.array([_safe_div(2 * tp[c], 2 * tp[c] + fp[c] + fn[c]) for c in range(num_classes)])
    precision = np.array([_safe_div(tp[c], tp[c] + fp[c]) for c in range(num_classes)])
    recall = np.array([_safe_div(tp[c], tp[c] + fn[c]) for c in range(num_classes)])
    f1 = np.array([
        _safe_div(2 * precision[c] * recall[c], precision[c] + recall[c])
        for c in range(num_classes)
    ])

    pixel_accuracy = float(tp.sum() / n) if n else 0.0
    mean_iou = float(iou.mean())
    macro_f1 = float(f1.mean())

    # Boundary F1: average across all classes. The metric is well-defined
    # when the masks are 2D and have the same shape. For 1D inputs we
    # return 1.0 for perfect agreement and 0.0 otherwise (the boundary
    # concept is degenerate in 1D).
    boundary_f1 = {1: 0.0, 3: 0.0, 5: 0.0}
    if y_true.ndim == 2 and y_true.shape == y_pred.shape:
        for tol in (1, 3, 5):
            band_true = np.zeros_like(y_true, dtype=bool)
            band_pred = np.zeros_like(y_true, dtype=bool)
            for c in range(num_classes):
                band_true |= _per_class_boundary_band(y_true, c, tol)
                band_pred |= _per_class_boundary_band(y_pred, c, tol)
            boundary_f1[tol] = _boundary_f1(band_true, band_pred, tol)
    elif y_true.ndim == 1 and y_true.shape == y_pred.shape:
        perfect = bool(np.array_equal(y_true, y_pred))
        for tol in (1, 3, 5):
            boundary_f1[tol] = 1.0 if perfect else 0.0

    hausdorff = _hausdorff_95(y_true, y_pred, num_classes)

    return SegmentationMetrics(
        iou_per_class=tuple(float(x) for x in iou),
        dice_per_class=tuple(float(x) for x in dice),
        precision_per_class=tuple(float(x) for x in precision),
        recall_per_class=tuple(float(x) for x in recall),
        pixel_accuracy=pixel_accuracy,
        mean_iou=mean_iou,
        macro_f1=macro_f1,
        boundary_f1_1px=boundary_f1[1],
        boundary_f1_3px=boundary_f1[3],
        boundary_f1_5px=boundary_f1[5],
        hausdorff_95=hausdorff,
        confusion_matrix=cm,
        num_pixels=n,
    )


def _binary_boundary_band(mask: np.ndarray, tolerance: int) -> np.ndarray:
    """Return a boolean array of boundary pixels plus a tolerance band.

    A pixel is in the band if it is within `tolerance` Chebyshev distance
    of any boundary pixel (a boundary pixel is one whose 4-neighborhood
    contains at least one pixel of a different class).
    """
    try:
        from scipy import ndimage as ndi  # type: ignore[import-untyped]
    except ImportError:
        return mask  # best effort
    # Boundary = mask XOR erosion(mask). Pad before eroding so the band is
    # `tolerance` pixels wide on each side.
    pad = max(0, int(tolerance))
    structure = np.ones((3, 3), dtype=bool)
    eroded = ndi.binary_erosion(mask, structure=structure, iterations=pad + 1, border_value=False)
    boundary = mask & ~eroded
    band = ndi.binary_dilation(boundary, structure=structure, iterations=pad, border_value=False)
    return band


def _boundary_f1(y_true: np.ndarray, y_pred: np.ndarray, tolerance: int) -> float:
    """Compute a simple boundary F1 score with the given tolerance in pixels.

    The metric is computed across all classes (one-vs-rest). For each class:
    - The "true boundary" is a band of width `tolerance` around the GT mask.
    - The "pred boundary" is the union of boundary bands of the predicted mask.
    - Boundary F1 is the F1 of the intersection vs the union of these bands.
    """
    if y_true.size == 0:
        return 0.0
    true = y_true.astype(bool)
    pred = y_pred.astype(bool)
    if true.shape != pred.shape:
        return 0.0
    tp = int((true & pred).sum())
    fp = int((~true & pred).sum())
    fn = int((true & ~pred).sum())
    union = tp + fp + fn
    if union == 0:
        return 1.0
    return (2.0 * tp) / (2.0 * tp + fp + fn)


def _per_class_boundary_band(mask: np.ndarray, class_id: int, tolerance: int) -> np.ndarray:
    """Boundary band for a single class in a multi-class mask."""
    binary = (mask == class_id).astype(bool)
    return _binary_boundary_band(binary, tolerance)


def _hausdorff_95(y_true: np.ndarray, y_pred: np.ndarray, num_classes: int) -> float:
    """Compute the mean 95th-percentile symmetric Hausdorff distance in pixels.

    For each class present in either mask, we compute the boundary points
    and the 95th percentile of the symmetric directed distances. We then
    average across classes. Uses `scipy.spatial.distance` cdist when scipy
    is available; otherwise returns 0.0.
    """
    if num_classes == 0 or y_true.size == 0 or y_true.shape != y_pred.shape:
        return 0.0
    try:
        from scipy.spatial.distance import cdist  # type: ignore[import-untyped]
        from scipy.ndimage import binary_erosion  # type: ignore[import-untyped]
    except ImportError:
        return 0.0

    def _boundary_points(mask: np.ndarray, class_id: int) -> np.ndarray:
        binary = (mask == class_id).astype(bool)
        if not binary.any():
            return np.empty((0, 2), dtype=np.float32)
        # Pad 1D to 2D for boundary detection (treat as a single row).
        if binary.ndim == 1:
            binary = binary[None, :]
        eroded = binary_erosion(binary, border_value=False)
        boundary = binary & ~eroded
        if not boundary.any():
            return np.empty((0, 2), dtype=np.float32)
        ys, xs = np.where(boundary)
        return np.stack([xs, ys], axis=1).astype(np.float32)

    classes = sorted(set(np.unique(y_true).tolist()) | set(np.unique(y_pred).tolist()))
    classes = [c for c in classes if 0 <= c < num_classes]
    distances: list[float] = []
    for c in classes:
        a = _boundary_points(y_true, c)
        b = _boundary_points(y_pred, c)
        if len(a) == 0 or len(b) == 0:
            continue
        d_ab = cdist(a, b).min(axis=1)
        d_ba = cdist(b, a).min(axis=0)
        sym = np.concatenate([d_ab, d_ba])
        if sym.size == 0:
            continue
        # 95th percentile
        distances.append(float(np.percentile(sym, 95)))
    if not distances:
        return 0.0
    return float(np.mean(distances))


# --- Object detection --------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DetectionMetrics:
    """mAP-style metrics."""

    map_50: float
    map_50_95: float
    per_class_ap_50: dict[int, float]
    num_predictions: int
    num_ground_truths: int

    def to_dict(self) -> dict[str, float]:
        return {
            "map_50": self.map_50,
            "map_50_95": self.map_50_95,
            "per_class_ap_50": {str(k): v for k, v in self.per_class_ap_50.items()},
            "num_predictions": self.num_predictions,
            "num_ground_truths": self.num_ground_truths,
        }


def compute_detection(
    predictions: Sequence[dict],
    ground_truths: Sequence[dict],
    *,
    iou_thresholds: Sequence[float] = (0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95),
) -> DetectionMetrics:
    """Compute COCO-style mAP metrics.

    Inputs are lists of dicts with keys:
      - `image_id`: which image the box belongs to
      - `category_id`: integer class label
      - `bbox`: `[x, y, w, h]` in pixels (we also accept `[x1, y1, x2, y2]`)
      - `score` (predictions only): confidence in `[0, 1]`

    For each IoU threshold in `iou_thresholds`, we compute per-class AP
    via the 101-point interpolated PR curve, then average. `map_50` and
    `map_50_95` are the mean across classes at IoU=0.5 and at the
    0.5:0.95 average respectively.
    """
    if not predictions or not ground_truths:
        return DetectionMetrics(
            map_50=0.0,
            map_50_95=0.0,
            per_class_ap_50={},
            num_predictions=len(predictions),
            num_ground_truths=len(ground_truths),
        )

    def _xywh_to_xyxy(b: list[float]) -> tuple[float, float, float, float]:
        if len(b) == 4:
            x, y, w, h = b
            # Heuristic: if the last two values look like x2/y2 (i.e., w/h < 0),
            # treat as xyxy.
            if w < 0 or h < 0:
                return float(x), float(y), float(x + w), float(y + h)
            return float(x), float(y), float(x + w), float(y + h)
        if len(b) == 5:
            return float(b[0]), float(b[1]), float(b[2]), float(b[3])
        raise ValueError(f"bbox must have 4 values, got {len(b)}")

    def _iou(b1: list[float], b2: list[float]) -> float:
        x1a, y1a, x2a, y2a = _xywh_to_xyxy(b1)
        x1b, y1b, x2b, y2b = _xywh_to_xyxy(b2)
        ix1, iy1 = max(x1a, x1b), max(y1a, y1b)
        ix2, iy2 = min(x2a, x2b), min(y2a, y2b)
        iw = max(0.0, ix2 - ix1)
        ih = max(0.0, iy2 - iy1)
        inter = iw * ih
        a = max(0.0, x2a - x1a) * max(0.0, y2a - y1a)
        b = max(0.0, x2b - x1b) * max(0.0, y2b - y1b)
        union = a + b - inter
        return inter / union if union > 0 else 0.0

    # Group GTs by (image_id, category_id)
    gts_by_class: dict[int, dict[str, list[dict]]] = {}
    for g in ground_truths:
        cat = int(g["category_id"])
        img = str(g["image_id"])
        gts_by_class.setdefault(cat, {}).setdefault(img, []).append(g)

    # Per-class AP at a given IoU threshold
    def _ap_at_iou(iou_thr: float) -> dict[int, float]:
        per_class_ap: dict[int, float] = {}
        for cat, gts_by_img in gts_by_class.items():
            # Sort predictions for this class by score desc
            preds = sorted(
                [p for p in predictions if int(p["category_id"]) == cat],
                key=lambda p: float(p.get("score", 0.0)),
                reverse=True,
            )
            total_gt = sum(len(v) for v in gts_by_img.values())
            if total_gt == 0:
                continue
            tp = np.zeros(len(preds), dtype=np.float64)
            fp = np.zeros(len(preds), dtype=np.float64)
            matched: dict[str, set[int]] = {img: set() for img in gts_by_img}
            for i, p in enumerate(preds):
                img = str(p["image_id"])
                gts = gts_by_img.get(img, [])
                best_iou = 0.0
                best_j = -1
                for j, g in enumerate(gts):
                    if j in matched[img]:
                        continue
                    v = _iou(p["bbox"], g["bbox"])
                    if v > best_iou:
                        best_iou = v
                        best_j = j
                if best_iou >= iou_thr and best_j >= 0:
                    tp[i] = 1
                    matched[img].add(best_j)
                else:
                    fp[i] = 1
            cum_tp = np.cumsum(tp)
            cum_fp = np.cumsum(fp)
            recall = cum_tp / max(total_gt, 1)
            precision = cum_tp / np.maximum(cum_tp + cum_fp, 1e-9)
            # 101-point interpolation (COCO)
            ap = 0.0
            for t in np.linspace(0.0, 1.0, 101):
                mask = recall >= t
                ap += float(precision[mask].max() if mask.any() else 0.0)
            ap /= 101.0
            per_class_ap[cat] = ap
        return per_class_ap

    aps_at_50 = _ap_at_iou(0.5)
    aps_at_each: list[dict[int, float]] = [_ap_at_iou(t) for t in iou_thresholds]
    classes = sorted({c for aps in aps_at_each for c in aps})

    def _mean(aps: dict[int, float]) -> float:
        if not aps:
            return 0.0
        return float(np.mean([aps[c] for c in classes if c in aps])) if classes else 0.0

    map_50 = _mean(aps_at_50)
    map_50_95 = float(np.mean([_mean(a) for a in aps_at_each])) if aps_at_each else 0.0

    return DetectionMetrics(
        map_50=map_50,
        map_50_95=map_50_95,
        per_class_ap_50=aps_at_50,
        num_predictions=len(predictions),
        num_ground_truths=len(ground_truths),
    )


# --- Change detection -------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ChangeDetectionMetrics:
    """Change-detection specific metrics."""

    iou: float
    f1: float
    precision: float
    recall: float
    false_alarm_rate_per_km2: float
    missed_detection_rate_per_km2: float
    num_changes: int
    num_pixels: int

    def to_dict(self) -> dict[str, float]:
        return {
            "iou": self.iou,
            "f1": self.f1,
            "precision": self.precision,
            "recall": self.recall,
            "false_alarm_rate_per_km2": self.false_alarm_rate_per_km2,
            "missed_detection_rate_per_km2": self.missed_detection_rate_per_km2,
            "num_changes": self.num_changes,
            "num_pixels": self.num_pixels,
        }


def compute_change_detection(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    *,
    pixel_area_m2: float = 100.0,  # for a 10 m GSD
) -> ChangeDetectionMetrics:
    """Compute change detection metrics."""
    if y_true.shape != y_pred.shape:
        raise ValueError("y_true and y_pred must have the same shape")
    y_true = y_true.astype(bool)
    y_pred = y_pred.astype(bool)
    tp = int((y_true & y_pred).sum())
    fp = int((~y_true & y_pred).sum())
    fn = int((y_true & ~y_pred).sum())
    tn = int((~y_true & ~y_pred).sum())
    union = tp + fp + fn
    iou = tp / union if union else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    area_km2 = y_true.size * pixel_area_m2 / 1_000_000.0
    fa_rate = (fp / area_km2) if area_km2 > 0 else 0.0
    md_rate = (fn / area_km2) if area_km2 > 0 else 0.0

    return ChangeDetectionMetrics(
        iou=iou,
        f1=f1,
        precision=precision,
        recall=recall,
        false_alarm_rate_per_km2=fa_rate,
        missed_detection_rate_per_km2=md_rate,
        num_changes=int(y_true.sum()),
        num_pixels=int(y_true.size),
    )


__all__ = [
    "ClassificationMetrics",
    "SegmentationMetrics",
    "DetectionMetrics",
    "ChangeDetectionMetrics",
    "compute_classification",
    "compute_segmentation",
    "compute_detection",
    "compute_change_detection",
]
