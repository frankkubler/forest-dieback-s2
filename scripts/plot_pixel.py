"""Figure du README : le CRSWIR des pixels sains et des pixels attaqués.

    python scripts/plot_pixel.py                    # depuis data/processed/dataset.npz
    python scripts/plot_pixel.py --synthetic        # démo sans données

À gauche, les deux populations recalées sur la date de première anomalie
donnée par les cartes FORDEAD : trait plein pour la médiane, bande pour
l'écart interquartile. Les pixels étant attaqués entre 2018 et 2023, les
moyenner en temps calendaire effacerait le signal. À droite, un pixel pris
isolément, dans son temps propre.
"""

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

SAIN, ATTAQUE = "#2e7d32", "#c62828"


def load(args):
    """Séries du canal CRSWIR, étiquettes et axe temporel."""
    if args.synthetic:
        from forest_dieback.synthetic import make_series
        series, labels, _, _ = make_series(n=400)
        return series[:, :, 0], labels, None, None
    d = np.load(args.data)
    canaux = [str(c) for c in d["channels"]] if "channels" in d else ["CRSWIR"]
    series = d["series"][:, :, canaux.index(args.channel)]
    dates = pd.to_datetime([str(x) for x in d["dates"]]) if "dates" in d else None
    onset = [str(o) for o in d["onset"]] if "onset" in d else None
    return series, d["labels"], dates, onset


def recale(series: np.ndarray, dates, onset, avant: int = 36, apres: int = 36):
    """Recentre chaque série sur sa date de première anomalie.

    Renvoie un tableau (n, avant + apres) et l'axe en pas de composite, les
    valeurs hors de la série d'origine restant à NaN.
    """
    out = np.full((len(series), avant + apres), np.nan, dtype=np.float32)
    for i, (serie, jour) in enumerate(zip(series, onset, strict=True)):
        if not jour:
            continue
        pivot = int(np.argmin(np.abs(dates - pd.Timestamp(jour))))
        lo, hi = max(0, pivot - avant), min(len(serie), pivot + apres)
        out[i, avant - (pivot - lo):avant + (hi - pivot)] = serie[lo:hi]
    return out, np.arange(-avant, apres)


def bande(ax, axe, valeurs, couleur, nom):
    """Médiane et écart interquartile d'une population."""
    q1, med, q3 = np.nanpercentile(valeurs, [25, 50, 75], axis=0)
    ax.fill_between(axe, q1, q3, color=couleur, alpha=0.18, linewidth=0)
    ax.plot(axe, med, color=couleur, linewidth=1.6, label=f"{nom} (n = {len(valeurs)})")
    return med


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", type=Path, default=Path("data/processed/dataset.npz"))
    p.add_argument("--synthetic", action="store_true")
    p.add_argument("--channel", default="CRSWIR")
    p.add_argument("--out", type=Path, default=None,
                   help="défaut : docs/figures/healthy_vs_attacked.png, et "
                        "synthetic_demo.png en mode --synthetic")
    args = p.parse_args()
    # la démo ne doit pas écraser la figure du README, tirée des vraies séries
    if args.out is None:
        nom = "synthetic_demo.png" if args.synthetic else "healthy_vs_attacked.png"
        args.out = Path("docs/figures") / nom

    series, labels, dates, onset = load(args)
    sains, attaques = series[labels == 0], series[labels == 1]
    if not len(attaques):
        raise SystemExit("Aucun pixel attaqué : construire le jeu avec les cartes FORDEAD.")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 3.8),
                                   gridspec_kw={"width_ratios": [3, 2]})

    if onset and dates is not None:
        # chaque pixel attaqué donne son pivot à un pixel sain tiré au hasard,
        # pour que les deux populations couvrent la même fenêtre saisonnière
        tirage = np.random.default_rng(0).permutation(len(sains))[:len(attaques)]
        faux = np.array([""] * len(sains), dtype=object)
        faux[tirage] = [o for o, lab in zip(onset, labels, strict=True) if lab == 1]
        cale_sain, axe = recale(sains, dates, faux)
        cale_att, _ = recale(attaques, dates, [o for o, lab in zip(onset, labels, strict=True)
                                               if lab == 1])
        bande(ax1, axe, cale_sain[np.isfinite(cale_sain).any(axis=1)], SAIN, "sains")
        bande(ax1, axe, cale_att, ATTAQUE, "attaqués")
        ax1.axvline(0, color="0.3", linewidth=0.8, linestyle="--")
        ax1.annotate("première anomalie", (0, ax1.get_ylim()[1]), fontsize=8,
                     ha="center", va="top", color="0.3")
        ax1.set_xlabel("composites de 10 jours autour de la détection")
        ax1.set_title("Recalées sur la date d'attaque", fontsize=10, loc="left")
    else:
        axe = dates if dates is not None else np.arange(series.shape[1]) * 10
        bande(ax1, axe, sains, SAIN, "sains")
        bande(ax1, axe, attaques, ATTAQUE, "attaqués")
        ax1.set_title("Les deux populations", fontsize=10, loc="left")
    ax1.set_ylabel(args.channel)
    ax1.legend(frameon=False, loc="upper left", fontsize=9)

    # le pixel dont la fin s'écarte le plus de son propre début
    debut, fin = np.nanmedian(attaques[:, :30], axis=1), np.nanmedian(attaques[:, -30:], axis=1)
    exemple = attaques[np.argmax(fin - debut)]
    axe2 = dates if dates is not None else np.arange(series.shape[1]) * 10
    ax2.plot(axe2, np.nanmedian(sains, axis=0), color=SAIN, linewidth=1.2, alpha=0.7,
             label="médiane saine")
    ax2.plot(axe2, exemple, color=ATTAQUE, linewidth=1.2, label="un pixel attaqué")
    ax2.legend(frameon=False, loc="upper left", fontsize=9)
    ax2.set_title("Un pixel, en temps calendaire", fontsize=10, loc="left")

    for ax in (ax1, ax2):
        ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=150)
    print(f"Figure écrite : {args.out}  "
          f"({len(sains)} sains, {len(attaques)} attaqués, {series.shape[1]} dates)")


if __name__ == "__main__":
    main()
