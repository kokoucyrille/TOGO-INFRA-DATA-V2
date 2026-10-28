"""Indice de Priorité Territoriale (IPT) : composantes, normalisation, scénarios, robustesse, recommandations.

L'IPT est un OUTIL D'AIDE À LA DÉCISION, pas une vérité. Unité : les 33 unités électriques (les préfectures groupées ne sont pas
dissociables sans inventer de données). Les préfectures héritent du score de leur unité (avec un indicateur visible).
`compute_ipt` est PURE et VECTORISÉE : elle est réutilisée telle quelle par le simulateur du tableau de bord.
"""
import numpy as np
import pandas as pd

# code → (libellé, formule, sens, étiquette de donnée)
COMPOSANTES = {
    "c1_deficit_acces": ("Déficit d'accès", "100 − taux d'accès à l'électricité 2021 (plafonné à 100)", "plus le taux est bas, plus la priorité est forte", "CALCUL"),
    "c2_pop_sans_acces": ("Population sans accès", "population 2022 × (1 − taux 2021)", "plus il y a de personnes sans accès, plus la priorité est forte", "PROXY"),
    "c3_croissance": ("Croissance démographique", "TCAM 2010–2022 (si comparabilité HIGH ou MEDIUM, sinon valeur neutre)", "plus la croissance est rapide, plus la priorité est forte", "CALCUL"),
    "c4_stagnation_acces": ("Stagnation de l'accès", "− (taux 2021 − taux 2018), en points (si la tendance est valide, sinon valeur neutre)", "moins l'accès progresse, plus la priorité est forte", "CALCUL"),
    "c5_deficit_equipement": ("Déficit d'équipement", "− agences CEET + TdE ouvertes pour 100 000 habitants", "moins il y a d'agences par habitant, plus la priorité est forte", "CALCUL"),
    "c6_absence_service": ("Absence de service", "moyenne des parts de population vivant sans agence CEET ouverte et sans agence TdE ouverte", "plus la population est privée d'agence, plus la priorité est forte", "CALCUL"),
}
CODES = list(COMPOSANTES)

# Poids tabulés (somme = 100). HYPOTHÈSE de travail : aucune pondération officielle ou d'expert n'est fournie ;
# le scénario C (équilibre) est la référence, les trois autres déplacent l'accent ; la robustesse mesure la sensibilité à ce choix.
SCENARIOS = {
    "A · Accès":       dict(c1_deficit_acces=35, c2_pop_sans_acces=15, c3_croissance=10, c4_stagnation_acces=25, c5_deficit_equipement=8, c6_absence_service=7),
    "B · Population":  dict(c1_deficit_acces=15, c2_pop_sans_acces=35, c3_croissance=25, c4_stagnation_acces=10, c5_deficit_equipement=8, c6_absence_service=7),
    "C · Équilibre":   dict(c1_deficit_acces=20, c2_pop_sans_acces=20, c3_croissance=15, c4_stagnation_acces=15, c5_deficit_equipement=15, c6_absence_service=15),
    "D · Équipement":  dict(c1_deficit_acces=10, c2_pop_sans_acces=15, c3_croissance=10, c4_stagnation_acces=5, c5_deficit_equipement=30, c6_absence_service=30),
}
SCENARIO_DEFAUT = "C · Équilibre"
CLASSES = ["Très haute", "Haute", "Moyenne", "Faible"]
SEUIL_ROBUSTE = 80.0           # % de configurations où l'unité est dans le Top 10
TOP_N = 10


def composantes_brutes(fu: pd.DataFrame, nsp: bool = False) -> pd.DataFrame:
    """Valeurs brutes c1…c6 (orientées : plus grand = situation plus défavorable). NaN = valeur neutre à appliquer (cas signalés)."""
    agences = fu.agences_par_100k_total if not nsp else (fu.agences_ouvertes_total_nsp / fu.population_2022 * 1e5)
    out = pd.DataFrame(index=fu.index)
    out["c1_deficit_acces"] = 100 - fu.taux_plaf_2021
    out["c2_pop_sans_acces"] = fu.pop_sans_acces_2021
    out["c3_croissance"] = fu.tcam_pct.where(fu.flag_croissance.isin(["HIGH", "MEDIUM"]))
    out["c4_stagnation_acces"] = (-fu.delta_pp_2018_2021).where(fu.valide_pour_tendance.astype(bool))
    out["c5_deficit_equipement"] = -agences
    out["c6_absence_service"] = fu.c6_part_pop_sans_service_pct if not nsp else 100 * (
        _part_sans(fu, "ceet") + _part_sans(fu, "tde")) / 2
    return out


def _part_sans(fu: pd.DataFrame, s: str) -> pd.Series:
    """Variante Nsp : une préfecture sans agence ouverte mais avec une agence au statut inconnu n'est plus « sans agence »."""
    return fu[f"part_pop_sans_{s}_nsp"] if f"part_pop_sans_{s}_nsp" in fu else fu[f"part_pop_sans_{s}"]


def normaliser(brut: pd.DataFrame, methode: str = "minmax", winsor=(5, 95)) -> pd.DataFrame:
    """0 à 100 (100 = situation la plus défavorable). `minmax` : winsorisation p5/p95 puis min–max ; `rang` : rang percentile. Les NaN deviennent la médiane (neutre)."""
    out = pd.DataFrame(index=brut.index)
    for c in brut:
        x = brut[c].astype(float)
        if methode == "rang":
            n = x.rank(pct=True, method="average") * 100
        else:
            lo, hi = np.nanpercentile(x, winsor[0]), np.nanpercentile(x, winsor[1])
            n = ((x.clip(lo, hi) - lo) / (hi - lo) * 100) if hi > lo else pd.Series(50.0, index=x.index)
        out[c] = n.fillna(n.median())                                                # valeur neutre = médiane des unités renseignées
    return out


def compute_ipt(fu: pd.DataFrame, weights: dict, methode: str = "minmax", nsp: bool = False) -> pd.DataFrame:
    """IPT = Σ poids × composante normalisée / Σ poids. Retourne `fu` enrichi : c*_norm, ipt (0–100), rang, classe, indicateurs « valeur neutre »."""
    w = pd.Series({c: float(weights.get(c, 0)) for c in CODES})
    if w.sum() <= 0:
        raise ValueError("La somme des poids doit être strictement positive.")
    brut = composantes_brutes(fu, nsp=nsp)
    norm = normaliser(brut, methode)
    ipt = (norm[CODES] * (w / w.sum())).sum(axis=1)
    out = fu.copy()
    for c in CODES:
        out[f"{c}_norm"] = norm[c]
    out["neutre_c3"] = brut.c3_croissance.isna()
    out["neutre_c4"] = brut.c4_stagnation_acces.isna()
    out["ipt"] = ipt
    out["rang_ipt"] = out.ipt.rank(ascending=False, method="min").astype(int)
    q = out.ipt.quantile([.25, .5, .75])
    out["classe_priorite"] = pd.cut(out.ipt, [-np.inf, q[.25], q[.5], q[.75], np.inf], labels=CLASSES[::-1], right=True).astype(str)
    out.attrs["seuils_classes"] = {"Q1": float(q[.25]), "Médiane": float(q[.5]), "Q3": float(q[.75])}
    return out


def top_n(df: pd.DataFrame, n: int = TOP_N) -> list:
    return list(df.sort_values("ipt", ascending=False).head(n).unite_electrique)


def correlation_composantes(fu: pd.DataFrame, methode: str = "minmax") -> dict:
    """Matrice de Spearman entre c1…c6 + verdict (|ρ| ≥ 0,8 → risque de double comptage ; Top 10 comparé à une variante sans la composante redondante)."""
    norm = normaliser(composantes_brutes(fu), methode)
    rho = norm.corr(method="spearman")
    paires = [(a, b, float(rho.loc[a, b])) for i, a in enumerate(CODES) for b in CODES[i + 1:] if abs(rho.loc[a, b]) >= 0.8]
    base = compute_ipt(fu, SCENARIOS[SCENARIO_DEFAUT])
    res = dict(rho=rho, paires=paires, verdict="Aucune paire de composantes ne dépasse |ρ| = 0,8 : pas de risque de double comptage détecté.", variantes=[])
    for a, b, r in paires:
        redondante = a if rho[a].drop(a).abs().mean() >= rho[b].drop(b).abs().mean() else b          # la plus corrélée aux autres = la moins informative
        w = dict(SCENARIOS[SCENARIO_DEFAUT]); w[redondante] = 0
        var = compute_ipt(fu, w)
        commun = len(set(top_n(base)) & set(top_n(var)))
        res["variantes"].append(dict(paire=(a, b), rho=r, retiree=redondante, top10_communs=commun))
    if paires:
        txt = "; ".join(f"{COMPOSANTES[v['paire'][0]][0]} ↔ {COMPOSANTES[v['paire'][1]][0]} (ρ = {v['rho']:.2f}) : sans « {COMPOSANTES[v['retiree']][0]} », {v['top10_communs']} unités sur 10 restent dans le Top 10" for v in res["variantes"])
        res["verdict"] = f"Risque de double comptage détecté — {txt}."
    return res


def robustesse(fu: pd.DataFrame, n_tirages: int = 500, seed: int = 42, n: int = TOP_N) -> pd.DataFrame:
    """Fréquence en Top n sur : 4 scénarios + `n_tirages` poids Dirichlet(α = 1, random_state = seed) + variante Nsp + normalisation par rang.
    `priority_stability_score` = % de configurations où l'unité est dans le Top n (robuste si ≥ 80 %)."""
    rng = np.random.default_rng(seed)
    configs = [(nom, compute_ipt(fu, w)) for nom, w in SCENARIOS.items()]
    configs.append(("Variante statut (Nsp compté ouvert)", compute_ipt(fu, SCENARIOS[SCENARIO_DEFAUT], nsp=True)))
    configs.append(("Normalisation par rang percentile", compute_ipt(fu, SCENARIOS[SCENARIO_DEFAUT], methode="rang")))
    tirages = rng.dirichlet(np.ones(len(CODES)), size=n_tirages)
    rangs, tops = {}, []
    for nom, d in configs:
        rangs[nom] = d.set_index("unite_electrique").rang_ipt
        tops.append(set(top_n(d, n)))
    for i, wv in enumerate(tirages):
        d = compute_ipt(fu, dict(zip(CODES, wv)))
        rangs[f"tirage_{i}"] = d.set_index("unite_electrique").rang_ipt
        tops.append(set(top_n(d, n)))
    R = pd.DataFrame(rangs)
    out = pd.DataFrame(index=R.index)
    out["frequence_top10_pct"] = [100 * sum(u in t for t in tops) / len(tops) for u in R.index]
    out["priority_stability_score"] = out.frequence_top10_pct
    out["rang_median"] = R.median(axis=1)
    out["rang_min"], out["rang_max"] = R.min(axis=1), R.max(axis=1)
    out["variation_rang"] = out.rang_max - out.rang_min
    out["stabilite"] = np.where(out.priority_stability_score >= SEUIL_ROBUSTE, "robuste", "sensible")
    for nom, _ in configs:
        out[f"rang · {nom}"] = R[nom]
    out.attrs["n_configurations"] = len(tops)
    return out.reset_index().rename(columns={"index": "unite_electrique"})


def matrice_finale(ipt: pd.DataFrame, rob: pd.DataFrame) -> pd.DataFrame:
    """`Territoire | Population | Accès | Évolution | Équipement | IPT | Priorité | Stabilité`, triée par IPT décroissant."""
    d = ipt.merge(rob[["unite_electrique", "priority_stability_score", "stabilite", "rang_median"]], on="unite_electrique", how="left")
    return d.sort_values("ipt", ascending=False).reset_index(drop=True)
