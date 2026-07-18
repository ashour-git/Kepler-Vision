"""PyTorch Lightning trainer for segmentation models.

This is a runnable scaffold. To run end-to-end you'll need:
- `lightning`, `torch`, `torchmetrics` installed
- A `TileDataset` and a torch `DataLoader`
- A `build_segmentation_model(...)` model

Usage:
    config = TrainingConfig(num_classes=2, in_channels=6)
    model, run = fit_segmentation_model(config, train_loader, val_loader)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

try:
    import torch
    from torch.utils.data import DataLoader
    import lightning as L
    from lightning.pytorch import Trainer as LTrainer
    import torchmetrics.classification as tm_cls
    from torch.optim import AdamW
    from torch.optim.lr_scheduler import CosineAnnealingLR
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "PyTorch + Lightning are required. Install with "
        "`pip install -e \".[torch-cpu]\"`."
    ) from exc

from ..models.factory import build_segmentation_model
from ..models.heads import UPerNetHead


@dataclass
class TrainingConfig:
    """Configuration for a training run."""

    num_classes: int = 1
    in_channels: int = 6
    base_channels: int = 32
    learning_rate: float = 3e-4
    weight_decay: float = 0.05
    max_epochs: int = 50
    precision: str = "bf16-mixed"
    accelerator: str = "auto"
    devices: int = 1
    output_dir: Path = Path("./runs")
    experiment_name: str = "kepler-baseline"
    log_every_n_steps: int = 10
    val_check_interval: float = 1.0
    gradient_clip_val: float = 1.0
    deterministic: bool = True
    warmup_pct: float = 0.05
    extra: dict[str, Any] = field(default_factory=dict)


class _SegmentationLitModel(L.LightningModule):
    """A Lightning wrapper around the small segmentation model."""

    def __init__(
        self,
        config: TrainingConfig,
        head_factory: Any | None = None,
    ) -> None:
        super().__init__()
        self.config = config
        self.model = build_segmentation_model(
            in_channels=config.in_channels,
            num_classes=config.num_classes,
            base_channels=config.base_channels,
        )
        if head_factory is not None:
            # Replace the head with a custom one (e.g., for transfer learning).
            in_ch = config.base_channels * 4
            self.model.head = head_factory(in_channels=in_ch, num_classes=config.num_classes)
        task = "binary" if config.num_classes == 1 else "multiclass"
        self.train_iou = tm_cls.JaccardIndex(task=task, num_classes=config.num_classes)
        self.val_iou = tm_cls.JaccardIndex(task=task, num_classes=config.num_classes)
        self.criterion = _DiceCELoss(num_classes=config.num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.model(x)

    def _step(self, batch: Any, stage: str) -> torch.Tensor:
        x, y = batch["image"], batch["mask"]
        logits = self(x)
        loss = self.criterion(logits, y)
        iou = getattr(self, f"{stage}_iou")
        if self.config.num_classes == 1:
            preds = (logits.squeeze(1) > 0).long()
            iou.update(preds, y.long())
        else:
            preds = logits.argmax(dim=1)
            iou.update(preds, y.long())
        self.log(f"{stage}/loss", loss, on_step=(stage == "train"), on_epoch=True, prog_bar=True)
        self.log(f"{stage}/iou", iou, on_step=False, on_epoch=True, prog_bar=True)
        return loss

    def training_step(self, batch: Any, batch_idx: int) -> torch.Tensor:
        return self._step(batch, "train")

    def validation_step(self, batch: Any, batch_idx: int) -> torch.Tensor:
        return self._step(batch, "val")

    def configure_optimizers(self) -> Any:
        opt = AdamW(self.parameters(), lr=self.config.learning_rate, weight_decay=self.config.weight_decay)
        sched = CosineAnnealingLR(opt, T_max=self.config.max_epochs, eta_min=self.config.learning_rate * 0.1)
        return {"optimizer": opt, "lr_scheduler": sched}


class _DiceCELoss(torch.nn.Module):
    """Combined Dice + cross-entropy loss for segmentation."""

    def __init__(self, num_classes: int) -> None:
        super().__init__()
        self.num_classes = num_classes
        if num_classes == 1:
            self.ce = torch.nn.BCEWithLogitsLoss()
        else:
            self.ce = torch.nn.CrossEntropyLoss()

    def forward(self, logits: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        if self.num_classes == 1:
            ce = self.ce(logits.squeeze(1), target.float())
            probs = torch.sigmoid(logits.squeeze(1))
            dice = 1 - _dice(probs, target.float())
        else:
            ce = self.ce(logits, target.long())
            probs = torch.softmax(logits, dim=1)
            dice = 1 - _dice_multiclass(probs, target.long(), self.num_classes)
        return ce + dice


def _dice(probs: torch.Tensor, target: torch.Tensor, eps: float = 1e-6) -> torch.Tensor:
    intersection = (probs * target).sum(dim=(1, 2))
    denom = probs.sum(dim=(1, 2)) + target.sum(dim=(1, 2))
    return ((2.0 * intersection + eps) / (denom + eps)).mean()


def _dice_multiclass(probs: torch.Tensor, target: torch.Tensor, num_classes: int, eps: float = 1e-6) -> torch.Tensor:
    out: list[torch.Tensor] = []
    for c in range(num_classes):
        pc = probs[:, c]
        tc = (target == c).float()
        inter = (pc * tc).sum(dim=(1, 2))
        denom = pc.sum(dim=(1, 2)) + tc.sum(dim=(1, 2))
        out.append(((2.0 * inter + eps) / (denom + eps)).mean())
    return torch.stack(out).mean()


class SegmentationTrainer:
    """A thin wrapper around the Lightning Trainer."""

    def __init__(self, config: TrainingConfig) -> None:
        self.config = config
        self._trainer: LTrainer | None = None

    def fit(
        self,
        train_loader: DataLoader,
        val_loader: DataLoader | None = None,
        *,
        head_factory: Any | None = None,
    ) -> dict[str, Any]:
        cfg = self.config
        cfg.output_dir.mkdir(parents=True, exist_ok=True)
        lit = _SegmentationLitModel(cfg, head_factory=head_factory)
        self._trainer = LTrainer(
            max_epochs=cfg.max_epochs,
            precision=cfg.precision,
            accelerator=cfg.accelerator,
            devices=cfg.devices,
            log_every_n_steps=cfg.log_every_n_steps,
            val_check_interval=cfg.val_check_interval,
            gradient_clip_val=cfg.gradient_clip_val,
            deterministic=cfg.deterministic,
            default_root_dir=cfg.output_dir,
        )
        self._trainer.fit(lit, train_dataloaders=train_loader, val_dataloaders=val_loader)
        return {"model": lit.model, "trainer": self._trainer, "config": cfg}


def fit_segmentation_model(
    config: TrainingConfig,
    train_loader: DataLoader,
    val_loader: DataLoader | None = None,
    *,
    head_factory: Any | None = None,
) -> tuple[Any, dict[str, Any]]:
    """Fit a small segmentation model and return `(model_state, run)`.

    `model_state` is the underlying `nn.Module`; `run` is the dict returned
    by `SegmentationTrainer.fit`.
    """
    trainer = SegmentationTrainer(config)
    run = trainer.fit(train_loader, val_loader, head_factory=head_factory)
    return run["model"], run


__all__ = [
    "TrainingConfig",
    "SegmentationTrainer",
    "fit_segmentation_model",
    "UPerNetHead",
    "Iterable",
]
