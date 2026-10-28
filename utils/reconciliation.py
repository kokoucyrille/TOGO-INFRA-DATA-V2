"""Réconciliation du taux d'accès à l'électricité : pourquoi 54,5 % (moyenne des unités pondérée par la population 2022) ≠ 57,82 % (taux national publié) ?

Démarche : on teste des dénominateurs / pondérations alternatifs et on mesure l'écart au taux publié. Fonctions PURES (aucune dépendance Streamlit).

Découverte centrale (reproductible, voir tests/test_reconciliation.py) : le fichier source publie, par unité, le nombre d'abonnés BT et le taux d'accès. Le rapport
`abonnés ÷ taux` donne le dénominateur implicite de la source (≈ 1,03 million en 2020, soit ≈ 12,8 % de la population 2022 : sa nature — ménages ? localités
électrifiables ? — n'est PAS documentée). Le taux national publié = Σ abonnés ÷ Σ dénominateurs implicites, c'est-à-dire la moyenne des taux pondérée par ces
dénominateurs, et NON par la population. Les 5 taux régionaux publiés suivent la même règle (la « Région Maritime » publiée exclut l'unité Lomé).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

ANNEES = (2018, 2019, 2020, 2021)
NATIONAL_PUBLIE = {2018: 45.09, 2019: 50.3, 2020: 53.0, 2021: 57.82}
REGIONS_PUBLIEES = {"REGION DES SAVANES": "SAVANES", "REGION DE LA KARA": "KARA", "REGION CENTRALE": "CENTRALE", "REGION DES PLATEAUX": "PLATEAUX", "REGION MARITIME": "MARITIME"}
UNITE_HORS_MARITIME_PUBLIEE = "LOME"        # l'unité Lomé (Golfe) n'est pas comptée dans la « Région Maritime » publiée


def _pivot(elec: pd.DataFrame, type_unite: str, indicateur: str, valeur: str) -> pd.DataFrame:
    d = elec[(elec.type_unite == type_unite) & (elec.indicateur == indicateur)]
    return d.pivot(index="unite_electrique", columns="annee", values=valeur)


def denominateurs_implicites(elec: pd.DataFrame, type_unite: str = "unite") -> pd.DataFrame:
    """Dénominateur implicite de la source, par unité et par année : abonnés BT ÷ (taux / 100). NaN si abonnés ou taux absents (ou taux nul)."""
    ab = _pivot(elec, type_unite, "abonnes_bt", "valeur_brute")
    tx = _pivot(elec, type_unite, "taux_acces", "taux_brut")
    tx = tx.where(tx > 0)
    return ab / (tx / 100)


def denominateurs_estimes(den: pd.DataFrame, annee: int = 2021) -> pd.Series:
    """ESTIMATION du dénominateur de `annee` (aucun abonné publié par unité en 2021) : dénominateur 2020 × croissance 2019→2020 de la même unité."""
    return den[annee - 1] * (den[annee - 1] / den[annee - 2])


def moyenne_ponderee(taux: pd.Series, poids: pd.Series, plafond: float | None = None) -> float:
    """Σ taux × poids ÷ Σ poids, sur les unités où taux ET poids existent (les absents sont exclus des deux sommes, jamais comptés 0)."""
    t = taux.clip(upper=plafond) if plafond is not None else taux
    m = t.notna() & poids.notna() & (poids > 0)
    return float((t[m] * poids[m]).sum() / poids[m].sum()) if m.any() else float("nan")


def scenarios_national(elec: pd.DataFrame, fu_base: pd.DataFrame, publie: dict | None = None) -> pd.DataFrame:
    """Tableau « scénario × année » : valeur du taux national recalculée, écart au taux publié (pp), nature de la donnée.
    `fu_base` : table des 33 unités avec `unite_electrique`, `population_2022`, `pop_2010_comparable`."""
    publie = publie or NATIONAL_PUBLIE
    tx = _pivot(elec, "unite", "taux_acces", "taux_brut")
    fb = fu_base.set_index("unite_electrique").reindex(tx.index)
    den = denominateurs_implicites(elec)
    pop22, pop10 = fb.population_2022, fb.pop_2010_comparable
    den_est = {a: denominateurs_estimes(den, a) for a in (2021,)}
    # unités dont le dénominateur de 2018 manque (Blitta) : on le complète avec celui de 2019 ramené à 2018 par la croissance médiane des autres unités
    den18_complet = den[2018].fillna(den[2019] / (den[2019] / den[2018]).median())

    def serie(fn) -> dict:
        return {a: fn(a) for a in ANNEES}

    rows = [
        ("S1", "Moyenne simple des 33 unités", "Chaque unité compte pour 1, quelle que soit sa taille.", "CALCUL", serie(lambda a: float(tx[a].mean()))),
        ("S2", "Pondérée par la population 2022, taux plafonnés à 100 % (méthode du tableau de bord)", "Préfectures sans taux exclues du numérateur et du dénominateur.", "CALCUL",
         serie(lambda a: moyenne_ponderee(tx[a], pop22, 100))),
        ("S3", "Pondérée par la population 2022, sans plafonnement", "Le taux de Zio dépasse 100 % en 2021 dans la source.", "CALCUL", serie(lambda a: moyenne_ponderee(tx[a], pop22))),
        ("S4", "Pondérée par la population 2010 (périmètre comparable)", "Unités comparables uniquement ; Grand Lomé exclu.", "CALCUL", serie(lambda a: moyenne_ponderee(tx[a], pop10))),
        ("S5", "Pondérée par la population 2022 des 5 régions publiées (taux régionaux publiés)", "Utilise les 5 taux régionaux du fichier ; la Maritime publiée exclut Lomé.", "CALCUL", serie(lambda a: _s5(elec, fu_base, a))),
        ("S6", "Pondérée par le dénominateur implicite de l'année (abonnés ÷ taux), sans plafonnement", "Disponible là où les abonnés par unité sont publiés (2018–2020) ; 2018 sans Blitta (taux absent).", "CALCUL",
         {a: (moyenne_ponderee(tx[a], den[a]) if a in (2018, 2019, 2020) else float("nan")) for a in ANNEES}),
        ("S7", "Idem S6, dénominateur de Blitta 2018 estimé", "Complète l'unité sans taux 2018 (ESTIMATION).", "ESTIMATION",
         {a: (moyenne_ponderee(tx[2018].fillna(tx[2019]), den18_complet) if a == 2018 else float("nan")) for a in ANNEES}),
        ("S8", "Dénominateur implicite extrapolé (2020 × croissance 2019→2020), taux plafonnés à 100 %", "Aucun abonné par unité n'est publié en 2021 : dénominateur ESTIMÉ.", "ESTIMATION",
         {a: (moyenne_ponderee(tx[a], den_est[a], 100) if a == 2021 else float("nan")) for a in ANNEES}),
        ("S9", "Pondérée par le nombre de ménages", "Aucune donnée de ménages dans les fichiers fournis : scénario non testable.", "N/D", serie(lambda a: float("nan"))),
    ]
    out = []
    for code, lib, note, nature, vals in rows:
        r = {"scenario": code, "libelle": lib, "remarque": note, "nature": nature}
        for a in ANNEES:
            r[f"taux_{a}"] = vals[a]
            r[f"ecart_{a}"] = vals[a] - publie[a] if vals[a] == vals[a] else np.nan
        out.append(r)
    pub = {"scenario": "P", "libelle": "Taux national PUBLIÉ (fichier source)", "remarque": "Référence.", "nature": "OBSERVATION"}
    for a in ANNEES:
        pub[f"taux_{a}"], pub[f"ecart_{a}"] = publie[a], 0.0
    return pd.DataFrame([pub] + out)


def _s5(elec: pd.DataFrame, fu_base: pd.DataFrame, annee: int) -> float:
    reg = _pivot(elec, "region_5", "taux_acces", "taux_brut")[annee]
    reg.index = reg.index.map(REGIONS_PUBLIEES)
    fb = fu_base[fu_base.unite_electrique != UNITE_HORS_MARITIME_PUBLIEE]
    pop = fb.groupby("region_5").population_2022.sum()
    return moyenne_ponderee(reg, pop.reindex(reg.index))


def reconcilier_regions(elec: pd.DataFrame, fu_base: pd.DataFrame) -> pd.DataFrame:
    """Taux régionaux : publié vs Σ abonnés ÷ Σ dénominateurs implicites vs moyenne pondérée par la population 2022 (périmètre de la source : Maritime hors Lomé)."""
    den = denominateurs_implicites(elec)
    tx = _pivot(elec, "unite", "taux_acces", "taux_brut")
    pub = _pivot(elec, "region_5", "taux_acces", "taux_brut")
    ab = _pivot(elec, "unite", "abonnes_bt", "valeur_brute")
    fb = fu_base.set_index("unite_electrique")
    rows = []
    for nom, code in REGIONS_PUBLIEES.items():
        unites = [u for u in fb.index[fb.region_5 == code] if u != UNITE_HORS_MARITIME_PUBLIEE]
        for a in ANNEES:
            if a in (2018, 2019, 2020):
                m = den.loc[unites, a].notna()
                recalc = float(ab.loc[unites, a][m].sum() / den.loc[unites, a][m].sum() * 100)
            else:
                recalc = float("nan")
            rows.append(dict(region=code, annee=a, publie=float(pub.loc[nom, a]), recalcule_denominateur_source=recalc,
                             pondere_population_2022=moyenne_ponderee(tx.loc[unites, a], fb.loc[unites, "population_2022"], 100)))
    d = pd.DataFrame(rows)
    d["ecart_denominateur_pp"] = d.recalcule_denominateur_source - d.publie
    d["ecart_population_pp"] = d.pondere_population_2022 - d.publie
    return d


def resume_denominateur(elec: pd.DataFrame, fu_base: pd.DataFrame) -> dict:
    """Nature du dénominateur implicite : total par année et rapport à la population 2022."""
    den = denominateurs_implicites(elec)
    pop = float(fu_base.population_2022.sum())
    return {int(a): dict(total=float(den[a].sum(skipna=True)), part_pop_2022_pct=float(den[a].sum(skipna=True) / pop * 100)) for a in (2018, 2019, 2020)}
