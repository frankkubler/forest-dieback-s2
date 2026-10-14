"""Modèles temporels pour la classification de séries par pixel."""

from __future__ import annotations

import torch
from torch import nn


class TempCNN(nn.Module):
    """TempCNN (Pelletier et al., 2019) : convolutions 1D sur l'axe du temps.

    Entrée (batch, T, C), sortie un logit par série (sain / attaqué).
    """

    def __init__(self, in_channels: int, seq_len: int, hidden: int = 64,
                 kernel_size: int = 5, dropout: float = 0.2):
        super().__init__()

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
        self.head = nn.Sequential(
            nn.Flatten(),
            nn.Linear(hidden * seq_len, 4 * hidden),
            nn.BatchNorm1d(4 * hidden),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(4 * hidden, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.features(x.transpose(1, 2))  # (B, C, T)
        return self.head(x).squeeze(-1)


def count_parameters(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def build_model(cfg: dict, in_channels: int, seq_len: int) -> nn.Module:
    m = cfg["model"]
    if m["name"] == "tempcnn":
        return TempCNN(in_channels, seq_len, m["hidden"], m["kernel_size"], m["dropout"])
    raise ValueError(f"Modèle inconnu : {m['name']}")
