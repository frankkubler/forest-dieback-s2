"""Modèles temporels pour la classification de séries par pixel."""

from __future__ import annotations

import math

import torch
from torch import nn


class TempCNN(nn.Module):
    """TempCNN (Pelletier et al., 2019) : convolutions 1D sur l'axe du temps.

    Entrée (batch, T, C), sortie un logit par série (sain / attaqué).
    """

    def __init__(self, in_channels: int, seq_len: int, hidden: int = 64,
                 kernel_size: int = 5, dropout: float = 0.2, pool: int = 8):
        super().__init__()
        pool = max(1, min(pool, seq_len))

        def block(c_in: int, c_out: int) -> nn.Sequential:
            return nn.Sequential(
                nn.Conv1d(c_in, c_out, kernel_size, padding=kernel_size // 2),
                nn.BatchNorm1d(c_out),
                nn.ReLU(),
                nn.Dropout(dropout),
            )

        self.features = nn.Sequential(
            block(in_channels, hidden), block(hidden, hidden), block(hidden, hidden)
        )
        # Aplatir la série entière ferait dépendre la tête de sa longueur : sur
        # sept ans de composites, cette seule couche pesait 99 % du modèle.
        # Le pooling ramène le temps à quelques pas, en gardant l'ordre.
        # AvgPool1d à pas fixe plutôt qu'AdaptiveAvgPool1d : ce dernier ne
        # s'exporte en ONNX que si la sortie divise l'entrée, ce qui n'arrive
        # pas avec 259 composites.
        noyau = max(1, math.ceil(seq_len / pool))
        self.pool = nn.AvgPool1d(noyau, stride=noyau, ceil_mode=True)
        with torch.no_grad():  # longueur réelle après pooling, bords compris
            n_pas = self.pool(torch.zeros(1, hidden, seq_len)).shape[-1]
        self.head = nn.Sequential(
            nn.Flatten(),
            nn.Linear(hidden * n_pas, 4 * hidden),
            nn.BatchNorm1d(4 * hidden),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(4 * hidden, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.features(x.transpose(1, 2))  # (B, C, T)
        return self.head(self.pool(x)).squeeze(-1)


def count_parameters(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def build_model(cfg: dict, in_channels: int, seq_len: int) -> nn.Module:
    m = cfg["model"]
    if m["name"] == "tempcnn":
        return TempCNN(in_channels, seq_len, m["hidden"], m["kernel_size"],
                       m["dropout"], m.get("pool", 8))
    raise ValueError(f"Modèle inconnu : {m['name']}")
