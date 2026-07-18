# Kepler Vision ML

Computer vision platform for Earth observation: training, evaluation, export, registry, and serving.

## Layout

```
kepler_ml/
├── preprocess/        # Raster tiling, normalization, augmentation
├── postprocess/       # Vectorization, polygonization, output formatting
├── datasets/          # Tile datasets, dataloaders
├── training/          # PyTorch Lightning trainers
├── models/            # Backbones, heads, registry
├── eval/              # Metrics, evaluation harness
├── export/            # ONNX + TensorRT export with parity tests
├── registry/          # Model registry glue (artifacts + cards)
├── serving/           # Triton client, preprocessing/aggregation
└── explain/           # Saliency, evidence linking
```

## Development

```bash
pip install -e ".[dev,torch-cpu]"
pytest tests/
ruff check src tests
mypy src
```

## Triton serving

The `deploy/triton/models/*/1/` directories hold Triton config.pbtxt files.
Models are loaded from GCS via the model-store.
