"""Les points d'entrée en ligne de commande démarrent-ils ?

Les tests unitaires couvrent les modules, pas les scripts : un bug dans
l'assemblage des arguments ne se voyait jusqu'ici que dans l'image Docker de
la CI, après le build. Ces essais en mode synthétique ne demandent aucune
donnée et tiennent en quelques secondes.
"""

import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]


def lancer(*args: str, attendu: int = 0) -> subprocess.CompletedProcess:
    r = subprocess.run([sys.executable, *args], cwd=RACINE,
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == attendu, f"code {r.returncode}\n{r.stdout}\n{r.stderr}"
    return r


def test_plot_pixel_runs_on_synthetic_data(tmp_path):
    sortie = tmp_path / "figure.png"
    r = lancer("scripts/plot_pixel.py", "--synthetic", "--out", str(sortie))
    assert sortie.exists() and sortie.stat().st_size > 0
    assert "Figure écrite" in r.stdout


def test_build_dataset_explains_a_missing_export(tmp_path):
    """Sans CSV rapatrié, le script doit dire quoi faire, pas tracer une pile."""
    r = lancer("scripts/build_dataset.py", "--samples-dir", str(tmp_path),
               "--no-labels", attendu=1)
    assert "Aucun fichier" in (r.stdout + r.stderr)


def test_entry_points_show_their_help():
    for script in ("extract_s2.py", "build_dataset.py", "plot_pixel.py",
                   "prepare_spruce_mask.py", "run_fordead.py"):
        r = lancer(f"scripts/{script}", "--help")
        assert "usage:" in r.stdout


def test_synthetic_demo_never_overwrites_the_readme_figure():
    """La démo écrit sa propre figure : make demo ne doit pas effacer la vraie."""
    reelle = RACINE / "docs/figures/healthy_vs_attacked.png"
    avant = reelle.stat().st_mtime_ns if reelle.exists() else None
    lancer("scripts/plot_pixel.py", "--synthetic")
    assert (RACINE / "docs/figures/synthetic_demo.png").exists()
    if avant is not None:
        assert reelle.stat().st_mtime_ns == avant
