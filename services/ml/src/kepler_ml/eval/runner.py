"""Evaluation runner: load model + dataset, run inference, compute metrics."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from .metrics import (
    compute_classification,
    compute_segmentation,
    compute_detection,
    compute_change_detection,
)


@dataclass
class EvalConfig:
    """Configuration for an evaluation run."""

    model_name: str
    dataset_id: str
    num_classes: int
    task: str = "segmentation"  # segmentation | classification | detection | change_detection
    output_dir: Path = Path("./eval")
    per_region: bool = True
    save_confusion_matrix: bool = True


@dataclass
class EvalOutput:
    """Result of an evaluation run."""

    config: EvalConfig
    metrics: dict[str, float]
    per_class: dict[str, dict[str, float]] = field(default_factory=dict)
    per_region: dict[str, dict[str, float]] = field(default_factory=dict)
    confusion_matrix_uri: str | None = None
    duration_seconds: float = 0.0
    created_at: str = ""


class EvalRunner:
    """Run an evaluation, persist results, return a summary."""

    def __init__(self, config: EvalConfig) -> None:
        self.config = config

    def run(
        self,
        *,
        y_true: Sequence[Any],
        y_pred: Sequence[Any],
        regions: Sequence[str] | None = None,
    ) -> EvalOutput:
        started = time.perf_counter()
        if self.config.task == "classification":
            m = compute_classification(y_true, y_pred, num_classes=self.config.num_classes)
            metrics = m.to_dict()
            per_class = {f"class_{i}": {"f1": f1, "precision": p, "recall": r, "support": s} for i, (f1, p, r, s) in enumerate(zip(m.f1_per_class, m.precision_per_class, m.recall_per_class, m.support_per_class))}
        elif self.config.task == "segmentation":
            m = compute_segmentation(np.asarray(y_true), np.asarray(y_pred), num_classes=self.config.num_classes)
            metrics = m.to_dict()
            per_class = {f"class_{i}": {"iou": iou, "dice": d, "precision": p, "recall": r} for i, (iou, d, p, r) in enumerate(zip(m.iou_per_class, m.dice_per_class, m.precision_per_class, m.recall_per_class))}
        elif self.config.task == "detection":
            m = compute_detection(y_true, y_pred)
            metrics = m.to_dict()
            per_class = {str(k): {"ap_50": v} for k, v in m.per_class_ap_50.items()}
        elif self.config.task == "change_detection":
            m = compute_change_detection(np.asarray(y_true), np.asarray(y_pred))
            metrics = m.to_dict()
            per_class = {}
        else:
            raise ValueError(f"Unknown task: {self.config.task}")

        per_region: dict[str, dict[str, float]] = {}
        if self.config.per_region and regions is not None:
            for region in set(regions):
                idx = [i for i, r in enumerate(regions) if r == region]
                if not idx:
                    continue
                if self.config.task == "segmentation":
                    rm = compute_segmentation(np.asarray(y_true)[idx], np.asarray(y_pred)[idx], num_classes=self.config.num_classes)
                    per_region[region] = {"mean_iou": rm.mean_iou, "pixel_accuracy": rm.pixel_accuracy}
                elif self.config.task == "classification":
                    rt = [y_true[i] for i in idx]
                    rp = [y_pred[i] for i in idx]
                    rc = compute_classification(rt, rp, num_classes=self.config.num_classes)
                    per_region[region] = {"accuracy": rc.accuracy, "macro_f1": rc.macro_f1}

        output = EvalOutput(
            config=self.config,
            metrics=metrics,
            per_class=per_class,
            per_region=per_region,
            duration_seconds=time.perf_counter() - started,
        )

        # Persist
        out_dir = Path(self.config.output_dir) / f"{self.config.model_name}__{self.config.dataset_id}"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "metrics.json").write_text(json.dumps(asdict(output), indent=2, default=str), encoding="utf-8")
        return output


__all__ = ["EvalRunner", "EvalConfig", "EvalOutput"]
