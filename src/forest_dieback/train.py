"""Entraînement du modèle temporel, suivi des runs avec MLflow."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader

from .config import load_config
from .dataset import PixelSeriesDataset, normalize, spatial_block_split
from .metrics import binary_metrics
from .model import build_model, count_parameters


def load_arrays(path: Path | None, synthetic: bool):
    if synthetic:
        from .synthetic import make_series
        return make_series()
    data = np.load(path)
    return data["series"], data["labels"], data["x"], data["y"]


def evaluate(model: nn.Module, loader: DataLoader) -> dict[str, float]:
    model.eval()
    preds, targets = [], []
    with torch.no_grad():
        for xb, yb in loader:
            preds.append(torch.sigmoid(model(xb)) > 0.5)
            targets.append(yb.bool())
    return binary_metrics(torch.cat(targets).numpy(), torch.cat(preds).numpy())


def train(cfg: dict, data_path: Path | None = None, synthetic: bool = False,
          use_mlflow: bool = True) -> dict:
    torch.manual_seed(cfg["dataset"]["seed"])
    series, labels, x, y = load_arrays(data_path, synthetic)
    split = spatial_block_split(x, y, cfg["dataset"]["block_size_m"],
                                cfg["dataset"]["split"], cfg["dataset"]["seed"])

    train_x, mean, std = normalize(series[split == "train"])
    val_x, _, _ = normalize(series[split == "val"], mean, std)
    tc = cfg["train"]
    train_dl = DataLoader(PixelSeriesDataset(train_x, labels[split == "train"]),
                          batch_size=tc["batch_size"], shuffle=True, drop_last=True)
    val_dl = DataLoader(PixelSeriesDataset(val_x, labels[split == "val"]),
                        batch_size=tc["batch_size"])

    _, seq_len, n_channels = series.shape
    model = build_model(cfg, n_channels, seq_len)
    pos = labels[split == "train"].mean()
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor((1 - pos) / max(pos, 1e-6)))
    opt = torch.optim.AdamW(model.parameters(), lr=tc["lr"], weight_decay=tc["weight_decay"])

    run = None
    if use_mlflow:
        import mlflow
        mlflow.set_experiment(tc["mlflow_experiment"])
        run = mlflow.start_run()
        mlflow.log_params({**cfg["model"], **tc, "n_params": count_parameters(model)})

    best_f1, best_state, metrics = -1.0, None, {}
    for epoch in range(tc["epochs"]):
        model.train()
        for xb, yb in train_dl:
            opt.zero_grad()
            loss = loss_fn(model(xb), yb)
            loss.backward()
            opt.step()
        metrics = evaluate(model, val_dl)
        if run:
            mlflow.log_metrics({"loss": loss.item(), **{f"val_{k}": v for k, v in metrics.items()}},
                               step=epoch)
        print(f"epoch {epoch:3d}  loss {loss.item():.4f}  val_f1 {metrics['f1']:.3f}")
        if metrics["f1"] > best_f1:
            best_f1 = metrics["f1"]
            best_state = {k: v.clone() for k, v in model.state_dict().items()}

    out = Path(cfg["paths"]["models"])
    out.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": best_state, "mean": mean, "std": std,
                "seq_len": seq_len, "n_channels": n_channels, "config": cfg},
               out / "tempcnn.pt")
    summary = {"best_val_f1": best_f1, "n_params": count_parameters(model)}
    (out / "train_summary.json").write_text(json.dumps(summary, indent=2))
    if run:
        mlflow.log_metric("best_val_f1", best_f1)
        mlflow.end_run()
    return summary


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", default=None)
    p.add_argument("--data", type=Path, default=Path("data/processed/dataset.npz"))
    p.add_argument("--synthetic", action="store_true", help="données synthétiques (démo)")
    p.add_argument("--no-mlflow", action="store_true")
    args = p.parse_args()
    print(train(load_config(args.config), args.data, args.synthetic, not args.no_mlflow))


if __name__ == "__main__":
    main()
