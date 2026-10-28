"""Reconstruit TOUTES les tables du tableau de bord à partir des données brutes (data/raw) : `python tools/build_tables.py`.

Chaîne : nettoyage → référentiel territorial → démographie → crosswalk 2010-2022 → services de base → IPT → robustesse → recommandations.
Sorties dans outputs/data/ (Parquet pour l'application, CSV pour la traçabilité).
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from utils.io import OUT
from utils.quality import clean_data, export_outputs, run_quality_tests
from utils.export import export_demo_evolution
from utils.priority import (COMPOSANTES, SCENARIO_DEFAUT, SCENARIOS, SEUIL_ROBUSTE, compute_ipt, correlation_composantes, matrice_finale, robustesse)
from utils.services import TAUX_NATIONAL, agences_par_commune, construire_fact_prefecture, construire_fact_unite
from utils import reconciliation as RC
from utils.story import construire_recommandations, verifier_coherence_reco
from utils.territoire import norm


def sauver(df: pd.DataFrame, nom: str, parquet: bool = True) -> None:
    df.to_csv(OUT / f"{nom}.csv", index=False, encoding="utf-8")
    if parquet:
        df.to_parquet(OUT / f"{nom}.parquet", index=False)


def cantons_geolocalises(canton: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Rattache les coordonnées (approximatives) fournies avec le template aux cantons 2022 par noms normalisés (préfecture + canton)."""
    t = pd.read_csv(ROOT / "data" / "geo" / "togo_territoire.csv")
    alias = {"PLAINE DU MO": "MO", "NAKI OUEST": "KPENDJAL OUEST", "LOME COMMUNE": "GOLFE"}
    t["pk"] = t.prefecture.map(norm).replace(alias)
    t["ck"] = t.canton.map(norm)
    c = canton[canton.niveau_feuille == "canton"].copy()
    c["pk"], c["ck"] = c.prefecture.map(norm), c.canton.map(norm)
    j = c.merge(t[["pk", "ck", "lat", "lon"]].drop_duplicates(["pk", "ck"]), on=["pk", "ck"], how="inner")
    stats = dict(cantons_2022=int(len(c)), cantons_positionnes=int(len(j)), part_cantons_pct=round(len(j) / len(c) * 100, 1),
                 part_population_pct=round(j.population_2022.sum() / c.population_2022.sum() * 100, 1))
    return j.drop(columns=["pk", "ck"]), stats


def main() -> None:
    t0 = time.perf_counter()
    ctx = clean_data()
    tests = run_quality_tests(ctx)
    export_outputs(ctx, tests)
    dim, dim10 = ctx["dim_territoire"], ctx["dim_2010"]
    R = export_demo_evolution(dim, dim10)
    D, E = R["D"], R["E"]
    ag, elec, un = ctx["agences"], ctx["electricite_long"], ctx["unites_electriques"]

    # services de base
    fp = construire_fact_prefecture(dim, elec, un, ag, E["crosswalk"])
    fu = construire_fact_unite(fp, un)
    seuils_profils = fu.attrs["seuils_profils"]
    ipt = compute_ipt(fu, SCENARIOS[SCENARIO_DEFAUT])
    rob = robustesse(fu)
    corr = correlation_composantes(fu)
    fin = matrice_finale(ipt, rob)
    # héritage par préfecture (avec indicateur visible : `taux_herite_du_groupe`)
    h = fin[["unite_electrique", "ipt", "rang_ipt", "classe_priorite", "priority_stability_score", "stabilite", "profil"]].rename(columns={
        "ipt": "unite_ipt", "rang_ipt": "unite_rang_ipt", "classe_priorite": "unite_classe_priorite", "priority_stability_score": "unite_stabilite_pct", "stabilite": "unite_stabilite", "profil": "unite_profil"})
    fp = fp.merge(h, on="unite_electrique", how="left")
    # agences par commune
    commune = agences_par_commune(ag, D["commune"])
    # cantons positionnés
    cg, geo_stats = cantons_geolocalises(D["canton"])
    # recommandations
    reco = construire_recommandations(fin, fp, commune, D["kpi"], ctx["etat_civil_long"], ag, D["canton"])
    anomalies = verifier_coherence_reco(reco, fin)
    assert not anomalies, f"recommandations incohérentes avec l'IPT : {anomalies}"
    # contrôle de cohérence des taux régionaux (publiés vs moyenne pondérée des unités)
    t21 = elec[(elec.indicateur == "taux_acces")].pivot_table(index=["unite_electrique", "type_unite"], columns="annee", values="taux_plafonne").reset_index()
    reg = t21[t21.type_unite == "region_5"].drop(columns="type_unite").rename(columns={"unite_electrique": "region_publiee"})
    code = {"REGION DES SAVANES": "SAVANES", "REGION DE LA KARA": "KARA", "REGION CENTRALE": "CENTRALE", "REGION DES PLATEAUX": "PLATEAUX", "REGION MARITIME": "MARITIME"}
    reg["region_5"] = reg.region_publiee.map(code)
    pond = fu.groupby("region_5").apply(lambda g: (g.taux_plaf_2021 * g.population_2022).sum() / g.population_2022.sum(), include_groups=False).rename("taux_2021_pondere_unites")
    reg = reg.merge(pond, left_on="region_5", right_index=True)
    reg["ecart_pp"] = reg.taux_2021_pondere_unites - reg[2021]
    reg.columns = [str(c) for c in reg.columns]

    # exports
    ass = ag.merge(dim[dim.niveau == "prefecture"][["territoire_id", "nom"]].rename(columns={"territoire_id": "prefecture_id", "nom": "prefecture_nom"}), on="prefecture_id", how="left")
    sauver(fp, "fact_prefecture"); sauver(fu, "fact_unite_electrique_base"); sauver(fin, "fact_unite_electrique")
    sauver(commune, "fact_commune"); sauver(cg, "canton_geo"); sauver(ass, "agences_geo"); sauver(reco, "recommandations"); sauver(reg, "electricite_regions")
    sauver(rob, "ipt_robustesse")
    sauver(RC.scenarios_national(elec, fu), "reconciliation_national", parquet=False)
    sauver(RC.reconcilier_regions(elec, fu), "reconciliation_regions", parquet=False)
    (OUT / "reconciliation_resume.json").write_text(json.dumps(RC.resume_denominateur(elec, fu), indent=2), encoding="utf-8")
    for nom in ("etat_civil_long", "identite_long", "electricite_long"):             # version Parquet (chargement plus rapide dans l'application)
        pd.read_csv(OUT / f"{nom}.csv").to_parquet(OUT / f"{nom}.parquet", index=False)
    sauver(pd.DataFrame([dict(scenario=k, **v, total=sum(v.values())) for k, v in SCENARIOS.items()]), "ipt_scenarios", parquet=False)
    sauver(pd.DataFrame([dict(code=k, libelle=v[0], formule=v[1], sens=v[2], etiquette=v[3]) for k, v in COMPOSANTES.items()]), "ipt_composantes", parquet=False)
    corr["rho"].round(3).reset_index(names="composante").to_csv(OUT / "ipt_correlation_spearman.csv", index=False, encoding="utf-8")
    meta = dict(date_construction=pd.Timestamp.today().date().isoformat(), seuils_classes=ipt.attrs["seuils_classes"], seuils_profils=seuils_profils, taux_national=TAUX_NATIONAL,
                correlation_verdict=corr["verdict"], correlation_paires=[(a, b, r) for a, b, r in corr["paires"]], n_configurations=int(rob.attrs["n_configurations"]),
                seuil_robuste=SEUIL_ROBUSTE, scenario_defaut=SCENARIO_DEFAUT, geo=geo_stats, n_tests=int(len(tests)), tests_par_statut=tests.statut.value_counts().to_dict(),
                population_sans_acces_proxy=float(fu.pop_sans_acces_2021.sum()))
    (OUT / "ipt_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    v = json.loads((OUT / "data_version.json").read_text(encoding="utf-8")); v.update(date_construction=meta["date_construction"])
    (OUT / "data_version.json").write_text(json.dumps(v, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Tables reconstruites en {time.perf_counter() - t0:.1f} s | tests qualité : {meta['tests_par_statut']} | IPT : {SCENARIO_DEFAUT}, {meta['n_configurations']} configurations | cantons positionnés : {geo_stats}")


if __name__ == "__main__":
    main()
