# Feuille de route

Environ 10 soirées de 2 à 3 h. Le jalon 1 suffit pour citer le projet dans une candidature ; le jalon 2 prépare l'entretien technique.

## Jalon 1 — publiable (4 soirées)

La marche à suivre détaillée de ces étapes est dans [EXTRACTION.md](EXTRACTION.md).

- [x] Compte et projet Google Earth Engine
- [x] Choix de la zone, vérification avec `make extract-check`
- [x] Masque épicéa BD Forêt envoyé en asset GEE (`make spruce-mask`)
- [x] Export des séries de pixels (`make extract-samples`) et des piles annuelles (`make extract-rasters`)
- [x] Cartes scolytes FORDEAD téléchargées, étiquettes faibles de la zone
- [x] Jeu d'entraînement et découpage spatial par blocs (`make dataset`)
- [x] Indices et figure pixel sain / pixel attaqué (`scripts/plot_pixel.py`)
- [x] README illustré, dépôt public

## Jalon 2 — entretien technique (6 soirées)

- [x] TempCNN : entraînement et premiers résultats (`make train`)
- [ ] Exécution de `fordead` sur la zone pour une référence recalculée (`make fordead`)
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

Une fois l'asset ingéré, Earth Engine en mesure 88,1 km² sur 881 237 pixels à
10 m, pour 374 entités comme le GeoPackage local : l'écart de 0,9 % avec la
géométrie est celui de la rasterisation.

## Premiers résultats du TempCNN

| Chiffre | Valeur |
| --- | --- |
| Précision / rappel / F1 (test, 699 pixels) | 0,45 / 0,81 / 0,58 |
| Paramètres | 174 593 |
| Taille ONNX | 0,70 Mo |
| Inférence CPU | 160 µs par pixel, 160 s pour 100 km² |

La tête dense concentrait d'abord 99 % des 4,3 millions de paramètres : elle
aplatissait les 259 composites, soit 16 576 entrées. Un pooling temporel à
huit pas la détache de la longueur de série et divise le modèle par 24, sans
perte nette de qualité — le F1 de validation oscillant de 0,33 à 0,51 d'une
époque à l'autre, les deux architectures ne se départagent pas sur ce seul
chiffre.

`AdaptiveAvgPool1d` ne s'exporte pas en ONNX quand la sortie ne divise pas
l'entrée : le pooling se fait donc à pas fixe, la longueur de sortie étant
mesurée à la construction du modèle.

Reste à traiter : le modèle surapprend (la perte tombe pendant que le F1 de
validation plafonne) et le jeu de validation ne compte qu'une trentaine de
pixels attaqués, ce qui rend son F1 très instable.

## Référence FORDEAD : cartes publiées ou exécution locale

Le jalon 1 s'appuie sur les [cartes publiées](https://doi.org/10.57745/8LJGQ9),
qui couvrent la zone de 2018 à 2023 et fournissent les étiquettes. Faire
tourner `fordead` sur la zone donnerait une référence recalculée avec les
mêmes paramètres des deux côtés, mais le package demande un environnement
conda séparé et des tuiles Sentinel-2 au format THEIA, que les exports GEE ne
remplacent pas : plusieurs centaines de dates à télécharger. Ce chantier est
reporté au jalon 2, la comparaison restant possible entre-temps sur les
cartes publiées.

## Volumes exportés

Les 20 tâches ont abouti en 2 h 31 pour **3,93 Go** sur Drive, à comparer aux
14,6 Go bruts annoncés par `extract-check` :

| Sortie | Estimation brute | Réel | Rapport |
| --- | --- | --- | --- |
| 10 piles annuelles (GeoTIFF) | 14,6 Go | **3,86 Go** | 26 % |
| 10 séries de pixels (CSV) | au plus 108 Mo | **73,7 Mo** | 68 % |

L'estimation porte sur la grille pleine et ignore le masque : 78 % des pixels
d'une pile sont nuls et se compressent presque entièrement. Les piles vont de
240 Mo (2017, où Sentinel-2B n'opère qu'à partir de mars, d'où des composites
vides) à 468 Mo (2025).

## Jeu d'entraînement

| Chiffre | Valeur |
| --- | --- |
| Pixels | 4 701, dont 227 attaqués (4,8 %) |
| Pixels écartés | 299, en sol nu : classe trop ambiguë pour être étiquetée |
| Composites | 259, de janvier 2017 à décembre 2023 |
| Observations claires | 73,9 % des couples pixel-date, le reste interpolé |
| Première anomalie | de mai 2018 à mai 2023 |
| Découpage par blocs de 2 km | 3 336 train, 666 val, 699 test |

Recalées sur la date de première anomalie, les deux populations se
superposent avant la détection et divergent aussitôt après : le CRSWIR médian
des pixels attaqués passe de 0,75 à 0,90 quand celui des pixels sains reste
à 0,78. En temps calendaire, ce signal est invisible, les attaques s'étalant
sur cinq ans.

## Sources

- [Documentation du package fordead (INRAE TETIS)](https://fordead.gitlab.io/fordead_package/latest/)
- [Présentation fordead sur Theia](https://www.theia-land.fr/?p=19564)
- [Cartographie des scolytes par la méthode fordead, juin 2023](https://doi.org/10.57745/8LJGQ9)
- [Usage de FORDEAD par la DSF et l'ONF sur le massif jurassien (webinaire 2024)](https://www.theia-land.fr/wp-content/uploads/2024/03/26032024_Webinaire_ART_Theia_FORDEAD-ONF.pdf)
