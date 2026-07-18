"""Kepler ML CLI."""

from __future__ import annotations

import typer
from rich.console import Console

from .registry import (
    ModelRegistry,
    TritonConfig,
    build_segmentation_config,
    write_config,
)
from .domain import (
    License,
    ModelCard,
    ModelFramework,
    ModelStatus,
    ModelTask,
    ModelVersion,
)

app = typer.Typer(no_args_is_help=True, help="Kepler Vision ML platform")
registry_app = typer.Typer(help="Model registry operations")
serving_app = typer.Typer(help="Triton serving config generation")
app.add_typer(registry_app, name="registry")
app.add_typer(serving_app, name="serving")
console = Console()


@registry_app.command("list")
def registry_list(root: str = "./models") -> None:
    """List all registered models."""
    reg = ModelRegistry(root=root)  # type: ignore[arg-type]
    for m in reg.list_models():
        console.print(m)


@registry_app.command("versions")
def registry_versions(model_id: str, root: str = "./models") -> None:
    """List versions of a model."""
    reg = ModelRegistry(root=root)  # type: ignore[arg-type]
    for v in reg.list_versions(model_id):
        console.print(v)


@registry_app.command("register")
def registry_register(
    model_id: str,
    name: str,
    task: str,
    version: str,
    framework: str = "onnx",
    artifact_uri: str | None = None,
    root: str = "./models",
    intended_use: str = "Internal use only.",
    license_name: str = "proprietary",
) -> None:
    """Register a new model version."""
    reg = ModelRegistry(root=root)  # type: ignore[arg-type]
    card = ModelCard(
        intended_use=intended_use,
        license=License(license_name),
    )
    mv = ModelVersion(
        model_id=model_id,
        name=name,
        task=ModelTask(task),
        version=version,
        framework=ModelFramework(framework),
        card=card,
    )
    if artifact_uri:
        from ..domain import ModelArtifact

        mv.artifacts.append(
            ModelArtifact(
                uri=artifact_uri,
                sha256="0" * 64,
                size_bytes=0,
                framework=ModelFramework(framework),
                precision="fp16",
            )
        )
    reg.register_version(mv)
    console.print(f"Registered {model_id}@{version}")


@serving_app.command("init")
def serving_init(
    name: str,
    task: str,
    height: int,
    width: int,
    num_classes: int,
    output_dir: str,
) -> None:
    """Generate a Triton config.pbtxt for a model."""
    if task == "segmentation":
        cfg = build_segmentation_config(name, height=height, width=width, num_classes=num_classes)
    elif task == "classification":
        from .registry import build_classification_config
        cfg = build_classification_config(name, height=height, width=width, num_classes=num_classes)
    elif task == "detection":
        from .registry import build_detection_config
        cfg = build_detection_config(name, height=height, width=width)
    else:
        raise typer.BadParameter(f"Unknown task: {task}")
    write_config(f"{output_dir}/{name}/config.pbtxt", cfg)
    console.print(f"Wrote {output_dir}/{name}/config.pbtxt")


@app.command("version")
def cli_version() -> None:
    """Print the kepler-ml version."""
    from . import __version__
    console.print(f"kepler-ml {__version__}")


def main() -> None:
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
