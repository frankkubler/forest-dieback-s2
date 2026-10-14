# Données locales (non versionnées)

```
data/
├── raw/
│   ├── s2/                    exports GEE : piles GeoTIFF annuelles, CSV de séries,
│   │                          ordre des bandes (*_bands.json)
│   ├── s2_theia/              tuiles S2 THEIA pour fordead
│   ├── bdforet/               BD Forêt V2 extraite (un dossier par département)
│   ├── fordead/               cartes scolytes FORDEAD (doi:10.57745/8LJGQ9)
│   ├── bdforet_epicea.gpkg    peuplements sapin-épicéa de la zone (+ .zip pour GEE)
│   └── control_points.gpkg    ~200 points photo-interprétés (BD ORTHO)
├── interim/                   cube xarray, sorties fordead
└── processed/dataset.npz      séries par pixel : series (N,T,C), labels, x, y
```
