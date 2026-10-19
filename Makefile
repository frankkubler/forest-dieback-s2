# Toutes les commandes passent par uv ; dans l'image Docker, RUN= (venv déjà actif).
RUN ?= uv run

.PHONY: install lint test spruce-mask extract-check extract-samples extract-rasters \
        fordead train demo benchmark

install:          ## environnement complet (.venv) avec toutes les extras
	uv sync --all-extras

lint:
	$(RUN) ruff check src tests scripts

test:
	$(RUN) pytest -q

spruce-mask:      ## masque épicéa depuis la BD Forêt extraite dans data/raw/bdforet/
	@find data/raw/bdforet -name '*.shp' 2>/dev/null | grep -q . || { \
	  echo "Aucun shapefile dans data/raw/bdforet/."; \
	  echo "Télécharger la BD Forêt V2 des départements qui couvrent la zone"; \
	  echo "(68, 88 et 90 pour la Thur et la Doller) sur https://geoservices.ign.fr/bdforet,"; \
	  echo "puis extraire les archives dans ce dossier."; exit 1; }
	$(RUN) python scripts/prepare_spruce_mask.py $$(find data/raw/bdforet -name '*.shp')

extract-check:    ## 1. chiffres clés de la zone (GEE), sans export
	$(RUN) python scripts/extract_s2.py check

extract-samples:  ## 1. séries de pixels tirés dans le masque (CSV vers Drive)
	$(RUN) python scripts/extract_s2.py samples

extract-rasters:  ## 1. piles annuelles de composites (GeoTIFF vers Drive)
	$(RUN) python scripts/extract_s2.py rasters

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
