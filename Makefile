.PHONY: install lint test extract fordead train demo export benchmark

install:
	pip install -e ".[dev]"

lint:
	ruff check src tests scripts

test:
	pytest -q

extract:          ## 1. exports GEE des séries S2 masquées
	python scripts/extract_s2.py

fordead:          ## 3. méthode de référence (fordead installé à part)
	python scripts/run_fordead.py --input data/raw/s2_theia

train:            ## 5. entraînement TempCNN
	python -m forest_dieback.train --data data/processed/dataset.npz

demo:             ## pipeline complet sur données synthétiques, sans GEE
	python -m forest_dieback.train --synthetic --no-mlflow
	python -m forest_dieback.export
	python scripts/plot_pixel.py --synthetic

export benchmark: ## 7. export ONNX et mesures de frugalité
	python -m forest_dieback.export
