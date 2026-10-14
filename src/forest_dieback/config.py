"""Chargement de la configuration YAML."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "configs" / "default.yaml"


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    """Lit la configuration ; GEE_PROJECT surcharge gee.project."""
    with open(path or DEFAULT_CONFIG, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if os.environ.get("GEE_PROJECT"):
        cfg["gee"]["project"] = os.environ["GEE_PROJECT"]
    return cfg
