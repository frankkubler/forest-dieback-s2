# Toutes les commandes passent par uv ; dans l'image Docker, RUN= (venv déjà actif).
RUN ?= uv run

.PHONY: install lint test extract fordead train demo benchmark

install:          ## environnement complet (.venv) avec toutes les extras
	uv sync --all-extras

lint:
	$(RUN) ruff check src tests scripts

test:
	$(RUN) pytest -q

extract:          ## 1. exports GEE des séries S2 masquées
	$(RUN) python scripts/extract_s2.py

fordead:          ## 3. méthode de référence (fordead installé à part)
	python scripts/run_fordead.py --input data/raw/s2_theia

train:            ## 5. entraînement TempCNN
	$(RUN) python -m forest_dieback.train --data data/processed/dataset.npz

demo:             ## pipeline complet sur données synthétiques, sans GEE
	$(RUN) python -m forest_dieback.train --synthetic --no-mlflow
	$(RUN) python -m forest_dieback.export
	$(RUN) python scripts/plot_pixel.py --synthetic

benchmark:        ## 7. export ONNX et mesures de frugalité
	$(RUN) python -m forest_dieback.export
