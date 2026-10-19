# forest-dieback-s2

Détection du dépérissement des épicéas (attaques de scolytes) à partir de séries temporelles **Sentinel-2**, sur une zone de 20 × 20 km dans les Hautes-Vosges (vallées de la Thur et de la Doller).

Le projet compare un modèle de deep learning temporel (**TempCNN**) à la méthode de référence publique **[FORDEAD](https://fordead.gitlab.io/fordead_package/latest/)** (INRAE TETIS). La comparaison se fait sur environ 200 points photo-interprétés sur orthophotos IGN, qui servent de vérité indépendante.

> 🚧 Projet en cours. Voir la [feuille de route](docs/ROADMAP.md).

| Compétence | Dans ce dépôt |
| --- | --- |
| Télédétection | Séries S2 L2A via Google Earth Engine, masque Cloud Score+, indices CRSWIR / NDVI / NDWI |
| Deep learning | TempCNN en PyTorch (puis petit Transformer temporel), découpage spatial par blocs |
| MLOps | Pipeline en scripts versionnés, `Makefile`, Docker, CI GitHub Actions, suivi MLflow |
| IA frugale | Nombre de paramètres, export ONNX, temps d'inférence CPU pour 100 km² |

## Résultats

*Les figures et le tableau seront remplis au fil des jalons.*

| Méthode | Précision | Rappel | F1 | Délai de détection (j) | Paramètres | Inférence 100 km² (CPU) |
| --- | --- | --- | --- | --- | --- | --- |
| FORDEAD (référence) | – | – | – | – | – | – |
| TempCNN | 0,45 | 0,81 | 0,58 | – | 174 593 | 160 s |

Mesures sur le jeu de test, 699 pixels de blocs spatiaux disjoints de ceux de l'entraînement,
**face aux étiquettes FORDEAD**. Ce n'est donc pas une évaluation indépendante : le modèle est
jugé sur sa capacité à retrouver les détections de la méthode de référence, qui a elle-même ses
erreurs. La ligne FORDEAD reste vide pour cette raison — elle obtiendrait 100 % contre ses
propres cartes. Les deux lignes ne seront comparables qu'avec les points photo-interprétés.

Le modèle privilégie le rappel : il retrouve 81 % des pixels que FORDEAD déclare dépérissants,
au prix d'une alerte sur deux qui est fausse. C'est l'effet du poids de classe, les pixels
attaqués ne représentant que 4,8 % du jeu. Le réseau tient dans 0,7 Mo une fois exporté en ONNX.

![CRSWIR des pixels sains et attaqués](docs/figures/healthy_vs_attacked.png)

Les 4 701 pixels du jeu, recalés sur la date de première anomalie donnée par FORDEAD.
Avant la détection, les deux populations sont indiscernables ; aussitôt après, le CRSWIR
médian des pixels attaqués passe de 0,75 à 0,90 et y reste, quand celui des pixels sains
ne bouge pas. En temps calendaire ce signal disparaît, les attaques s'étalant de 2018 à
2023 — c'est tout l'enjeu d'un modèle temporel.

<!-- ![Carte des détections](docs/figures/detection_map.png) -->

## Données

Toutes les sources sont gratuites.

| Donnée | Rôle | Accès |
| --- | --- | --- |
| Sentinel-2 L2A (2017–2026) | Séries de réflectance, 10–20 m | GEE `COPERNICUS/S2_SR_HARMONIZED` |
| Cloud Score+ | Masque des nuages et des ombres | GEE `GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED` |
| [Cartes scolytes FORDEAD](https://doi.org/10.57745/8LJGQ9) | Étiquettes faibles | Recherche Data Gouv, Etalab 2.0 |
| BD Forêt V2 (IGN) | Masque des peuplements d'épicéas (départements 68, 88 et 90) | Géoservices IGN |
| BD ORTHO (IGN) | Photo-interprétation de ~200 points de contrôle | Géoservices IGN |
| Sentinel-1 GRD (option) | Radar, insensible aux nuages | GEE `COPERNICUS/S1_GRD` |
| Sentinel-2 L2A THEIA | Entrée de FORDEAD, lue à la demande | STAC `api.stac.teledetection.fr`, compte requis pour les images |

**Biais connu :** un modèle entraîné sur les cartes FORDEAD apprend d'abord à imiter FORDEAD. C'est pourquoi l'évaluation finale ne s'appuie que sur les points photo-interprétés, indépendants des deux méthodes.

## Pipeline

```
 GEE export ─► indices ─► FORDEAD (référence)
      │            │
      └────────────┴─► jeu d'entraînement (blocs spatiaux) ─► TempCNN ─► évaluation ─► ONNX + benchmark
```

| Étape | Commande | Module |
| --- | --- | --- |
| 0. Masque résineux | `make spruce-mask` | `forest_dieback.masks` |
| 1. Extraction S2 masquée | `make extract-check`, `extract-samples`, `extract-rasters` | `forest_dieback.gee` |
| 2. Indices spectraux | *(calculés par l'étape 4)* | `forest_dieback.indices` |
| 3. Référence FORDEAD | `make fordead` | `scripts/run_fordead.py` |
| 4. Jeu d'entraînement | `make dataset` | `forest_dieback.dataset` |
| 5. Entraînement | `make train` | `forest_dieback.train` |
| 6. Évaluation | `make evaluate` | `forest_dieback.evaluate` |
| 7. Frugalité | `make benchmark` | `forest_dieback.export` |

Tous les paramètres (zone, dates, bandes, hyperparamètres) sont dans [`configs/default.yaml`](configs/default.yaml).
La marche à suivre de l'étape 1, du contrôle de zone au masque BD Forêt actif dans Earth Engine,
est détaillée dans [`docs/EXTRACTION.md`](docs/EXTRACTION.md).

### Extraction Sentinel-2

Exporter chaque image brute de la zone représenterait environ 1 300 dates et 200 Go. Tout est donc réduit côté Earth Engine :

- composites médians sur une grille de 10 jours, après masquage Cloud Score+ ;
- cinq bandes seulement (B4, B8, B8A, B11, B12), suffisantes pour CRSWIR, NDVI et NDWI, en entiers 16 bits ;
- pixels limités au masque des épicéas (BD Forêt V2 envoyée en asset GEE) ou, à défaut, aux arbres
  d'ESA WorldCover, qui couvrent 84 % de la zone contre 22 % pour les peuplements résineux ;
- images restreintes aux tuiles MGRS d'une seule zone UTM (`sentinel2.tiles`) : quatre tuiles voient les Hautes-Vosges
  et livrent les mêmes acquisitions, n'en garder que deux divise le calcul par deux sans perdre une seule date et
  évite de reprojeter des réflectances à la volée.

Deux sorties, une tâche Drive par année :

| Commande | Sortie | Usage |
| --- | --- | --- |
| `extract_s2.py samples` | CSV des séries de 5 000 pixels tirés dans le masque (~10 Mo par an) | entraînement, figures |
| `extract_s2.py points --file …` | CSV des séries aux points d'un fichier (ex. points de contrôle) | évaluation |
| `extract_s2.py rasters` | une pile GeoTIFF par année (bandes `AAAAMMJJ_Bx`) | carte des détections |

`extract_s2.py check` affiche le nombre d'images, la part de la zone couverte par le masque et le volume attendu, sans rien exporter. L'option `--coverage` mesure en plus la part de pixels clairs de chaque composite : c'est ce chiffre qui dit si la série est assez continue pour qu'une rupture y soit détectable.

### Jeu d'entraînement

Une fois les CSV rapatriés de Drive dans `data/raw/s2/`, `make dataset` les assemble en
`data/processed/dataset.npz` : lecture des tables longues, empilement sur la grille
régulière des composites, passage aux indices, rejet des valeurs hors plage physique
(`indices_range` : les ombres de relief hivernales font exploser le CRSWIR), comblement
des trous nuageux par interpolation, découpage spatial par blocs.

```bash
make dataset                      # étiquettes comprises, si les cartes FORDEAD sont là
uv run python scripts/build_dataset.py --no-labels     # cube seul, pour inspecter
```

Les étiquettes viennent des cartes FORDEAD : ce sont des **étiquettes faibles**, qui
reprennent les erreurs de la méthode qui les a produites. Les pixels en sol nu sortent du
jeu plutôt que d'être étiquetés, et les séries s'arrêtent avec les cartes, fin 2023
(`labels.dieback_*`). Sur la zone : 4 701 pixels, 227 attaqués, 259 composites.

## Installation

```bash
git clone https://github.com/frankkubler/forest-dieback-s2.git
cd forest-dieback-s2
uv sync --all-extras          # crée .venv (Python 3.11, PyTorch CPU) — ou : make install
make demo                     # pipeline complet sur données synthétiques

# Google Earth Engine
uv run earthengine authenticate
export GEE_PROJECT=<ton-projet-gee>   # ou renseigner gee.project dans configs/default.yaml
make extract-check
```

L'environnement est géré par [uv](https://docs.astral.sh/uv/) : toutes les commandes passent par `uv run`, sans activer de venv.

Avec Docker :

```bash
docker build -t forest-dieback-s2 .
docker run --rm -v $PWD/data:/app/data forest-dieback-s2 make train RUN=
```

## Structure

```
configs/            paramètres du pipeline (zone, dates, modèle)
src/forest_dieback/ code du package (GEE, indices, dataset, modèle, entraînement, évaluation, export)
scripts/            points d'entrée en ligne de commande
tests/              tests unitaires (pytest), lancés par la CI
docs/               feuille de route et figures du README
data/               données locales, non versionnées
```

## Licence

Code sous licence MIT. Les données FORDEAD sont sous licence Etalab 2.0 et les données IGN
sous licence ouverte Etalab. Le package [`fordead`](https://gitlab.com/fordead/fordead_package),
appelé par `make fordead`, est sous GPL-3 : c'est une dépendance facultative (extra `fordead`),
utilisée comme outil et non intégrée au code de ce dépôt.
