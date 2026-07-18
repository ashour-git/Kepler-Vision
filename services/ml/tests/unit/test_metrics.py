"""Unit tests for evaluation metrics."""

from __future__ import annotations

import numpy as np
import pytest

from kepler_ml.eval.metrics import (
    compute_change_detection,
    compute_classification,
    compute_detection,
    compute_segmentation,
)


def test_classification_perfect() -> None:
    y_true = [0, 1, 2, 0, 1, 2]
    y_pred = [0, 1, 2, 0, 1, 2]
    m = compute_classification(y_true, y_pred, num_classes=3)
    assert m.accuracy == 1.0
    assert m.macro_f1 == 1.0
    assert m.weighted_f1 == 1.0
    assert m.confusion_matrix.shape == (3, 3)
    np.testing.assert_array_equal(np.diag(m.confusion_matrix), m.support_per_class)


def test_classification_mismatch() -> None:
    y_true = [0, 0, 0, 0]
    y_pred = [1, 1, 1, 1]
    m = compute_classification(y_true, y_pred, num_classes=2)
    assert m.accuracy == 0.0
    assert m.macro_f1 == 0.0


def test_classification_empty_raises() -> None:
    with pytest.raises(ValueError):
        compute_classification([], [], num_classes=2)


def test_segmentation_perfect() -> None:
    y_true = np.array([[0, 1], [1, 2]], dtype=np.int64)
    y_pred = y_true.copy()
    m = compute_segmentation(y_true, y_pred, num_classes=3)
    assert m.mean_iou == 1.0
    assert m.pixel_accuracy == 1.0
    assert m.macro_f1 == 1.0


def test_segmentation_shape_mismatch_raises() -> None:
    with pytest.raises(ValueError):
        compute_segmentation(np.zeros((2, 2)), np.zeros((2, 3)), num_classes=2)


def test_change_detection_perfect() -> None:
    y_true = np.zeros((10, 10), dtype=np.uint8)
    y_true[2:5, 2:5] = 1
    m = compute_change_detection(y_true, y_true)
    assert m.iou == 1.0
    assert m.f1 == 1.0


def test_change_detection_partial() -> None:
    y_true = np.zeros((10, 10), dtype=np.uint8)
    y_true[2:5, 2:5] = 1
    y_pred = y_true.copy()
    y_pred[2:5, 6:8] = 1  # extra false positive
    y_pred[7:8, 7:8] = 0  # missed detection (already 0)
    m = compute_change_detection(y_true, y_pred)
    assert 0.0 < m.iou < 1.0
    assert 0.0 < m.precision < 1.0


def test_detection_returns_structure() -> None:
    preds = [{"image_id": "a", "category_id": 1, "bbox": [0, 0, 10, 10], "score": 0.9}]
    gts = [{"image_id": "a", "category_id": 1, "bbox": [0, 0, 10, 10]}]
    m = compute_detection(preds, gts)
    assert m.map_50 >= 0.0
    assert m.num_predictions == 1
    assert m.num_ground_truths == 1
