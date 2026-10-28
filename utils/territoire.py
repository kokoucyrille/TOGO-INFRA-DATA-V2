"""Référentiel territorial : reconstruction des hiérarchies 2022 et 2010 (listes plates sans colonne de niveau).

Principe : les niveaux sont reconstruits par l'ORDRE des lignes puis VALIDÉS PAR SOMME (parent = somme des enfants).
Jamais de jointure sur le nom seul : toute jointure passe par une clé de chemin `region|prefecture|commune|canton`.
"""
import re
import unicodedata
import numpy as np
import pandas as pd

REGIONS_6 = ["SAVANES", "KARA", "CENTRALE", "PLATEAUX", "MARITIME", "DAGL"]
REGIONS_10 = ["LOME", "MARITIME", "PLATEAUX", "CENTRALE", "KARA", "SAVANES"]
NOM_REGION = {"SAVANES": "Savanes", "KARA": "Kara", "CENTRALE": "Centrale", "PLATEAUX": "Plateaux",
              "MARITIME": "Maritime", "DAGL": "Grand Lomé (DAGL)", "LOME": "Lomé"}


def norm(s) -> str:
    """Normalisation de nom : sans accents, majuscules, ponctuation (-, _, /, ') remplacée par un espace."""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c)).upper().replace("\u2019", "'")
    return re.sub(r"\s+", " ", re.sub(r"[-_/']", " ", s)).strip()


def _corr(ligne, champ, valeur, nature, traitement, impact):
    return dict(ligne=int(ligne), champ=champ, valeur=valeur, nature=nature, traitement=traitement, impact=impact)


# ───────────────────────────── 2022 ─────────────────────────────
def build_hierarchy_2022(df: pd.DataFrame):
    """Retourne (hier, corrections). `hier` : une ligne par ligne du fichier, avec niveau et parents.

    niveaux : national / region / prefecture / commune / feuille (canton hors DAGL, quartier dans le DAGL).
    """
    noms = df["découpage-administratif"].str.strip().tolist()
    vals = df["Value"].astype(int).tolist()
    n = len(noms)
    niveau = [None] * n
    niveau[0] = "national"
    region = [None] * n
    cur = None
    for i in range(1, n):
        if noms[i] in REGIONS_6:
            niveau[i] = "region"
            cur = noms[i]
        region[i] = cur
    for i in range(1, n):                                    # communes = lignes finissant par un chiffre
        if niveau[i] is None and re.search(r"\d$", noms[i]):
            if region[i] == "DAGL" and not re.match(r"^(GOLFE|AGOE-NYIVE) \d$", noms[i]):
                continue                                      # quartiers KELEGOUGAN1, ATIEGOU1, … (pas des communes)
            niveau[i] = "commune"
    for i in range(1, n):                                    # préfecture = valeur égale à la somme des communes suivantes
        if niveau[i] is None:
            s, j = 0, i + 1
            while j < n and s < vals[i] and niveau[j] != "region":
                if niveau[j] == "commune":
                    s += vals[j]
                j += 1
            if s == vals[i] and any(k == "commune" for k in niveau[i + 1:j]):
                niveau[i] = "prefecture"
    niveau = [k or "feuille" for k in niveau]

    corrections, libelle = [], list(noms)
    pref = [None] * n; com_pos = [None] * n; pref_pos = [None] * n
    cur_pref = cur_pref_pos = cur_com = None
    seen = {}
    for i, k in enumerate(niveau):
        if k == "prefecture":
            cur_pref, cur_pref_pos, cur_com = noms[i], i, None
            seen = {}
            if noms[i] == "TOTOAL AVE":
                libelle[i] = "AVE"; cur_pref = "AVE"
                corrections.append(_corr(i + 2, "découpage-administratif", "TOTOAL AVE", "Faute de frappe (préfixe « TOTOAL »)",
                                         "Renommée « AVE » (préfecture d'Avé)", "Aucun (somme validée)"))
        elif k in ("region", "national"):
            cur_pref = cur_pref_pos = cur_com = None
        elif k == "commune":
            lab = noms[i]
            if re.search(r"\S\d+$", lab) and not re.search(r"\s\d+$", lab):
                libelle[i] = re.sub(r"(\D)(\d+)$", r"\1 \2", lab)
                corrections.append(_corr(i + 2, "découpage-administratif", lab, "Espace manquant", f"Renommée « {libelle[i]} »", "Aucun"))
                lab = libelle[i]
            rang = sum(1 for j in range(cur_pref_pos + 1, i + 1) if niveau[j] == "commune")
            if lab in seen:
                prefixe = re.sub(r"\s*\d+$", "", lab)
                libelle[i] = f"{prefixe} {rang}"
                corrections.append(_corr(i + 2, "découpage-administratif", lab, f"Libellé dupliqué dans la préfecture (2e occurrence = commune n°{rang})",
                                         f"Renommée « {libelle[i]} » (confirmé par la somme des préfectures)", "Évite un doublon de clé"))
            seen[lab] = True
            cur_com = i
        elif k == "feuille":
            pass
        pref[i] = cur_pref if k not in ("region", "national") else None
        pref_pos[i] = cur_pref_pos if k not in ("region", "national") else None
        com_pos[i] = cur_com if k == "feuille" else None
    hier = pd.DataFrame(dict(
        idx=np.arange(n), ligne=np.arange(n) + 2, libelle_brut=noms, libelle=libelle, valeur=vals, niveau=niveau,
        region_6=region, prefecture=pref, prefecture_idx=pref_pos, commune_idx=com_pos))
    # quartiers du DAGL / cantons ailleurs
    hier["niveau_feuille"] = np.where(hier.niveau == "feuille", np.where(hier.region_6 == "DAGL", "quartier", "canton"), None)
    for i in hier.index[(hier.niveau == "commune") & hier.libelle.str.contains(r"\+")]:
        corrections.append(_corr(hier.ligne[i], "découpage-administratif", hier.libelle_brut[i], "Une seule ligne pour 2 communes (DANYI 1 et DANYI 2)",
                                 "Conservée telle quelle, drapeau `commune_fusionnee` ; non séparable sans inventer", "Danyi 1 et Danyi 2 non distinguables"))
    for i in hier.index[(hier.niveau == "feuille") & hier.libelle.str.contains(r"\d$")]:
        corrections.append(_corr(hier.ligne[i], "découpage-administratif", hier.libelle_brut[i], "Quartier (et non commune) finissant par un chiffre",
                                 "Classé comme feuille (quartier du DAGL)", "Exclu du décompte des communes"))
    return hier, corrections


# ───────────────────────────── 2010 ─────────────────────────────
def build_hierarchy_2010(df: pd.DataFrame):
    """Hiérarchie 2010 (région → préfecture → canton ; Lomé : arrondissement → quartier). Retourne (hier, corrections)."""
    noms = df["indicateurs"].str.strip().tolist()
    vals = df["Value"].astype(int).tolist()
    n = len(noms)
    niveau = [None] * n; niveau[0] = "national"
    pos, last = [], 0
    for r in REGIONS_10:
        i = next(j for j in range(last + 1, n) if noms[j] == r)
        pos.append(i); niveau[i] = "region"; last = i
    pref = [None] * n; reg = [None] * n
    for k, i in enumerate(pos):
        fin = (pos + [n])[k + 1]
        for t in range(i, fin):
            reg[t] = noms[i]
        j = i + 1
        while j < fin:
            s, t = 0, j + 1
            while t < fin and s < vals[j]:
                s += vals[t]; t += 1
            if s == vals[j] and t > j + 1:
                niveau[j] = "arrondissement" if noms[i] == "LOME" else "prefecture"
                for u in range(j, t):
                    pref[u] = noms[j]
                j = t
            else:
                niveau[j] = "NON_RECONSTITUE"; j += 1
    niveau = [k or "feuille" for k in niveau]
    corrections, libelle = [], list(noms)
    for i in range(n):
        if niveau[i] == "prefecture" and noms[i] == "Sous Prefecture de MO":
            libelle[i] = "MO"; pref = [("MO" if p == "Sous Prefecture de MO" else p) for p in pref]
            corrections.append(_corr(i + 2, "indicateurs", noms[i], "Libellé hétérogène (préfecture de Mô)", "Renommée « MO »", "Aucun"))
    hier = pd.DataFrame(dict(idx=np.arange(n), ligne=np.arange(n) + 2, libelle_brut=noms, libelle=libelle, valeur=vals,
                             niveau=niveau, region_10=reg, prefecture=pref))
    hier["niveau_feuille"] = np.where(hier.niveau == "feuille", np.where(hier.region_10 == "LOME", "quartier", "canton"), None)
    sp = hier.libelle.str.split("=", n=1, expand=True)
    hier["canton"] = np.where(hier.niveau == "feuille", sp[0].str.strip(), None)
    hier["sous_localite"] = np.where((hier.niveau == "feuille") & sp[1].notna(), sp[1].str.strip() if 1 in sp else None, None)
    hier["groupe_reconstitution_agoe"] = hier.libelle_brut.str.startswith(("AGOENYIVE", "VAKPOSSITO"))
    dup = hier.libelle_brut[hier.libelle_brut.duplicated(keep=False)]
    for lab in sorted(dup.unique()):
        lignes = hier.index[hier.libelle_brut == lab].tolist()
        corrections.append(_corr(hier.ligne[lignes[0]], "indicateurs", lab,
                                 f"Libellé dupliqué à plusieurs niveaux ({len(lignes)} lignes : {', '.join(hier.niveau[lignes])})",
                                 "Désambiguïsé par la clé de chemin région|préfecture|canton", "Jointure sur nom seul interdite"))
    return hier, corrections


NOMS_PREFECTURES = {   # nom normalisé → nom d'affichage correct (accents et traits d'union)
    "AGOE NYIVE": "Agoè-Nyivé", "AGOU": "Agou", "AKEBOU": "Akébou", "AMOU": "Amou", "ANIE": "Anié", "ASSOLI": "Assoli", "AVE": "Avé", "BAS MONO": "Bas-Mono",
    "BASSAR": "Bassar", "BINAH": "Binah", "BLITTA": "Blitta", "CINKASSE": "Cinkassé", "DANKPEN": "Dankpen", "DANYI": "Danyi", "DOUFELGOU": "Doufelgou",
    "EST MONO": "Est-Mono", "GOLFE": "Golfe", "HAHO": "Haho", "KERAN": "Kéran", "KLOTO": "Kloto", "KOZAH": "Kozah", "KPELE": "Kpélé", "KPENDJAL": "Kpendjal",
    "KPENDJAL OUEST": "Kpendjal-Ouest", "LACS": "Lacs", "MOYEN MONO": "Moyen-Mono", "MO": "Mô", "OGOU": "Ogou", "OTI": "Oti", "OTI SUD": "Oti-Sud",
    "SOTOUBOUA": "Sotouboua", "TANDJOARE": "Tandjoaré", "TCHAMBA": "Tchamba", "TCHAOUDJO": "Tchaoudjo", "TONE": "Tône", "VO": "Vo", "WAWA": "Wawa",
    "YOTO": "Yoto", "ZIO": "Zio",
}


def nom_affichage(s: str, accent_map: dict | None = None) -> str:
    """Nom lisible : préfectures et communes numérotées (« KPELE 1 » → « Kpélé 1 ») corrigées ; sinon noms observés dans les agences ; sinon titre."""
    k = norm(s)
    if k in NOMS_PREFECTURES:
        return NOMS_PREFECTURES[k]
    m = re.match(r"^(.*?)(\s*\d+)$", str(s).strip())
    if m and norm(m.group(1)) in NOMS_PREFECTURES:
        return NOMS_PREFECTURES[norm(m.group(1))] + m.group(2).replace(" ", " ")
    return (accent_map or {}).get(k) or _titre(s)


def _titre(s: str) -> str:
    return s.title().replace("'S", "'s")


def build_accent_map(agences: pd.DataFrame) -> dict:
    """Noms accentués observés dans les fichiers d'agences : {nom normalisé: nom accentué}."""
    m = {}
    for c in ("region_nom_bdd", "prefecture_nom_bdd", "commune_nom_bdd", "canton_nom_bdd"):
        for v in agences[c].dropna().unique():
            if v and v not in ("N/a", "Nsp"):
                m.setdefault(norm(v), v.strip())
    return m


def _cle(*parts) -> str:
    return "|".join(norm(p) for p in parts if p is not None and p == p)


def build_dim_territoire(h22: pd.DataFrame, unite_par_pref: dict | None = None, accent_map: dict | None = None) -> pd.DataFrame:
    """Dimension territoriale 2022 : une ligne par nœud (national, 6 régions, 39 préfectures, communes, cantons/quartiers)."""
    nom_aff = lambda s: nom_affichage(s, accent_map)
    rows = []
    for r in h22.itertuples():
        reg = r.region_6
        base = dict(territoire_id=int(r.idx), niveau=("canton" if r.niveau == "feuille" else r.niveau), population_2022=int(r.valeur), ligne_source_2022=int(r.ligne),
                    libelle_brut=r.libelle_brut, libelle_corrige=bool(r.libelle != r.libelle_brut), niveau_feuille=r.niveau_feuille)
        if r.niveau == "national":
            rows.append({**base, "nom": "Togo", "cle_hierarchique": "TOGO", "parent_id": None, "region_6": None, "region_5": None,
                         "prefecture": None, "commune": None, "canton": None}); continue
        if r.niveau == "region":
            rows.append({**base, "nom": NOM_REGION[reg], "cle_hierarchique": reg, "parent_id": 0, "region_6": reg,
                         "region_5": "MARITIME" if reg == "DAGL" else reg, "prefecture": None, "commune": None, "canton": None}); continue
        pref = h22.libelle[int(r.prefecture_idx)] if r.niveau != "region" else None
        com = h22.libelle[int(r.commune_idx)] if r.niveau == "feuille" else (r.libelle if r.niveau == "commune" else None)
        can = r.libelle if r.niveau == "feuille" else None
        if r.niveau == "prefecture":
            parent = int(h22.index[(h22.niveau == "region") & (h22.libelle_brut == reg)][0]); pref = r.libelle; com = can = None
        elif r.niveau == "commune":
            parent = int(r.prefecture_idx)
        else:
            parent = int(r.commune_idx)
        rows.append({**base, "nom": nom_aff(r.libelle), "cle_hierarchique": _cle(reg, pref, com, can), "parent_id": parent,
                     "region_6": reg, "region_5": "MARITIME" if reg == "DAGL" else reg, "prefecture": pref, "commune": com, "canton": can})
    d = pd.DataFrame(rows)
    # unicité de la clé : suffixe #n si deux feuilles de même nom dans la même commune
    dup = d.cle_hierarchique.duplicated(keep=False)
    if dup.any():
        d.loc[dup, "cle_hierarchique"] = d[dup].cle_hierarchique + "#" + (d[dup].groupby("cle_hierarchique").cumcount() + 1).astype(str)
    d["commune_fusionnee"] = (d.niveau == "commune") & d.libelle_brut.str.contains(r"\+")
    d["region_nom"] = d.region_6.map(NOM_REGION)
    d["region_5_nom"] = d.region_5.map(NOM_REGION)
    # rattachement aux unités électriques (par préfecture)
    up = unite_par_pref or {}
    d["unite_electrique"] = d.prefecture.map(lambda p: up.get(norm(p)) if isinstance(p, str) else None)
    d["taux_herite_du_groupe"] = d.unite_electrique.fillna("").str.contains(r"\+")
    ordre = ["territoire_id", "niveau", "niveau_feuille", "nom", "cle_hierarchique", "parent_id", "region_6", "region_nom", "region_5", "region_5_nom",
             "prefecture", "commune", "canton", "population_2022", "unite_electrique", "taux_herite_du_groupe", "commune_fusionnee",
             "libelle_brut", "libelle_corrige", "ligne_source_2022"]
    return d[ordre]


def build_dim_2010(h10: pd.DataFrame) -> pd.DataFrame:
    """Table 2010 nettoyée (région → préfecture → canton ; Lomé : arrondissement → quartier), avec clé de chemin unique."""
    rows = []
    for r in h10.itertuples():
        reg = r.region_10
        if r.niveau == "national":
            cle, nom = "TOGO", "Togo"
        elif r.niveau == "region":
            cle, nom = r.libelle_brut, NOM_REGION[r.libelle_brut]
        elif r.niveau in ("prefecture", "arrondissement"):
            cle, nom = _cle(reg, r.libelle), _titre(r.libelle)
        else:
            cle, nom = _cle(reg, r.prefecture, r.libelle), _titre(r.libelle)
        rows.append(dict(territoire_id_2010=int(r.idx), niveau=r.niveau, niveau_feuille=r.niveau_feuille, nom=nom, cle_hierarchique=cle,
                         region_10=reg, prefecture=r.prefecture, canton=r.canton, sous_localite=r.sous_localite,
                         groupe_reconstitution_agoe=bool(r.groupe_reconstitution_agoe), population_2010=int(r.valeur),
                         libelle_brut=r.libelle_brut, ligne_source_2010=int(r.ligne)))
    d = pd.DataFrame(rows)
    dup = d.cle_hierarchique.duplicated(keep=False)
    if dup.any():
        d.loc[dup, "cle_hierarchique"] = d[dup].cle_hierarchique + "#" + (d[dup].groupby("cle_hierarchique").cumcount() + 1).astype(str)
    return d
