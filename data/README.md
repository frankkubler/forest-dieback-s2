# Données locales (non versionnées)

```
data/
├── raw/
│   ├── s2/                    exports GEE (GeoTIFF par date)
│   ├── s2_theia/              tuiles S2 THEIA pour fordead
│   ├── fordead/               cartes scolytes FORDEAD (doi:10.57745/8LJGQ9)
│   ├── bdforet_epicea.gpkg    peuplements d'épicéas extraits de la BD Forêt V2
│   └── control_points.gpkg    ~200 points photo-interprétés (BD ORTHO)
├── interim/                   cube xarray, sorties fordead
└── processed/dataset.npz      séries par pixel : series (N,T,C), labels, x, y
```
