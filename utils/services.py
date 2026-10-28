"""Services de base : électricité (taux ≠ personnes), agences CEET / TdE, tables `fact_prefecture` (39) et `fact_unite_electrique` (33).

Règles (prompt V3.1 §6.3–6.6) :
* on sépare TAUX et NOMBRE DE PERSONNES : population sans accès = population 2022 × (1 − taux 2021 plafonné)  → PROXY ;
* une agence « ouverte » = catégorie publique ET statut `Utilisé` ; les sites Admin/Technique sont comptés à part ;
* pour un groupe d'unités électriques : agences = somme sur les préfectures, agences / 100 000 hab. = somme des agences ÷ somme des populations ;
* le taux d'une unité est hérité par toutes les préfectures de l'unité (`taux_herite_du_groupe`).
"""
import numpy as np
import pandas as pd

SERVICES = ("ceet", "tde")
LIB_SERVICE = {"ceet": "CEET", "tde": "TdE"}
TAUX_NATIONAL = {2018: 45.09, 2019: None, 2020: None, 2021: 57.82}     # taux PUBLIÉS (non recalculables à partir des unités)


def compter_agences(ag: pd.DataFrame, cle: str) -> pd.DataFrame:
    """Compte les agences par territoire (`cle` = prefecture_id ou commune_id) : statuts par service + sites Admin/Technique."""
    pub = ag[ag.est_public]
    out = {}
    for s in SERVICES:
        d = pub[pub.service == LIB_SERVICE[s]]
        g = d.groupby(cle)
        out[f"{s}_ouvertes"] = g.apply(lambda x: int((x.statut == "Utilisé").sum()), include_groups=False)
        out[f"{s}_en_construction"] = g.apply(lambda x: int((x.statut == "En construction").sum()), include_groups=False)
        out[f"{s}_inachevees"] = g.apply(lambda x: int((x.statut == "Inachevé").sum()), include_groups=False)
        out[f"{s}_inconnues"] = g.apply(lambda x: int((x.statut == "Inconnu (Nsp)").sum()), include_groups=False)
        out[f"{s}_non_applicable"] = g.apply(lambda x: int((x.statut == "Non applicable (N/a)").sum()), include_groups=False)
    out["admin_technique"] = ag[~ag.est_public].groupby(cle).size()
    return pd.DataFrame(out).fillna(0).astype(int)


def _ratios(df: pd.DataFrame, pop: str = "population_2022") -> pd.DataFrame:
    """Agences pour 100 000 hab. et habitants par agence (NaN quand aucune agence : « aucune agence », jamais 0 inventé)."""
    for s in SERVICES:
        df[f"{s}_par_100k"] = df[f"{s}_ouvertes"] / df[pop] * 1e5
        df[f"{s}_hab_par_agence"] = np.where(df[f"{s}_ouvertes"] > 0, df[pop] / df[f"{s}_ouvertes"].replace(0, np.nan), np.nan)
        df[f"{s}_ouvertes_nsp"] = df[f"{s}_ouvertes"] + df[f"{s}_inconnues"]          # variante de sensibilité (Nsp compté ouvert)
    df["agences_ouvertes_total"] = df.ceet_ouvertes + df.tde_ouvertes
    df["agences_par_100k_total"] = df.agences_ouvertes_total / df[pop] * 1e5
    df["hab_par_agence_total"] = np.where(df.agences_ouvertes_total > 0, df[pop] / df.agences_ouvertes_total.replace(0, np.nan), np.nan)
    df["agences_ouvertes_total_nsp"] = df.ceet_ouvertes_nsp + df.tde_ouvertes_nsp
    return df


def taux_electricite(elec: pd.DataFrame) -> pd.DataFrame:
    """Taux d'accès par unité : brut / plafonné pour 2018–2021, évolution en points de pourcentage, validité des tendances."""
    t = elec[(elec.indicateur == "taux_acces") & (elec.type_unite == "unite")]
    brut = t.pivot(index="unite_electrique", columns="annee", values="taux_brut").add_prefix("taux_")
    plaf = t.pivot(index="unite_electrique", columns="annee", values="taux_plafonne").add_prefix("taux_plaf_")
    d = brut.join(plaf)
    d["delta_pp_2018_2021"] = d.taux_plaf_2021 - d.taux_plaf_2018                    # NaN si 2018 absent (Blitta)
    return d.reset_index()


def construire_fact_prefecture(dim: pd.DataFrame, elec: pd.DataFrame, unites: pd.DataFrame, ag: pd.DataFrame, crosswalk: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par préfecture (39) : population, accès (hérité de l'unité), agences, croissance (si comparable)."""
    p = dim[dim.niveau == "prefecture"].copy()
    keep = ["territoire_id", "nom", "prefecture", "region_6", "region_nom", "region_5", "region_5_nom", "population_2022", "unite_electrique", "taux_herite_du_groupe"]
    p = p[keep].rename(columns={"territoire_id": "prefecture_id", "nom": "prefecture_nom", "prefecture": "prefecture_raw"})
    p["poids_national_pct"] = p.population_2022 / p.population_2022.sum() * 100
    p = p.merge(taux_electricite(elec), on="unite_electrique", how="left")
    p["ecart_national_pp_2021"] = p.taux_plaf_2021 - TAUX_NATIONAL[2021]
    p["pop_sans_acces_2021"] = p.population_2022 * (1 - p.taux_plaf_2021 / 100)         # PROXY
    ag_pref = compter_agences(ag, "prefecture_id")
    p = p.merge(ag_pref, left_on="prefecture_id", right_index=True, how="left")
    for c in ag_pref.columns:
        p[c] = p[c].fillna(0).astype(int)
    p = _ratios(p)
    for s in SERVICES:
        p[f"{s}_sans_agence"] = p[f"{s}_ouvertes"] == 0
    p["sans_aucun_service"] = p.ceet_sans_agence & p.tde_sans_agence
    # croissance 2010–2022 : seulement si comparable (HIGH / MEDIUM)
    cw = crosswalk[crosswalk.niveau_comparaison == "préfecture"][["prefectures_raw", "pop_2010", "tcam_pct", "comparability_flag", "type_correspondance", "motif"]]
    cw = cw.rename(columns={"prefectures_raw": "prefecture_raw", "pop_2010": "pop_2010_comparable", "tcam_pct": "tcam_pct", "comparability_flag": "flag_croissance", "motif": "motif_croissance"})
    p = p.merge(cw, on="prefecture_raw", how="left")
    gl = crosswalk[crosswalk.territoire_2022.str.startswith("Grand Lomé")].iloc[0]
    p["tcam_grand_lome_pct"] = np.where(p.prefecture_raw.isin(["GOLFE", "AGOE-NYIVE"]), gl.tcam_pct, np.nan)
    p["variation_rel_pct"] = (p.population_2022 / p.pop_2010_comparable - 1) * 100
    return p.sort_values("population_2022", ascending=False).reset_index(drop=True)


def construire_fact_unite(fp: pd.DataFrame, unites: pd.DataFrame) -> pd.DataFrame:
    """33 unités électriques (base de l'IPT) : somme des préfectures du groupe ; ratios recalculés sur les sommes."""
    rows = []
    for u, g in fp.groupby("unite_electrique", sort=False):
        r = dict(unite_electrique=u, n_prefectures=len(g), prefectures=" + ".join(g.sort_values("population_2022", ascending=False).prefecture_nom),
                 prefectures_raw=";".join(g.prefecture_raw), region_5=g.region_5.iloc[0], region_5_nom=g.region_5_nom.iloc[0],
                 regions_6=";".join(sorted(set(g.region_6))), population_2022=g.population_2022.sum())
        for c in ("taux_2018", "taux_2019", "taux_2020", "taux_2021", "taux_plaf_2018", "taux_plaf_2021", "delta_pp_2018_2021"):
            r[c] = g[c].iloc[0]                                                          # identique pour toutes les préfectures du groupe
        for s in SERVICES:
            for st in ("ouvertes", "en_construction", "inachevees", "inconnues", "non_applicable"):
                r[f"{s}_{st}"] = int(g[f"{s}_{st}"].sum())
            # part de la population de l'unité vivant dans une préfecture sans agence ouverte (règle c6)
            r[f"part_pop_sans_{s}"] = g.loc[g[f"{s}_sans_agence"], "population_2022"].sum() / g.population_2022.sum()
            r[f"part_pop_sans_{s}_nsp"] = g.loc[g[f"{s}_ouvertes_nsp"] == 0, "population_2022"].sum() / g.population_2022.sum()     # variante Nsp
        r["admin_technique"] = int(g.admin_technique.sum())
        # croissance : seulement si aucune préfecture du groupe n'est LOW
        ok = g.flag_croissance.isin(["HIGH", "MEDIUM"]).all() and g.pop_2010_comparable.notna().all()
        r["pop_2010_comparable"] = g.pop_2010_comparable.sum() if ok else np.nan
        r["flag_croissance"] = ("MEDIUM" if (g.flag_croissance == "MEDIUM").any() else "HIGH") if ok else "LOW"
        rows.append(r)
    f = pd.DataFrame(rows)
    f["poids_national_pct"] = f.population_2022 / f.population_2022.sum() * 100
    f["tcam_pct"] = np.where(f.pop_2010_comparable.notna(), ((f.population_2022 / f.pop_2010_comparable) ** (1 / 12) - 1) * 100, np.nan)
    f["ecart_national_pp_2021"] = f.taux_plaf_2021 - TAUX_NATIONAL[2021]
    f["pop_sans_acces_2021"] = f.population_2022 * (1 - f.taux_plaf_2021 / 100)         # PROXY
    f["c6_part_pop_sans_service_pct"] = 100 * (f.part_pop_sans_ceet + f.part_pop_sans_tde) / 2
    f = _ratios(f)
    f = f.merge(unites[["unite_electrique", "valide_pour_tendance", "motif_tendance_invalide"]], on="unite_electrique", how="left")
    f["unite_affichage"] = f.prefectures
    f["rang_taux_2021"] = f.taux_plaf_2021.rank(ascending=True, method="min").astype(int)            # 1 = taux le plus bas
    f["rang_pop_sans_acces"] = f.pop_sans_acces_2021.rank(ascending=False, method="min").astype(int)
    # profils par règles explicites (seuils = médianes des 33 unités, documentés) — §6.7
    m_pop, m_taux, m_eq = f.population_2022.median(), f.taux_plaf_2021.median(), f.agences_par_100k_total.median()
    tn = ((f.population_2022.sum() / f.loc[f.pop_2010_comparable.notna(), "pop_2010_comparable"].sum()) ** (1 / 12) - 1) * 100
    pop_h, acc_f, eq_f = f.population_2022 >= m_pop, f.taux_plaf_2021 <= m_taux, f.agences_par_100k_total <= m_eq
    f["profil"] = np.select([pop_h & acc_f & eq_f, pop_h & ~acc_f & ~eq_f, ~pop_h & acc_f, (f.tcam_pct > tn) & eq_f],
                            ["A · forte population, accès et équipement sous la médiane", "B · forte population, accès et équipement au-dessus de la médiane",
                             "C · faible population, accès sous la médiane", "D · croissance plus rapide que le pays, équipement sous la médiane"], default="Autre profil")
    f.attrs["seuils_profils"] = dict(mediane_population=float(m_pop), mediane_taux=float(m_taux), mediane_agences_100k=float(m_eq), tcam_national=float(tn))
    return f.sort_values("population_2022", ascending=False).reset_index(drop=True)


def agences_par_commune(ag: pd.DataFrame, commune: pd.DataFrame) -> pd.DataFrame:
    """Ajoute à `fact_commune` les agences ouvertes par service et les ratios (population = population de la commune)."""
    c = compter_agences(ag, "commune_id")
    d = commune.merge(c, left_on="territoire_id", right_index=True, how="left")
    for col in c.columns:
        d[col] = d[col].fillna(0).astype(int)
    return _ratios(d)


# ───────── indicateurs de la page « Services de base » (fonctions pures, testées dans tests/test_services.py) ─────────
def taux_pondere(df: pd.DataFrame, annee: int, pop: str = "population_2022") -> dict:
    """Taux d'accès moyen PONDÉRÉ par la population 2022, taux plafonné à 100 %.

    Les préfectures sans taux pour l'année sont exclues du numérateur ET du dénominateur (jamais assimilées à 0).
    Retourne {valeur (%|None), pop_couverte, pop_totale, n_sans_taux, n_plafonnes}.
    """
    col = f"taux_{annee}"
    if df is None or df.empty or col not in df.columns:
        return {"valeur": None, "pop_couverte": 0.0, "pop_totale": 0.0, "n_sans_taux": 0, "n_plafonnes": 0}
    ok = df[col].notna() & df[pop].notna()
    pop_couverte = float(df.loc[ok, pop].sum())
    valeur = float((df.loc[ok, col].clip(upper=100) * df.loc[ok, pop]).sum() / pop_couverte) if pop_couverte > 0 else None
    return {"valeur": valeur, "pop_couverte": pop_couverte, "pop_totale": float(df[pop].sum()),
            "n_sans_taux": int((~ok).sum()), "n_plafonnes": int((df[col] > 100).sum())}


def population_sans_acces(df: pd.DataFrame, annee: int, pop: str = "population_2022") -> pd.Series:
    """PROXY par préfecture : population 2022 × (1 − taux plafonné). NaN si le taux de l'année est absent (jamais 0)."""
    col = f"taux_{annee}"
    return df[pop] * (1 - df[col].clip(upper=100) / 100)


def score_deficit_croise(fp_national: pd.DataFrame, annee: int) -> pd.Series:
    """Score relatif 0–100 (100 = plus déficitaire) : 100 × (1 − moyenne des rangs centiles du taux d'accès et des agences ouvertes / 100 000 hab.).

    Les rangs sont TOUJOURS calculés sur les 39 préfectures (référence nationale stable), puis filtrés par l'affichage.
    Indexé par `prefecture_raw`. NaN si le taux de l'année est absent.
    """
    rate = fp_national[f"taux_{annee}"].clip(upper=100)
    density = fp_national["agences_par_100k_total"]
    score = 100 * (1 - (rate.rank(pct=True) + density.rank(pct=True)) / 2)
    return pd.Series(score.to_numpy(), index=fp_national["prefecture_raw"].to_numpy())
