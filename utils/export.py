"""Exports de l'étape 2 : tables pré-agrégées lues par l'application (Parquet) + CSV de traçabilité."""
import json
import datetime as dt
import pandas as pd
from .io import OUT
from .demography import compute_demography
from .evolution import build_crosswalk_2010_2022


def export_demo_evolution(dim: pd.DataFrame, dim10: pd.DataFrame, out_dir=OUT) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    D = compute_demography(dim)
    E = build_crosswalk_2010_2022(dim, dim10)
    tables = {"fact_commune": D["commune"], "canton_2022": D["canton"], "demographie_prefecture": D["prefecture"], "demographie_region": D["region"],
              "crosswalk_2010_2022": E["crosswalk"], "population_2010_2022": E["comparaison"], "concentration_population": D["concentration"],
              "distribution_taille": D["distribution"]}
    tailles = {}
    for nom, df in tables.items():
        df.to_csv(out_dir / f"{nom}.csv", index=False, encoding="utf-8"); tailles[f"{nom}.csv"] = (out_dir / f"{nom}.csv").stat().st_size
        if nom not in ("concentration_population", "distribution_taille"):
            df.to_parquet(out_dir / f"{nom}.parquet", index=False); tailles[f"{nom}.parquet"] = (out_dir / f"{nom}.parquet").stat().st_size
    (out_dir / "kpi_demographie.json").write_text(json.dumps(D["kpi"], ensure_ascii=False, indent=2), encoding="utf-8")
    version = dict(date_construction=dt.date.today().isoformat(), sources="RGPH 2010 et 2022 (listes plates), CEET/TdE (extraits 2024), fichiers observationdata",
                   nb_prefectures=int((dim.niveau == "prefecture").sum()), nb_communes_lignes=int((dim.niveau == "commune").sum()), nb_cantons=int((dim.niveau == "canton").sum()))
    (out_dir / "data_version.json").write_text(json.dumps(version, ensure_ascii=False, indent=2), encoding="utf-8")
    return dict(D=D, E=E, tailles=tailles)
