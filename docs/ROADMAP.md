# Feuille de route

Environ 10 soirées de 2 à 3 h. Le jalon 1 suffit pour citer le projet dans une candidature ; le jalon 2 prépare l'entretien technique.

## Jalon 1 — publiable (4 soirées)

- [x] Compte et projet Google Earth Engine
- [x] Choix de la zone, vérification avec `make extract-check`
- [ ] Masque épicéa BD Forêt envoyé en asset GEE (`make spruce-mask`, voir [EXTRACTION.md](EXTRACTION.md))
- [ ] Export des séries de pixels (`make extract-samples`) et des piles annuelles (`make extract-rasters`)
- [ ] Indices et figure pixel sain / pixel attaqué (`scripts/plot_pixel.py`)
- [ ] Exécution de `fordead` sur la zone, carte des anomalies (`make fordead`)
- [ ] README illustré, dépôt public

## Jalon 2 — entretien technique (6 soirées)

- [ ] Jeu d'entraînement et découpage spatial par blocs (script `build_dataset` à écrire)
- [ ] TempCNN : entraînement et premiers résultats (`make train`)
- [ ] Photo-interprétation des ~200 points de contrôle et comparaison avec FORDEAD (`make evaluate`)
- [ ] Export ONNX, mesures de frugalité, Docker et CI (`make benchmark`)
- [ ] Option Sentinel-1 ou Transformer temporel, puis mise à jour du README

## Zone retenue

Carré de 20 × 20 km des vallées de la Thur et de la Doller, vérifié avec
`extract_s2.py check --coverage` :

| Chiffre | Valeur |
| --- | --- |
| Emprise | 2017 × 2004 pixels à 10 m |
| Tuiles MGRS | quatre touchent la zone ; `32TLT` + `32ULU` la couvrent à 100 % |
| Images S2 (2017–2026) | 2 890 après filtre de tuiles, contre 5 774 sans |
| Composites | 37 par an sur une grille de 10 jours |
| Couverture claire 2022 | 86 % en moyenne, 89 % d'avril à septembre, 5 composites sur 37 sous 50 % |
| Couverture claire 2023 | 72 % en moyenne, 79 % d'avril à septembre, 12 composites sur 37 sous 50 % |

La série est donc assez continue sur la saison de végétation, qui porte le
signal du dépérissement.

## Masque résineux

La BD Forêt V2 des départements 68, 88 et 90 couvre la zone. Sur ses
324 km² de forêt, les essences se répartissent ainsi :

| Essence | Surface dans la zone | Part de la zone |
| --- | --- | --- |
| Mixte (feuillus et conifères) | 133,1 km² | 33,3 % |
| Sapin, épicéa | 67,7 km² | 16,9 % |
| Hêtre | 38,3 km² | 9,6 % |
| Feuillus | 38,1 km² | 9,5 % |
| Conifères non différenciés | 21,2 km² | 5,3 % |

Le masque retient « Sapin, épicéa » et « Conifères » (`labels.spruce_essences`),
soit 88,9 km², 22 % de la zone, contre 84 % pour les arbres d'ESA WorldCover.
« Mixte » est écarté bien qu'il pèse le double : la plupart de ses pixels n'ont
pas d'épicéa et bruiteraient autant les étiquettes FORDEAD que l'entraînement.

## Sources

- [Documentation du package fordead (INRAE TETIS)](https://fordead.gitlab.io/fordead_package/latest/)
- [Présentation fordead sur Theia](https://www.theia-land.fr/?p=19564)
- [Cartographie des scolytes par la méthode fordead, juin 2023](https://doi.org/10.57745/8LJGQ9)
- [Usage de FORDEAD par la DSF et l'ONF sur le massif jurassien (webinaire 2024)](https://www.theia-land.fr/wp-content/uploads/2024/03/26032024_Webinaire_ART_Theia_FORDEAD-ONF.pdf)
