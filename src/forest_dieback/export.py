"""Export ONNX et mesures de frugalité (paramètres, temps d'inférence CPU)."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch

from .config import load_config
from .model import build_model, count_parameters

PIXELS_PER_100KM2 = 1_000_000  # pixels de 10 m dans 100 km² (avant masque épicéa)


def load_checkpoint(path: Path):
    ckpt = torch.load(path, map_location="cpu", weights_only=False)
    model = build_model(ckpt["config"], ckpt["n_channels"], ckpt["seq_len"])
    model.load_state_dict(ckpt["state_dict"])
    return model.eval(), ckpt


def export_onnx(model: torch.nn.Module, seq_len: int, n_channels: int, out: Path) -> Path:
    dummy = torch.zeros(1, seq_len, n_channels)
    torch.onnx.export(model, dummy, out, input_names=["series"], output_names=["logit"],
                      dynamic_axes={"series": {0: "batch"}, "logit": {0: "batch"}},
                      opset_version=17, dynamo=False)
    return out


def benchmark_onnx(path: Path, seq_len: int, n_channels: int,
                   batch: int = 4096, n_batches: int = 10) -> dict[str, float]:
    import onnxruntime as ort

    sess = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    x = np.random.default_rng(0).normal(size=(batch, seq_len, n_channels)).astype(np.float32)
    sess.run(None, {"series": x})  # chauffe
    t0 = time.perf_counter()
    for _ in range(n_batches):
        sess.run(None, {"series": x})
    per_pixel = (time.perf_counter() - t0) / (batch * n_batches)
    return {
        "onnx_size_mb": path.stat().st_size / 1e6,
        "us_per_pixel": per_pixel * 1e6,
        "seconds_per_100km2": per_pixel * PIXELS_PER_100KM2,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", default=None)
    p.add_argument("--checkpoint", type=Path, default=None)
    args = p.parse_args()
    cfg = load_config(args.config)
    models = Path(cfg["paths"]["models"])
    model, ckpt = load_checkpoint(args.checkpoint or models / "tempcnn.pt")
    onnx_path = export_onnx(model, ckpt["seq_len"], ckpt["n_channels"], models / "tempcnn.onnx")
    report = {"n_params": count_parameters(model),
              **benchmark_onnx(onnx_path, ckpt["seq_len"], ckpt["n_channels"])}
    (models / "frugality.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
