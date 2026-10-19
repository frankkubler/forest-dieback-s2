# Du contrôle de zone au masque résineux

Marche à suivre complète de l'étape 1, entre `make extract-check` et un masque
BD Forêt actif dans Earth Engine. Les étapes 2 à 4 sont manuelles : la BD Forêt
se télécharge par département, et Earth Engine n'ingère pas un fichier local
sans passer par son interface web.

Les valeurs données en exemple sont celles de la zone configurée, les vallées
de la Thur et de la Doller.

## 1. Vérifier la zone

```bash
make extract-check
```

Trois chiffres décident :

- **l'emprise** (2017 × 2004 pixels à 10 m) doit correspondre à la zone voulue ;
- **le nombre d'images** doit rester proportionné. Plusieurs tuiles MGRS se
  recouvrent sur une même zone et livrent les mêmes acquisitions ;
  `sentinel2.tiles` n'en garde qu'une zone UTM (voir le README) ;
- **le volume** annoncé des rasters, qui dimensionne les exports Drive.

La continuité de la série se mesure à part, car elle coûte une requête par
année :

```bash
uv run python scripts/extract_s2.py check --coverage --years 2022 2023
```

Une couverture d'avril à septembre au-dessus de 75 % suffit : c'est la saison
qui porte le signal du dépérissement. En dessous, élargir `composite_days` ou
abaisser `sentinel2.clear_threshold` avant d'aller plus loin.

## 2. Trouver les départements à télécharger

La BD Forêt V2 est livrée par département, et une zone de montagne chevauche
souvent plusieurs limites. Interroger les quatre coins de la bbox :

```bash
for pt in '6.88:47.75' '7.15:47.75' '6.88:47.93' '7.15:47.93'; do
  lon="${pt%%:*}"; lat="${pt##*:}"
  curl -s "https://geo.api.gouv.fr/communes?lon=${lon}&lat=${lat}&fields=nom,departement"
  echo
done
```

Pour la zone configurée : **68** (Haut-Rhin), **88** (Vosges) au nord-ouest et
**90** (Territoire de Belfort) au sud-ouest. Ne retenir que le Haut-Rhin
tronquerait le masque sur tout le versant ouest de la crête.

## 3. Télécharger la BD Forêt V2

Par l'interface : <https://geoservices.ign.fr/bdforet>. En ligne de commande,
la Géoplateforme publie un flux Atom qui donne l'URL, la taille et le MD5 de
chaque archive :

```bash
NOM=BDFORET_2-0__SHP_LAMB93_D068_2014-04-01
curl -sSfL "https://data.geopf.fr/telechargement/resource/BDFORET/$NOM" \
  | grep -oE 'href="[^"]+\.7z"|<content>[0-9a-f]{32}</content>'
```

Le champ `<content>` porte le MD5 de l'archive, à vérifier après
téléchargement avec `md5sum`. Les archives de la zone :

| Archive | Taille | MD5 |
| --- | --- | --- |
| `BDFORET_2-0__SHP_LAMB93_D068_2014-04-01.7z` | 11,7 Mo | `5fe297539009de1204b4668d4c571678` |
| `BDFORET_2-0__SHP_LAMB93_D088_2015-04-01.7z` | 26,9 Mo | `5b2aa788eb172e53bd797c56d81a986a` |
| `BDFORET_2-0__SHP_LAMB93_D090_2015-06-01.7z` | 3,9 Mo | `237b31f9b85bb2bf309cced16320bfa3` |

> `urllib` reçoit un **403** de la Géoplateforme : utiliser `curl` ou `wget`.

Les éditions datent de 2014 et 2015, soit avant les crises de scolytes de
2018-2020. Des peuplements cartographiés en épicéa ont donc pu être coupés
depuis, et les plantations postérieures manquent. Ce décalage ne gêne pas la
détection, mais interdit de lire la surface du masque comme une surface
d'épicéa actuelle.

## 4. Extraire les archives

```bash
7z x -odata/raw/bdforet data/raw/bdforet/BDFORET_2-0__SHP_LAMB93_D068_2014-04-01.7z
```

`make spruce-mask` cherche récursivement les `*.shp` sous `data/raw/bdforet/`.
La couche utile de chaque livraison est `FORMATION_VEGETALE.shp` :

```
data/raw/bdforet/BDFORET_2-0__SHP_LAMB93_D068_2014-04-01/BDFORET/
  1_DONNEES_LIVRAISON/BDF_2-0_SHP_LAMB93_D068/FORMATION_VEGETALE.shp
```

## 5. Choisir les essences

`labels.spruce_essences` fixe les valeurs du champ `ESSENCE` retenues. Pour
les connaître avant de trancher, il suffit d'une valeur inexistante : le
script refuse et liste les essences des livraisons chargées — celles des
départements entiers, pas seulement de la zone.

```bash
uv run python scripts/prepare_spruce_mask.py \
  $(find data/raw/bdforet -name '*.shp') --values inexistant
```

Dans la zone configurée, « Mixte » pèse le double de « Sapin, épicéa ». Il est
pourtant écarté : la plupart de ses pixels n'ont pas d'épicéa et bruiteraient
autant les étiquettes FORDEAD que l'entraînement. Le détail figure dans la
[feuille de route](ROADMAP.md).

## 6. Construire le masque

```bash
make spruce-mask
```

Deux sorties dans `data/raw/` : un GeoPackage pour les traitements locaux et
`bdforet_epicea.zip`, l'archive shapefile destinée à Earth Engine. Les
polygones sont reprojetés en WGS84, comme l'ingestion l'attend.

## 7. Envoyer le masque dans Earth Engine

**`earthengine upload table` n'accepte que des URL `gs://`** : il ne sait pas
envoyer un fichier local. Deux voies, selon qu'un bucket Cloud Storage est
disponible.

### Sans bucket — Code Editor (recommandé)

1. ouvrir <https://code.earthengine.google.com/> ;
2. onglet **Assets**, bouton **NEW**, puis **Shape files (.shp, .shx, .dbf, .prj, ou .zip)** ;
3. choisir `data/raw/bdforet_epicea.zip` ;
4. donner comme nom d'asset `bdforet_epicea`, dans le projet Cloud configuré ;
5. suivre l'ingestion dans l'onglet **Tasks**.

### Avec un bucket Cloud Storage

```bash
gsutil cp data/raw/bdforet_epicea.zip gs://<bucket>/
uv run earthengine upload table --wait \
  --asset_id=projects/<projet>/assets/bdforet_epicea \
  gs://<bucket>/bdforet_epicea.zip
```

La facturation doit être active sur le projet, ce qui n'est pas nécessaire
pour la voie précédente.

## 8. Activer le masque

Renseigner l'identifiant de l'asset dans `configs/default.yaml` :

```yaml
extraction:
  mask_asset: projects/<projet>/assets/bdforet_epicea
```

## 9. Vérifier que le masque est pris en compte

```bash
make extract-check
```

La ligne « Masque » doit citer l'asset et non plus ESA WorldCover, et la part
de la zone chuter nettement — de 84 % à environ 22 % pour la zone configurée.
Si elle ne bouge pas, l'ingestion n'est pas terminée ou le chemin de l'asset
est faux.

Les exports peuvent alors partir : `make extract-samples`, puis
`make extract-rasters`.
