"""ML settings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MLSettings(BaseSettings):
    """ML platform configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_prefix="KEPLER_ML_",
    )

    # Compute
    device: str = "cuda"  # cuda | cpu | mps
    num_workers: int = 4
    seed: int = 42

    # Training
    default_batch_size: int = 32
    default_learning_rate: float = 3e-4
    default_weight_decay: float = 0.05
    default_max_epochs: int = 50
    precision: str = "bf16-mixed"  # bf16-mixed | 16-mixed | 32

    # IO
    model_store_path: Path = Field(default=Path("./models"))
    artifact_bucket: str = "kepler-models-dev"
    tile_size: int = 512
    tile_overlap: int = 256  # 50% overlap

    # Export
    onnx_opset: int = 19
    trt_fp16: bool = True
    trt_int8: bool = False
    trt_workspace_gb: int = 4

    # Serving
    triton_url: str = "http://triton:8001"
    triton_grpc_url: str = "triton:8001"
    triton_timeout_seconds: float = 30.0

    # Tracking
    mlflow_tracking_uri: str | None = None
    wandb_project: str | None = None

    # Telemetry
    log_level: str = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> MLSettings:
    """Return cached settings."""
    return MLSettings()


def reset_settings_cache() -> None:
    """Reset cache (tests)."""
    get_settings.cache_clear()
