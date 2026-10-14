# Feuille de route

Environ 10 soirées de 2 à 3 h. Le jalon 1 suffit pour citer le projet dans une candidature ; le jalon 2 prépare l'entretien technique.

## Jalon 1 — publiable (4 soirées)

- [x] Compte et projet Google Earth Engine
- [ ] Choix de la zone, export des séries Sentinel-2 masquées (`make extract`)
- [ ] Indices et figure pixel sain / pixel attaqué (`scripts/plot_pixel.py`)
- [ ] Exécution de `fordead` sur la zone, carte des anomalies (`make fordead`)
- [ ] README illustré, dépôt public

## Jalon 2 — entretien technique (6 soirées)

- [ ] Jeu d'entraînement et découpage spatial par blocs (script `build_dataset` à écrire)
- [ ] TempCNN : entraînement et premiers résultats (`make train`)
- [ ] Photo-interprétation des ~200 points de contrôle et comparaison avec FORDEAD (`make evaluate`)
- [ ] Export ONNX, mesures de frugalité, Docker et CI (`make export benchmark`)
- [ ] Option Sentinel-1 ou Transformer temporel, puis mise à jour du README

## Sources

- [Documentation du package fordead (INRAE TETIS)](https://fordead.gitlab.io/fordead_package/latest/)
- [Présentation fordead sur Theia](https://www.theia-land.fr/?p=19564)
- [Cartographie des scolytes par la méthode fordead, juin 2023](https://doi.org/10.57745/8LJGQ9)
- [Usage de FORDEAD par la DSF et l'ONF sur le massif jurassien (webinaire 2024)](https://www.theia-land.fr/wp-content/uploads/2024/03/26032024_Webinaire_ART_Theia_FORDEAD-ONF.pdf)
