"""Démographie 2022 : classements, tailles, cantons, concentration (Lorenz, Gini)."""
import numpy as np
import pandas as pd

SEUIL_PETIT_CANTON = 5000     # habitants. Justification : entre le 10e centile (≈ 3 560) et le 1er quartile (≈ 6 220) des cantons ;
                              # concerne ≈ 18 % des cantons mais < 4 % de la population des cantons (voir sensibilité du notebook).


def gini(valeurs) -> float:
    """Coefficient de Gini (0 = égalité parfaite, 1 = un seul territoire détient tout). Formule des écarts moyens, sur valeurs > 0."""
    x = np.sort(np.asarray(valeurs, dtype=float))
    x = x[~np.isnan(x)]
    n = len(x)
    if n < 2 or x.sum() == 0:
        return float("nan")
    i = np.arange(1, n + 1)
    return float((2 * (i * x).sum()) / (n * x.sum()) - (n + 1) / n)


def courbe_lorenz(valeurs) -> pd.DataFrame:
    """Points de la courbe de Lorenz : part cumulée des territoires (triés du plus petit au plus grand) vs part cumulée de la population."""
    x = np.sort(np.asarray(valeurs, dtype=float))
    x = x[~np.isnan(x)]
    cum = np.concatenate([[0.0], np.cumsum(x) / x.sum()])
    part = np.linspace(0, 1, len(cum))
    return pd.DataFrame({"part_territoires": part, "part_population": cum})


def part_top(valeurs, k: int) -> float:
    """Part (%) de la population détenue par les k territoires les plus peuplés."""
    x = np.sort(np.asarray(valeurs, dtype=float))[::-1]
    return float(x[:k].sum() / x.sum() * 100)


def _stats(s: pd.Series) -> dict:
    return dict(n=int(s.size), minimum=float(s.min()), q1=float(s.quantile(.25)), mediane=float(s.median()), q3=float(s.quantile(.75)),
                maximum=float(s.max()), moyenne=float(s.mean()), rapport_max_min=float(s.max() / s.min()), gini=gini(s))


def compute_demography(dim: pd.DataFrame, seuil_petit_canton: int = SEUIL_PETIT_CANTON) -> dict:
    """Calcule toutes les tables démographiques 2022 à partir de `dim_territoire`.

    Retourne : region, prefecture, commune (= fact_commune), canton, distribution, concentration, kpi.
    Les quartiers du Grand Lomé sont traités à part (niveau_feuille = « quartier »).
    """
    nat = int(dim.loc[dim.niveau == "national", "population_2022"].iloc[0])
    cant = dim[dim.niveau == "canton"].copy()
    cant["poids_national_pct"] = cant.population_2022 / nat * 100
    cant["rang_national"] = cant.groupby("niveau_feuille").population_2022.rank(ascending=False, method="min").astype(int)
    cant["rang_commune"] = cant.groupby("parent_id").population_2022.rank(ascending=False, method="min").astype(int)
    cant["petit_canton"] = np.where(cant.niveau_feuille == "canton", cant.population_2022 < seuil_petit_canton, np.nan)
    cant["petit_canton"] = cant.petit_canton.map({1.0: True, 0.0: False})

    # ── communes (fact_commune) ──
    com = dim[dim.niveau == "commune"].copy()
    g = cant.groupby("parent_id")
    agg = pd.DataFrame({
        "nb_feuilles": g.size(), "niveau_feuille": g.niveau_feuille.first(),
        "taille_moyenne_feuille": g.population_2022.mean(), "taille_mediane_feuille": g.population_2022.median(),
        "taille_min_feuille": g.population_2022.min(), "taille_max_feuille": g.population_2022.max(),
        "part_petites_feuilles_pct": g.apply(lambda d: d.petit_canton.mean() * 100 if d.niveau_feuille.iloc[0] == "canton" else np.nan, include_groups=False)})
    com = com.drop(columns=["niveau_feuille"]).merge(agg, left_on="territoire_id", right_index=True, how="left")
    com["poids_national_pct"] = com.population_2022 / nat * 100
    com["rang_national"] = com.population_2022.rank(ascending=False, method="min").astype(int)
    com["rang_prefecture"] = com.groupby("prefecture").population_2022.rank(ascending=False, method="min").astype(int)
    colc = ["territoire_id", "cle_hierarchique", "nom", "commune", "prefecture", "region_6", "region_nom", "region_5", "region_5_nom", "population_2022",
            "poids_national_pct", "rang_national", "rang_prefecture", "nb_feuilles", "niveau_feuille", "taille_moyenne_feuille", "taille_mediane_feuille",
            "taille_min_feuille", "taille_max_feuille", "part_petites_feuilles_pct", "commune_fusionnee", "unite_electrique"]
    commune = com[colc].reset_index(drop=True)

    # ── préfectures ──
    pref = dim[dim.niveau == "prefecture"].copy()
    pc = commune.groupby("prefecture").agg(nb_communes=("territoire_id", "size"), taille_moyenne_commune=("population_2022", "mean"),
                                           taille_mediane_commune=("population_2022", "median"), taille_max_commune=("population_2022", "max"))
    pf = cant.groupby("prefecture").agg(nb_feuilles=("territoire_id", "size"), nb_petits_cantons=("petit_canton", lambda s: int(s.fillna(False).sum())),
                                        taille_moyenne_feuille=("population_2022", "mean"), taille_mediane_feuille=("population_2022", "median"))
    pref = pref.merge(pc, left_on="prefecture", right_index=True, how="left").merge(pf, left_on="prefecture", right_index=True, how="left")
    pref["poids_national_pct"] = pref.population_2022 / nat * 100
    pref["rang_national"] = pref.population_2022.rank(ascending=False, method="min").astype(int)
    pref["niveau_feuille"] = np.where(pref.region_6 == "DAGL", "quartier", "canton")
    colp = ["territoire_id", "cle_hierarchique", "nom", "prefecture", "region_6", "region_nom", "region_5", "region_5_nom", "population_2022", "poids_national_pct",
            "rang_national", "nb_communes", "taille_moyenne_commune", "taille_mediane_commune", "taille_max_commune", "nb_feuilles", "niveau_feuille",
            "taille_moyenne_feuille", "taille_mediane_feuille", "nb_petits_cantons", "unite_electrique", "taux_herite_du_groupe"]
    prefecture = pref[colp].reset_index(drop=True)

    # ── régions (6 régions 2022 et 5 régions historiques) ──
    r6 = dim[dim.niveau == "region"][["territoire_id", "nom", "region_6", "population_2022"]].copy()
    r6["decoupage"] = "6 régions 2022"; r6["code_region"] = r6.region_6
    r5 = dim[dim.niveau == "prefecture"].groupby("region_5", as_index=False).population_2022.sum()
    r5["nom"] = r5.region_5.map({"MARITIME": "Maritime (avec Grand Lomé)"}).fillna(r5.region_5.str.title())
    r5["decoupage"] = "5 régions historiques"; r5["code_region"] = r5.region_5
    r5["territoire_id"] = np.nan; r5["region_6"] = np.nan
    region = pd.concat([r6, r5], ignore_index=True)
    region["poids_national_pct"] = region.population_2022 / nat * 100
    nbp = dim[dim.niveau == "prefecture"]
    region["nb_prefectures"] = [int((nbp.region_6 == c).sum()) if d.startswith("6") else int((nbp.region_5 == c).sum()) for c, d in zip(region.code_region, region.decoupage)]
    region["rang"] = region.groupby("decoupage").population_2022.rank(ascending=False, method="min").astype(int)

    # ── cantons ──
    cantons = cant[["territoire_id", "niveau_feuille", "nom", "cle_hierarchique", "region_6", "region_5", "prefecture", "commune", "canton", "population_2022",
                    "poids_national_pct", "rang_national", "rang_commune", "petit_canton"]].reset_index(drop=True)

    # ── distribution & concentration ──
    niveaux = {"Préfectures (39)": prefecture.population_2022, "Communes (116 lignes)": commune.population_2022,
               "Cantons hors Grand Lomé": cantons[cantons.niveau_feuille == "canton"].population_2022,
               "Quartiers du Grand Lomé": cantons[cantons.niveau_feuille == "quartier"].population_2022}
    distribution = pd.DataFrame({k: _stats(v) for k, v in niveaux.items()}).T.reset_index(names="niveau")
    conc = []
    for k, v in niveaux.items():
        for n in (5, 10, 20):
            if len(v) > n:
                conc.append(dict(niveau=k, indicateur=f"Top {n}", valeur=part_top(v, n), unite="% de la population nationale"))
        conc.append(dict(niveau=k, indicateur="Gini", valeur=gini(v), unite="indice 0–1"))
    concentration = pd.DataFrame(conc)

    # ── KPI ──
    top_c, bas_c = commune.loc[commune.population_2022.idxmax()], commune.loc[commune.population_2022.idxmin()]
    top_p, bas_p = prefecture.loc[prefecture.population_2022.idxmax()], prefecture.loc[prefecture.population_2022.idxmin()]
    dagl = int(dim[(dim.niveau == "region") & (dim.region_6 == "DAGL")].population_2022.iloc[0])
    kpi = dict(population_totale=nat, part_grand_lome_pct=dagl / nat * 100, part_top10_communes_pct=part_top(commune.population_2022, 10),
               commune_plus_peuplee=top_c.nom, pop_commune_plus_peuplee=int(top_c.population_2022), commune_moins_peuplee=bas_c.nom,
               pop_commune_moins_peuplee=int(bas_c.population_2022), rapport_max_min_communes=float(top_c.population_2022 / bas_c.population_2022),
               prefecture_plus_peuplee=top_p.nom, pop_prefecture_plus_peuplee=int(top_p.population_2022), prefecture_moins_peuplee=bas_p.nom,
               pop_prefecture_moins_peuplee=int(bas_p.population_2022), mediane_commune=float(commune.population_2022.median()),
               gini_communes=gini(commune.population_2022), gini_prefectures=gini(prefecture.population_2022),
               nb_cantons=int((cantons.niveau_feuille == "canton").sum()), nb_quartiers=int((cantons.niveau_feuille == "quartier").sum()),
               seuil_petit_canton=seuil_petit_canton,
               part_petits_cantons_pct=float(cantons[cantons.niveau_feuille == "canton"].petit_canton.mean() * 100),
               n_petits_cantons=int(cantons[cantons.niveau_feuille == "canton"].petit_canton.sum()),
               part_pop_petits_cantons_pct=float(cantons[(cantons.niveau_feuille == "canton") & (cantons.petit_canton == True)].population_2022.sum()
                                                 / cantons[cantons.niveau_feuille == "canton"].population_2022.sum() * 100))
    return dict(region=region, prefecture=prefecture, commune=commune, canton=cantons, distribution=distribution, concentration=concentration, kpi=kpi)
