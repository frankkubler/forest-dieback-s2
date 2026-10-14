"""Figure du README : séries CRSWIR d'un pixel sain et d'un pixel attaqué.

    python scripts/plot_pixel.py --synthetic        # démo sans données
    python scripts/plot_pixel.py --data data/processed/dataset.npz
"""

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, default=Path("data/processed/dataset.npz"))
    p.add_argument("--synthetic", action="store_true")
    p.add_argument("--out", type=Path, default=Path("docs/figures/healthy_vs_attacked.png"))
    args = p.parse_args()

    if args.synthetic:
        from forest_dieback.synthetic import make_series
        series, labels, _, _ = make_series(n=200)
    else:
        d = np.load(args.data)
        series, labels = d["series"], d["labels"]

    healthy = series[labels == 0][0, :, 0]
    attacked = series[labels == 1][0, :, 0]
    days = np.arange(len(healthy)) * 10

    fig, ax = plt.subplots(figsize=(8, 3.5))
    ax.plot(days, healthy, label="sain", color="#2e7d32")
    ax.plot(days, attacked, label="attaqué", color="#c62828")
    ax.set_xlabel("jours depuis le début de la série")
    ax.set_ylabel("CRSWIR")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=150)
    print(f"Figure écrite : {args.out}")


if __name__ == "__main__":
    main()
