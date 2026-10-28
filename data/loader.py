"""Couche données du tableau de bord : chargement (mis en cache) des tables du Data-Lab, listes de filtres en cascade, géométries.

Toutes les valeurs affichées proviennent de `outputs/data/` (produit par `tools/build_tables.py`). Aucune donnée de démonstration.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from utils.formats import ND, fmt_dec, fmt_int, fmt_pct, fmt_pp, fmt_signe, liste_fr      # noqa: F401  (ré-exportés pour les composants)
from utils.io import OUT
from utils.territoire import norm

ROOT = Path(__file__).resolve().parents[1]
GEO = ROOT / "data" / "geo"

ALL_REGIONS, ALL_PREFS, ALL_COMMUNES, ALL_CANTONS = "Toutes les régions", "Toutes les préfectures", "Toutes les communes", "Tous les cantons"
DEC6, DEC5 = "6 régions 2022", "5 régions historiques"
DECOUPAGES = [DEC6, DEC5]
ORDRE = ["SAVANES", "KARA", "CENTRALE", "PLATEAUX", "MARITIME", "DAGL"]
LABEL6 = {"SAVANES": "Savanes", "KARA": "Kara", "CENTRALE": "Centrale", "PLATEAUX": "Plateaux", "MARITIME": "Maritime", "DAGL": "Grand Lomé (DAGL)"}
LABEL5 = {**LABEL6, "MARITIME": "Maritime (avec Grand Lomé)"}
ANNEES_ELEC = [2021, 2020, 2019, 2018]
ANNEES_EC = list(range(2014, 2023))
TAUX_NATIONAL = {2018: 45.09, 2021: 57.82}                    # taux PUBLIÉS (non recalculables à partir des unités)

# Villes repères (positions approximatives, pour l'orientation sur les cartes uniquement)
CITIES = {"Lomé": (6.137, 1.212), "Kara": (9.551, 1.186), "Sokodé": (8.983, 1.133), "Atakpamé": (7.533, 1.133), "Dapaong": (10.863, 0.208),
          "Kpalimé": (6.900, 0.633), "Tsévié": (6.426, 1.213), "Aného": (6.229, 1.598), "Mango": (10.367, 0.467)}

TABLES = {"dim": "dim_territoire", "commune": "fact_commune", "canton": "canton_2022", "canton_geo": "canton_geo", "prefecture": "fact_prefecture",
          "unite": "fact_unite_electrique", "region": "demographie_region", "crosswalk": "crosswalk_2010_2022", "comparaison": "population_2010_2022",
          "agences": "agences_geo", "ec": "etat_civil_long", "idn": "identite_long", "reco": "recommandations", "rob": "ipt_robustesse",
          "elec_long": "electricite_long", "elec_reg": "electricite_regions"}
CSV_ONLY = {"scen": "ipt_scenarios", "comp": "ipt_composantes", "corr": "ipt_correlation_spearman", "quality": "data_quality_tests", "anomalies": "anomaly_log",
            "distribution": "distribution_taille", "concentration": "concentration_population",
            "recon_nat": "reconciliation_national", "recon_reg": "reconciliation_regions"}


@st.cache_data(show_spinner=False)
def load_tables() -> dict:
    """Charge toutes les tables du Data-Lab (Parquet quand disponible) + métadonnées ; construit la hiérarchie des filtres."""
    T = {k: (pd.read_parquet(OUT / f"{v}.parquet") if (OUT / f"{v}.parquet").exists() else pd.read_csv(OUT / f"{v}.csv")) for k, v in TABLES.items()}
    T.update({k: pd.read_csv(OUT / f"{v}.csv") for k, v in CSV_ONLY.items()})
    T["kpi"] = json.loads((OUT / "kpi_demographie.json").read_text(encoding="utf-8"))
    T["meta"] = json.loads((OUT / "ipt_meta.json").read_text(encoding="utf-8"))
    T["recon_res"] = json.loads((OUT / "reconciliation_resume.json").read_text(encoding="utf-8"))
    T["version"] = json.loads((OUT / "data_version.json").read_text(encoding="utf-8"))
    c = T["commune"]
    pref_nom = dict(zip(T["prefecture"].prefecture_raw, T["prefecture"].prefecture_nom))
    T["hier"] = pd.DataFrame(dict(region_6=c.region_6, region_5=c.region_5, pref_raw=c.prefecture, pref_nom=c.prefecture.map(pref_nom),
                                  com_raw=c.commune, com_nom=c.nom)).reset_index(drop=True)
    T["pref_nom"] = pref_nom
    T["volume_mo"] = sum(((OUT / f"{v}.parquet") if (OUT / f"{v}.parquet").exists() else (OUT / f"{v}.csv")).stat().st_size for v in TABLES.values()) / 1e6
    return T


# ───────────────────────── listes de filtres en cascade ─────────────────────────
def labels(decoupage: str) -> dict:
    return LABEL6 if decoupage == DEC6 else LABEL5


def region_col(decoupage: str) -> str:
    return "region_6" if decoupage == DEC6 else "region_5"


def regions(decoupage: str = DEC6) -> list[str]:
    T = load_tables()
    present = set(T["hier"][region_col(decoupage)])
    return [labels(decoupage)[c] for c in ORDRE if c in present]


def region_code(decoupage: str, label: str | None) -> str | None:
    inv = {v: k for k, v in labels(decoupage).items()}
    return inv.get(label)


def prefectures_of(decoupage: str, region: str | None) -> list[str]:
    """Noms d'affichage des préfectures d'une région (code), toutes si `region` est None."""
    h = load_tables()["hier"]
    if region:
        h = h[h[region_col(decoupage)] == region]
    return sorted(h.pref_nom.unique())


def communes_of(decoupage: str, region: str | None, pref_nom: str | None) -> list[str]:
    h = load_tables()["hier"]
    if region:
        h = h[h[region_col(decoupage)] == region]
    if pref_nom:
        h = h[h.pref_nom == pref_nom]
    return sorted(h.com_nom.unique())


def cantons_of(commune_nom: str | None, pref_nom: str | None, region: str | None, decoupage: str = DEC6) -> list[str]:
    T = load_tables()
    c = T["canton"]
    rc = region_col(decoupage)
    if region:
        c = c[c[rc] == region]
    if pref_nom:
        c = c[c.prefecture == T["prefecture"].set_index("prefecture_nom").prefecture_raw.get(pref_nom)]
    if commune_nom:
        c = c[c.commune == T["commune"].set_index("nom").commune.get(commune_nom)]
    return sorted(c.nom.unique())


def raw_of(kind: str, nom: str | None) -> str | None:
    """Nom d'affichage → libellé brut du référentiel (préfecture ou commune)."""
    if not nom:
        return None
    h = load_tables()["hier"]
    if kind == "prefecture":
        r = h[h.pref_nom == nom].pref_raw
    else:
        r = h[h.com_nom == nom].com_raw
    return r.iloc[0] if len(r) else None


# ───────────────────────── géométries ─────────────────────────
@st.cache_resource(show_spinner=False)
def regions_geojson() -> dict:
    return json.loads((GEO / "togo_regions.geojson").read_text(encoding="utf-8"))


@st.cache_resource(show_spinner=False)
def prefectures_geojson() -> dict:
    return json.loads((GEO / "togo_prefectures.geojson").read_text(encoding="utf-8"))


_ALIAS_POLY = {"PLAINE DU MO": "MO", "NAKI OUEST": "KPENDJAL OUEST", "LOME COMMUNE": "GOLFE"}


@st.cache_data(show_spinner=False)
def polygons_of_prefecture() -> dict:
    """Libellé brut de préfecture 2022 → noms des polygones du template (Golfe = 2 polygones : Golfe + Lomé Commune)."""
    T = load_tables()
    raw_by_norm = {norm(r): r for r in T["prefecture"].prefecture_raw}
    out: dict = {}
    for ft in prefectures_geojson()["features"]:
        nm = ft["properties"]["name"]
        k = _ALIAS_POLY.get(norm(nm), norm(nm))
        if k in raw_by_norm:
            out.setdefault(raw_by_norm[k], []).append(nm)
    return out


def expand_to_polygons(df: pd.DataFrame, raw_col: str = "prefecture_raw") -> pd.DataFrame:
    """Une ligne par polygone (colonne `code` = nom du polygone) : une préfecture à 2 polygones est dupliquée."""
    mp = polygons_of_prefecture()
    rows = []
    for _, r in df.iterrows():
        for nm in mp.get(r[raw_col], []):
            d = r.to_dict()
            d["code"] = nm
            rows.append(d)
    return pd.DataFrame(rows)
