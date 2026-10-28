"""Évolution 2010–2022 à découpage maîtrisé : crosswalk, partition comparable, variation, TCAM, contributions.

Règle : on ne compare jamais deux territoires sur leur seul nom. Une unité de comparaison est un ensemble de territoires dont le
périmètre est (quasi) identique aux deux dates ; sinon elle est reconstituée par cantons, ou classée LOW (non comparable).
"""
import numpy as np
import pandas as pd
from .territoire import norm

NB_ANNEES = 12                       # RGPH 2010 → RGPH 2022
SEUIL_FLAG_HIGH = 0.90               # part de la population 2010 couverte par des cantons retrouvés à l'identique pour viser HIGH
INCERTITUDE = {"HIGH": "faible", "MEDIUM": "moyenne", "LOW": "élevée"}
SCISSIONS = {"KPENDJAL": ("KPENDJAL", "KPENDJAL OUEST"), "OTI": ("OTI", "OTI SUD")}      # préfecture 2010 → 2 préfectures 2022
ALIAS_CANTONS = {"PAPRI KPENDJAGA": "KPENDJAL OUEST"}                                    # libellé 2010 hétérogène, rattaché à la main (documenté)
GRAND_LOME_2022 = ("GOLFE", "AGOE NYIVE")

# Examen des transferts de cantons détectés par heuristique de nom (verdict humain, documenté) :
TRANSFERTS_EXAMINES = {
    "ADETI KOPE": ("CONFIRMÉ", "Absent de Zio 2022 ; ADETIKOPE-CENTRE figure sous Agoè-Nyivé 2022 (20 238 hab. en 2010 → 18 033 en 2022)."),
    "KAMINA AKEBOU": ("REJETÉ (homonyme)", "Akébou 2022 contient déjà un canton KAMINA ; KAMINA sous Est-Mono est un autre lieu."),
    "AGOTIME SUD/ ADZAKPA": ("REJETÉ (homonyme)", "AGOTIME sous Golfe/Agoè-Nyivé est un quartier de Lomé homonyme, pas le canton d'Agou."),
    "ASSAHOUN FIAGBE": ("REJETÉ (orthographe)", "Agou 2022 contient ADJAHUN FIAGBE (même lieu, autre graphie) ; ASSAHOUN/ANDO sous Avé est un autre lieu."),
}


def tcam(p0, p1, n=NB_ANNEES):
    """Taux de croissance annuel moyen (CAGR) en %."""
    p0, p1 = np.asarray(p0, dtype=float), np.asarray(p1, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return ((p1 / p0) ** (1 / n) - 1) * 100


def _feuilles(dim22: pd.DataFrame, dim10: pd.DataFrame):
    l22 = dim22[dim22.niveau == "canton"][["canton", "prefecture", "population_2022", "niveau_feuille"]].copy()
    l22["k"], l22["pk"] = l22.canton.map(norm), l22.prefecture.map(norm)
    l10 = dim10[(dim10.niveau == "feuille") & (dim10.region_10 != "LOME")].copy()
    l10["k"] = l10.apply(lambda r: norm(r.sous_localite if isinstance(r.sous_localite, str) else r.canton), axis=1)
    l10["pk"] = l10.prefecture.map(norm)
    return l10, l22


def apparier_cantons(dim22: pd.DataFrame, dim10: pd.DataFrame) -> pd.DataFrame:
    """Pour chaque canton 2010 (hors Lomé) : retrouvé à l'identique (même nom, même préfecture ou sa scission) en 2022 ?"""
    l10, l22 = _feuilles(dim22, dim10)
    s22 = l22.groupby("pk").k.apply(set).to_dict()
    sib = {a: set(b) for a, b in SCISSIONS.items()}
    l10["apparie"] = [any(k in s22.get(p, set()) for p in sib.get(pk, {pk})) for k, pk in zip(l10.k, l10.pk)]
    return l10


def detecter_transferts(dim22: pd.DataFrame, dim10: pd.DataFrame) -> pd.DataFrame:
    """Candidats de transfert de canton entre préfectures : canton 2010 non retrouvé, mais dont un nom proche existe sous une AUTRE préfecture 2022."""
    l10 = apparier_cantons(dim22, dim10)
    _, l22 = _feuilles(dim22, dim10)
    sq = lambda s: s.replace(" ", "")
    rows = []
    for r in l10[(~l10.apparie) & (l10.pk != "GOLFE")].itertuples():
        a = sq(r.k)
        if len(a) < 6:
            continue
        for q in l22.itertuples():
            b = sq(q.k)
            if len(b) >= 6 and (b.startswith(a[:7]) or a.startswith(b[:7])) and q.pk not in {r.pk} | set(SCISSIONS.get(r.pk, ())):
                rows.append(dict(canton_2010=r.canton, pref_2010=r.prefecture, pop_2010=int(r.population_2010), feuille_2022=q.canton, pref_2022=q.prefecture, pop_2022=int(q.population_2022)))
    d = pd.DataFrame(rows)
    if len(d):
        d["verdict"] = d.canton_2010.map(lambda c: TRANSFERTS_EXAMINES.get(c, ("À EXAMINER", ""))[0])
        d["justification"] = d.canton_2010.map(lambda c: TRANSFERTS_EXAMINES.get(c, ("", ""))[1])
    return d


def build_crosswalk_2010_2022(dim22: pd.DataFrame, dim10: pd.DataFrame) -> dict:
    """Construit : `crosswalk` (39 préfectures 2022 + lignes d'union), `comparaison` (partition comparable + régions), `cantons_2010`, `transferts`."""
    l10, l22 = _feuilles(dim22, dim10)
    l10 = apparier_cantons(dim22, dim10)
    cov = l10.groupby("pk").apply(lambda d: d.loc[d.apparie, "population_2010"].sum() / d.population_2010.sum(), include_groups=False)
    transferts = detecter_transferts(dim22, dim10)
    s22 = l22.groupby("pk").k.apply(set).to_dict()

    p22 = dim22[dim22.niveau == "prefecture"].copy()
    p22["k"] = p22.prefecture.map(norm)
    p10 = dim10[dim10.niveau == "prefecture"].copy()
    p10["k"] = p10.prefecture.map(norm)
    pop10 = dict(zip(p10.k, p10.population_2010))
    lome10 = int(dim10[(dim10.niveau == "region") & (dim10.nom == "Lomé")].population_2010.iloc[0])
    golfe10 = int(pop10["GOLFE"])
    adeti10 = l10[l10.k.str.contains("ADETI")]
    adeti22 = l22[l22.k.str.contains("ADETI")]
    assert len(adeti10) == 1 and (adeti10.pk == "ZIO").all() and (adeti22.pk == "AGOE NYIVE").all() and not l22[l22.pk == "ZIO"].k.str.contains("ADETI").any()
    pa10, pa22 = int(adeti10.population_2010.iloc[0]), int(adeti22.population_2022.iloc[0])

    rows = []
    spec = set(GRAND_LOME_2022) | {x for v in SCISSIONS.values() for x in v}
    for r in p22.itertuples():
        k, pop22 = r.k, int(r.population_2022)
        base = dict(territoire_2022=r.nom, prefectures_2022=r.nom, prefectures_raw=r.prefecture, region_6=r.region_6, region_5=r.region_5)
        if k in GRAND_LOME_2022:
            low = "Pris seul, Golfe 2022 n'a pas d'équivalent 2010 : le Grand Lomé fusionné est la bonne unité." if k == "GOLFE" else \
                  "La reconstitution par préfixes de localités 2010 donne 285 404 hab. (×3,1 en 12 ans, ≈ 9,9 %/an) : périmètres non équivalents."
            rows.append({**base, "niveau_comparaison": "préfecture", "territoires_2010": "Lomé + Golfe (2010), recomposés" if k == "GOLFE" else "Golfe 2010 : localités AGOENYIVE/VAKPOSSITO",
                         "type_correspondance": "reconstitution", "comparability_flag": "LOW", "motif": low, "couverture_cantons_pct": np.nan,
                         "pop_2010": np.nan, "pop_2022": pop22, "unite_partition": False})
        elif k in spec:
            parent = next(p for p, parts in SCISSIONS.items() if k in parts)
            c = l10[l10.pk == parent]
            assign = [ALIAS_CANTONS.get(x) or (k if x in s22.get(k, set()) else None) for x in c.k]
            pop10_part = int(c.loc[[a_ == k for a_ in assign], "population_2010"].sum())
            alias = any(ALIAS_CANTONS.get(x) == k for x in c.k)
            flag = "MEDIUM" if alias else "HIGH"
            rows.append({**base, "niveau_comparaison": "préfecture", "territoires_2010": f"{parent.title()} 2010 : cantons de {r.nom}", "type_correspondance": "scission",
                         "comparability_flag": flag, "couverture_cantons_pct": 100.0,
                         "motif": "Reconstitué par cantons" + (" avec alias PAPRI/KPENDJAGA → Kpendjal-Ouest (rattachement manuel documenté)" if alias else " (tous les cantons appariés sans alias)"),
                         "pop_2010": pop10_part, "pop_2022": pop22, "unite_partition": True})
        else:
            pc = float(cov.get(k, np.nan)); flag = "HIGH" if pc >= SEUIL_FLAG_HIGH else "MEDIUM"
            motif = f"{pc:.0%} de la pop. 2010 en cantons retrouvés à l'identique" + ("" if pc >= SEUIL_FLAG_HIGH else " (libellés de cantons hétérogènes)")
            if k == "ZIO":
                flag, motif = "MEDIUM", motif + f" ; le canton ADETI KOPE ({pa10:,} hab. en 2010) est passé sous Agoè-Nyivé en 2022 → périmètre modifié".replace(",", "\u202f")
            rows.append({**base, "niveau_comparaison": "préfecture", "territoires_2010": r.nom, "type_correspondance": "exacte", "comparability_flag": flag, "motif": motif,
                         "couverture_cantons_pct": pc * 100, "pop_2010": int(pop10[k]), "pop_2022": pop22, "unite_partition": True})
    cw = pd.DataFrame(rows)

    # lignes d'union (obligatoires : Grand Lomé, Kpendjal, Oti)
    pop22p = dict(zip(p22.k, p22.population_2022))
    unions = [
        dict(territoire_2022="Grand Lomé (Golfe + Agoè-Nyivé)", prefectures_2022="Golfe + Agoè-Nyivé", prefectures_raw="GOLFE;AGOE-NYIVE", region_6="DAGL", region_5="MARITIME", niveau_comparaison="union",
             territoires_2010="Lomé + Golfe (2010)", type_correspondance="fusion", comparability_flag="HIGH",
             motif="Union des deux préfectures du DAGL contre Lomé + Golfe 2010 ; réserve : un transfert Zio→Agoè-Nyivé (Adéti Kopé) < 1,3 % de la base",
             couverture_cantons_pct=np.nan, pop_2010=lome10 + golfe10, pop_2022=int(pop22p["GOLFE"] + pop22p["AGOE NYIVE"]), unite_partition=True)]
    for parent, (a, b) in SCISSIONS.items():
        unions.append(dict(territoire_2022=f"{parent.title()} + {b.title()}".replace(" Ouest", "-Ouest").replace(" Sud", "-Sud"), prefectures_2022=f"{a.title()} + {b.title()}", prefectures_raw=f"{a};{b}".replace(" ", "-"),
                           region_6="SAVANES", region_5="SAVANES", niveau_comparaison="union", territoires_2010=f"{parent.title()} (2010)", type_correspondance="scission",
                           comparability_flag="HIGH", motif="Union exacte des deux préfectures issues de la scission", couverture_cantons_pct=np.nan,
                           pop_2010=int(pop10[parent]), pop_2022=int(pop22p[a] + pop22p[b]), unite_partition=False))
    cw = pd.concat([cw, pd.DataFrame(unions)], ignore_index=True)
    # Grand Lomé remplace Golfe et Agoè-Nyivé dans la partition ; les lignes de scission restent dans la partition
    cw["niveau_incertitude"] = cw.comparability_flag.map(INCERTITUDE)
    cw["tcam_pct"] = tcam(cw.pop_2010, cw.pop_2022)
    # sensibilité (ESTIMATION) au transfert Adéti Kopé
    cw["tcam_sensibilite_pct"] = np.nan; cw["note_sensibilite"] = ""
    iz = cw.index[cw.territoire_2022 == "Zio"][0]
    cw.loc[iz, "tcam_sensibilite_pct"] = tcam(cw.pop_2010[iz] - pa10, cw.pop_2022[iz])
    cw.loc[iz, "note_sensibilite"] = f"ESTIMATION : base 2010 de Zio privée d'Adéti Kopé ({pa10:,} hab.) → croissance à périmètre constant probablement sous-estimée".replace(",", "\u202f")
    ig = cw.index[cw.territoire_2022.str.startswith("Grand Lomé")][0]
    cw.loc[ig, "tcam_sensibilite_pct"] = tcam(cw.pop_2010[ig], cw.pop_2022[ig] - pa22)
    cw.loc[ig, "note_sensibilite"] = f"ESTIMATION : population 2022 privée du seul quartier ADETIKOPE-CENTRE ({pa22:,} hab.) → borne basse de la croissance à périmètre constant".replace(",", "\u202f")
    cw["id_comparaison"] = [f"C{i + 1:02d}" for i in range(len(cw))]
    cw["dans_classement"] = cw.unite_partition & cw.comparability_flag.isin(["HIGH", "MEDIUM"])
    ordre = ["id_comparaison", "niveau_comparaison", "territoire_2022", "prefectures_2022", "prefectures_raw", "region_6", "region_5", "territoires_2010", "type_correspondance",
             "comparability_flag", "niveau_incertitude", "motif", "couverture_cantons_pct", "pop_2010", "pop_2022", "tcam_pct", "tcam_sensibilite_pct", "note_sensibilite",
             "unite_partition", "dans_classement"]
    cw = cw[ordre]
    comparaison = compute_evolution(cw)
    return dict(crosswalk=cw, comparaison=comparaison, cantons_2010=l10, transferts=transferts)


def compute_evolution(cw: pd.DataFrame) -> pd.DataFrame:
    """Partition comparable (unités) + régions : variation absolue/relative, TCAM sur 12 ans, contribution à la croissance nationale, rang."""
    u = cw[cw.unite_partition].copy()
    # le Grand Lomé (union) remplace Golfe et Agoè-Nyivé (LOW), déjà exclus de la partition
    u = u[~u.territoire_2022.isin(["Golfe", "Agoè-Nyivé"])]
    d10, d22 = float(u.pop_2010.sum()), float(u.pop_2022.sum())
    u["niveau"] = "unité de comparaison"
    u["nom"] = u.territoire_2022
    out = [u.rename(columns={})]
    # régions : 5 historiques (Maritime avec Grand Lomé) et 6 de 2022 (Grand Lomé séparé)
    def regroupe(col, niveau, flags):
        g = u.groupby(col, as_index=False).agg(pop_2010=("pop_2010", "sum"), pop_2022=("pop_2022", "sum"))
        g["niveau"] = niveau; g["nom"] = g[col].map(lambda c: {"MARITIME": "Maritime (avec Grand Lomé)" if col == "region_5" else "Maritime (hors Grand Lomé)", "DAGL": "Grand Lomé (DAGL)"}.get(c, c.title()))
        g["comparability_flag"] = g[col].map(lambda c: flags.get(c, "HIGH")); g["niveau_incertitude"] = g.comparability_flag.map(INCERTITUDE)
        g["motif"] = ""
        return g
    out.append(regroupe("region_5", "région historique (5)", {}))
    out.append(regroupe("region_6", "région 2022 (6)", {"MARITIME": "MEDIUM"}))
    c = pd.concat(out, ignore_index=True)
    c["variation_abs"] = c.pop_2022 - c.pop_2010
    c["variation_rel_pct"] = c.variation_abs / c.pop_2010 * 100
    c["tcam_pct"] = tcam(c.pop_2010, c.pop_2022)
    c["contribution_croissance_pct"] = c.variation_abs / (d22 - d10) * 100
    ok = c.comparability_flag.isin(["HIGH", "MEDIUM"])
    c["rang_tcam"] = c.where(ok).groupby("niveau").tcam_pct.rank(ascending=False, method="min")
    c["classement_autorise"] = ok
    c["id_comparaison"] = c.id_comparaison.fillna(pd.Series([f"R{i + 1:02d}" for i in range(len(c))]))
    cols = ["id_comparaison", "niveau", "nom", "region_6", "region_5", "prefectures_2022", "prefectures_raw", "pop_2010", "pop_2022", "variation_abs", "variation_rel_pct", "tcam_pct",
            "contribution_croissance_pct", "comparability_flag", "niveau_incertitude", "rang_tcam", "classement_autorise", "motif"]
    for k in cols:
        if k not in c:
            c[k] = np.nan
    return c[cols].reset_index(drop=True)
