"""Requêtes sur les tables du Data-Lab : application des filtres (région → préfecture → commune → canton) et tableaux par niveau territorial."""
from __future__ import annotations

import numpy as np
import pandas as pd

from data import loader as D

LEVELS = ["Région", "Préfecture", "Commune", "Canton"]


def _hier() -> pd.DataFrame:
    return D.load_tables()["hier"]


def region_of_pref(f: dict, pref_raw: str) -> str | None:
    h = _hier()
    r = h[h.pref_raw == pref_raw][f["region_col"]]
    return r.iloc[0] if len(r) else None


def appliquer(df: pd.DataFrame, f: dict, niveau: str, pref_col: str = "prefecture", com_col: str = "commune", use_commune: bool = True) -> pd.DataFrame:
    """Restreint une table de territoires aux filtres actifs. `niveau` : region | prefecture | commune | canton.
    Les niveaux plus fins que le territoire demandé restent des contraintes (un filtre « préfecture » restreint aussi les communes)."""
    h = _hier()
    rc = f["region_col"]
    com = f.get("commune") if use_commune else None
    if niveau == "region":
        d = df[df.decoupage == f["decoupage"]]
        code = f["region"]
        if not code and f.get("prefecture"):
            code = region_of_pref(f, f["prefecture"])
        if not code and com:
            code = region_of_pref(f, h[h.com_raw == com].pref_raw.iloc[0])
        return d[d.code_region == code] if code else d
    d = df
    if f.get("region"):
        d = d[d[rc] == f["region"]]
    if f.get("prefecture"):
        d = d[d[pref_col] == f["prefecture"]]
    if com:
        if niveau in ("commune", "canton"):
            d = d[d[com_col] == com]
        elif niveau == "prefecture":
            d = d[d[pref_col] == h[h.com_raw == com].pref_raw.iloc[0]]
    if niveau == "canton" and f.get("canton"):
        d = d[d.canton == f["canton"]]
    return d


def titre_selection(f: dict, defaut: str = "Togo") -> str:
    """Libellé court du territoire sélectionné (pour titres et annotations)."""
    for k in ("canton", "com_nom", "pref_nom", "region_label"):
        if f.get(k):
            return f[k]
    return defaut


def niveau_selection(f: dict) -> str:
    for k, lab in (("canton", "canton"), ("commune", "commune"), ("prefecture", "préfecture"), ("region", "région")):
        if f.get(k):
            return lab
    return "pays"


# ───────────────────────── démographie ─────────────────────────
def demo_frame(f: dict, level: str) -> pd.DataFrame:
    """Tableau d'un niveau : id, Territoire, Préfecture, Région, Population, Poids (%), Rang (+ positions pour les bulles)."""
    T = D.load_tables()
    pn = T["pref_nom"]
    labs = D.labels(f["decoupage"])
    rc = f["region_col"]
    if level == "Région":
        d = appliquer(T["region"], f, "region")
        out = pd.DataFrame(dict(id=d.code_region, Territoire=d.nom, Préfecture="", Région=d.nom, Population=d.population_2022, Poids=d.poids_national_pct, code_region=d.code_region))
    elif level == "Préfecture":
        d = appliquer(T["prefecture"], f, "prefecture", pref_col="prefecture_raw")
        out = pd.DataFrame(dict(id=d.prefecture_id, Territoire=d.prefecture_nom, Préfecture=d.prefecture_nom, Région=d[rc].map(labs), Population=d.population_2022,
                                Poids=d.poids_national_pct, prefecture_raw=d.prefecture_raw))
    elif level == "Commune":
        d = appliquer(T["commune"], f, "commune")
        out = pd.DataFrame(dict(id=d.territoire_id, Territoire=d.nom, Préfecture=d.prefecture.map(pn), Région=d[rc].map(labs), Population=d.population_2022, Poids=d.poids_national_pct,
                                prefecture_raw=d.prefecture, commune_raw=d.commune, fusionnee=d.commune_fusionnee))
        g = T["canton_geo"].groupby("commune").apply(lambda x: pd.Series(dict(lat=np.average(x.lat, weights=x.population_2022), lon=np.average(x.lon, weights=x.population_2022))), include_groups=False)
        out = out.merge(g, left_on="commune_raw", right_index=True, how="left")                                 # position approchée = barycentre des cantons positionnés
    else:
        d = appliquer(T["canton"][T["canton"].niveau_feuille == "canton"], f, "canton")
        out = pd.DataFrame(dict(id=d.territoire_id, Territoire=d.nom, Préfecture=d.prefecture.map(pn), Commune=d.commune, Région=d[rc].map(labs), Population=d.population_2022,
                                Poids=d.poids_national_pct, petit=d.petit_canton, prefecture_raw=d.prefecture))
        out = out.merge(T["canton_geo"][["territoire_id", "lat", "lon"]].rename(columns={"territoire_id": "id"}), on="id", how="left")
    out["Rang"] = out.Population.rank(ascending=False, method="min").astype("Int64")
    return out.sort_values("Population", ascending=False).reset_index(drop=True)


def demo_stats(com: pd.DataFrame) -> dict:
    """Médiane, moyenne, dispersion, Top 10 et Gini des tailles de communes."""
    from utils.demography import gini, part_top
    p = com.population_2022.dropna()
    return dict(n=len(p), mediane=p.median(), moyenne=p.mean(), ecart_type=p.std(), min=p.min(), max=p.max(), gini=gini(p) if len(p) > 2 else np.nan,
                top10_pct=part_top(p, 10) if len(p) >= 10 else (100.0 if len(p) else np.nan), cv=(p.std() / p.mean()) if len(p) > 1 else np.nan)


# ───────────────────────── cartes ─────────────────────────
def poly_frame(df: pd.DataFrame, level: str, f: dict, value: str = "Valeur", label: str = "Territoire") -> pd.DataFrame:
    """Prépare un tableau pour une carte à polygones : une ligne par polygone du template.
    Région : chaque préfecture prend la valeur de sa région (mosaïque) ; Préfecture : Golfe est dupliqué sur ses 2 polygones."""
    h = _hier()
    rc = f["region_col"]
    if level == "Région":
        rows = []
        for _, r in df.iterrows():
            for pref in h[h[rc] == r["id"]].pref_raw.unique():
                for nm in D.polygons_of_prefecture().get(pref, []):
                    rows.append({"code": nm, "Territoire": r[label], "Valeur": r[value], "tip": r[label], "id": r["id"]})
        return pd.DataFrame(rows)
    d = df.rename(columns={"prefecture_raw": "praw"})
    rows = []
    for _, r in d.iterrows():
        for nm in D.polygons_of_prefecture().get(r["praw"], []):
            rows.append({"code": nm, "Territoire": r[label], "Valeur": r[value], "tip": r[label], "id": r["id"]})
    return pd.DataFrame(rows)


def classes_and_legend(values: pd.Series, palette, fmt, higher_is_first: bool = True):
    from components import maps
    return maps.legend_from_values(values, palette, fmt, higher_is_first=higher_is_first)


def csv_bytes(df: pd.DataFrame) -> bytes:
    """Export exactement conforme à la sélection affichée (UTF-8 avec BOM pour Excel)."""
    return df.to_csv(index=False).encode("utf-8-sig")
