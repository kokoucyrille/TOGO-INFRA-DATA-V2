#!/usr/bin/env python3
"""
ÉTAPE 0 — Exploration, vérification du §2 du prompt V3.1, faisabilité (Défi 2 Togo).

Usage :  python etape0_exploration.py [DATA-DEFI-2.zip] [dossier_sortie]
Sorties : data_inventory.csv, verification_affirmations.csv, crosswalk_propose_2010_2022.csv
Reproductible : repart de l'archive brute, chemins relatifs, aucune saisie manuelle de valeurs.
"""
import re, sys, json, glob, tempfile, zipfile, unicodedata
from pathlib import Path
import numpy as np, pandas as pd

ZIP = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("DATA-DEFI-2.zip")
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("outputs/etape0")
OUT.mkdir(parents=True, exist_ok=True)
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
pd.set_option("display.max_rows", 200); pd.set_option("display.max_colwidth", 70)

# ───────────────────────── 0. Extraction ─────────────────────────
TMP = Path(tempfile.mkdtemp())
zipfile.ZipFile(ZIP).extractall(TMP)
for z in list(TMP.rglob("*.zip")):                       # zips imbriqués (versions 2026)
    zipfile.ZipFile(z).extractall(z.parent / "z2026")
def find(pattern, exclude=None):
    c = [p for p in TMP.rglob(pattern) if not exclude or exclude not in str(p)]
    assert len(c) == 1, (pattern, c); return c[0]
P = dict(
    pop2022=find("observationdata-kwwolwb.csv"), pop2010=find("observationdata-sapxctg.csv"),
    elec=find("observationdata-puncgpd.csv"), etat_civil=find("observationdata-vrsicxf.csv"),
    identite=find("observationdata-fsemhj.csv"),
    ceet_2024=find("file-agences-ceet-*.csv"), tde_2024=find("file-agences-togolaise-des-eaux-tde-*.csv"),
    meta_ceet=find("agences-ceet.csv"), meta_tde=find("agences-togolaise-des-eaux-tde-.csv"),
    ceet_2026=find("file-Agences - CEET-*.csv"), tde_2026=find("file-Agences - Togolaise des Eaux (TdE)-*.csv"),
)
rd = lambda k: pd.read_csv(P[k], dtype=str, keep_default_na=False, encoding="utf-8")

# ───────────────────────── 1. Outils ─────────────────────────
def norm(s):
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c)).upper().replace("’", "'")
    return re.sub(r"\s+", " ", re.sub(r"[-_/']", " ", s)).strip()

REG6 = {"SAVANES", "KARA", "CENTRALE", "PLATEAUX", "MARITIME", "DAGL"}
def build_hierarchy_2022(df):
    """Liste plate → niveaux, reconstruits par l'ordre des lignes ET validés par somme."""
    names = df["découpage-administratif"].str.strip().tolist(); vals = df["Value"].astype(int).tolist(); n = len(names)
    kind = [None] * n; kind[0] = "national"; reg = [None] * n; cur = None
    for i in range(1, n):
        if names[i] in REG6: kind[i] = "region"; cur = names[i]
        reg[i] = cur
    for i in range(1, n):
        if kind[i] is None and re.search(r"\d$", names[i]):
            if reg[i] == "DAGL" and not re.match(r"^(GOLFE|AGOE-NYIVE) \d$", names[i]): continue   # quartiers (KELEGOUGAN1…)
            kind[i] = "commune"
    for i in range(1, n):                                   # préfecture = somme des communes qui suivent
        if kind[i] is None:
            s, j = 0, i + 1
            while j < n and s < vals[i] and kind[j] != "region":
                if kind[j] == "commune": s += vals[j]
                j += 1
            if s == vals[i] and i + 1 < n and any(k == "commune" for k in kind[i + 1:j]): kind[i] = "prefecture"
    kind = [k or "feuille" for k in kind]
    pref = com = None; P_, C_, CID = [], [], []
    for i, k in enumerate(kind):
        if k == "prefecture": pref, com = names[i], None
        elif k in ("region", "national"): pref = com = None
        elif k == "commune": com = i
        P_.append(pref if k not in ("region", "national") else None)
        C_.append(com if k == "feuille" else None)
    return pd.DataFrame(dict(ligne=np.arange(n) + 2, libelle_brut=names, valeur=vals, niveau=kind,
                             region_6=reg, prefecture=P_, commune_id=C_))

REG10 = ["LOME", "MARITIME", "PLATEAUX", "CENTRALE", "KARA", "SAVANES"]
def build_hierarchy_2010(df):
    names = df["indicateurs"].str.strip().tolist(); vals = df["Value"].astype(int).tolist(); n = len(names)
    kind = [None] * n; kind[0] = "national"; pos = []; last = 0
    for r in REG10:
        i = next(j for j in range(last + 1, n) if names[j] == r); pos.append(i); kind[i] = "region"; last = i
    pref = [None] * n; reg = [None] * n
    for k, i in enumerate(pos):
        end = (pos + [n])[k + 1]; j = i + 1
        for t in range(i, end): reg[t] = names[i]
        while j < end:
            s, t = 0, j + 1
            while t < end and s < vals[j]: s += vals[t]; t += 1
            if s == vals[j] and t > j + 1:
                kind[j] = "prefecture"
                for u in range(j, t): pref[u] = names[j]
                j = t
            else: kind[j] = "NON_RECONSTITUE"; j += 1
    kind = [k or "feuille" for k in kind]
    return pd.DataFrame(dict(ligne=np.arange(n) + 2, libelle_brut=names, valeur=vals, niveau=kind, region_10=reg, prefecture=pref))

V = []   # table de vérification
def chk(sec, aff, attendu, obtenu, ok=None, statut=None, note=""):
    st = statut or ("CONFIRMÉ" if (ok if ok is not None else attendu == obtenu) else "ÉCART")
    V.append(dict(section=sec, affirmation=aff, attendu=attendu, obtenu=obtenu, statut=st, note=note))
fmt = lambda x: f"{x:,.0f}".replace(",", " ")

# ───────────────────────── 2. data_inventory ─────────────────────────
rows = []
for k in P:
    d = rd(k)
    yrs = f"{d['Date'].min()}–{d['Date'].max()}" if "Date" in d else ""
    rows.append(dict(fichier=k, fichier_reel=P[k].name, lignes=len(d), colonnes=d.shape[1], annees=yrs,
                     pct_vides=round(((d == "").sum().sum()) / d.size * 100, 2), lignes_dupliquees=int(d.duplicated().sum())))
inv = pd.DataFrame(rows); inv.to_csv(OUT / "data_inventory.csv", index=False)
print("═" * 100, "\n1. DATA_INVENTORY\n"); print(inv.to_string(index=False))
print("\nNB : pop2010 = 25 % de vides → colonne `Unit` entièrement vide (aucun impact).")

# ───────────────────────── 3. Population 2022 (§2.1) ─────────────────────────
h22 = build_hierarchy_2022(rd("pop2022")); tot22 = h22.valeur.iloc[0]
reg = h22[h22.niveau == "region"].set_index("libelle_brut").valeur
pr = h22[h22.niveau == "prefecture"]; co = h22[h22.niveau == "commune"]; fe = h22[h22.niveau == "feuille"]
S = "§2.1"
chk(S, "759 lignes, 2022, sexe Total", 759, len(h22))
chk(S, "Total Togo", 8095498, tot22)
chk(S, "6 régions, somme = national", 6, len(reg), ok=len(reg) == 6 and reg.sum() == tot22)
chk(S, "DAGL = 2 188 376 (27,0 %)", "2188376 / 27,0", f"{reg['DAGL']} / {reg['DAGL']/tot22*100:.1f}", ok=reg["DAGL"] == 2188376)
chk(S, "39 préfectures", 39, len(pr))
g = pr.set_index("libelle_brut").valeur
chk(S, "Golfe 1 305 681 / Agoé-Nyivé 882 695", "1305681 / 882695", f"{g['GOLFE']} / {g['AGOE-NYIVE']}", ok=g["GOLFE"] == 1305681 and g["AGOE-NYIVE"] == 882695)
dig = h22[h22.libelle_brut.str.contains(r"\d$")]
chk(S, "121 lignes finissant par un chiffre", 121, len(dig))
chk(S, "117 communes (116 lignes + DANYI 1+2 = 2 communes)", 117, len(co) + 1)
quart = dig[dig.niveau == "feuille"].libelle_brut.tolist()
chk(S, "5 quartiers finissant par un chiffre (KELEGOUGAN1, ATIEGOU1, KELEGOUGAN 2, ATIEGOU 2, KELEGOUGAN 3)", 5, len(quart),
    ok=set(quart) == {"KELEGOUGAN1", "ATIEGOU1", "KELEGOUGAN 2", "ATIEGOU 2", "KELEGOUGAN 3"})
bad = [r for r, gp in pr.groupby("region_6") if gp.valeur.sum() != reg[r]]
chk(S, "région = somme des préfectures (écarts)", 0, len(bad))
bad = [p for p, gp in co.groupby("prefecture") if gp.valeur.sum() != pr[pr.libelle_brut == p].valeur.iloc[0]]
chk(S, "préfecture = somme des communes (écarts)", 0, len(bad))
leaf = fe.groupby("commune_id").agg(n=("valeur", "size"), s=("valeur", "sum"))
cj = h22.loc[co.index.intersection(h22.index)].copy(); cj = cj.join(leaf, how="left")
chk(S, "commune = somme de ses feuilles (par identifiant positionnel, 116 communes)", 0, int((cj.valeur != cj.s).sum()))
chk(S, "somme de toutes les feuilles = total national (pas de double comptage)", tot22, int(fe.valeur.sum()),
    note="Les 6 communes à canton unique (ex. OGOU 3 = GLEI) ne posent problème que si on somme commune + feuille.")
dup = co.libelle_brut[co.libelle_brut.duplicated(keep=False)]
chk(S, "AMOU 2 et EST-MONO 1 en double (2e = Amou 3 / Est-Mono 3)", "2 libellés", f"{dup.nunique()} libellés", ok=set(dup) == {"AMOU 2", "EST-MONO 1"})
ccount = pd.Series({"cantons (hors DAGL)": int((fe.region_6 != "DAGL").sum()), "quartiers (DAGL)": int((fe.region_6 == "DAGL").sum())})
chk(S, "[NOUVEAU] décompte des feuilles", "—", f"{ccount.iloc[0]} cantons hors DAGL + {ccount.iloc[1]} quartiers DAGL", statut="INFO")
ratio = co.valeur.max() / co.valeur.min()
chk(S, "écart max/min communal 35,4× (Golfe 1 / Assoli 2)", 35.4, round(ratio, 1))
chk(S, "médiane communale ≈ 52 300", 52300, float(co.valeur.median()), ok=abs(co.valeur.median() - 52300) < 500)
chk(S, "Top 10 communes ≈ 28,7 %", 28.7, round(co.nlargest(10, "valeur").valeur.sum() / tot22 * 100, 1))

# ───────────────────────── 4. Population 2010 (§2.2) ─────────────────────────
h10 = build_hierarchy_2010(rd("pop2010")); tot10 = h10.valeur.iloc[0]
r10 = h10[h10.niveau == "region"].set_index("libelle_brut").valeur
p10 = h10[(h10.niveau == "prefecture") & (h10.region_10 != "LOME")]; g10 = p10.set_index("libelle_brut").valeur
S = "§2.2"
chk(S, "555 lignes, total 6 191 155", "555 / 6191155", f"{len(h10)} / {tot10}", ok=len(h10) == 555 and tot10 == 6191155)
chk(S, "somme des 6 blocs = national", tot10, int(r10.sum()))
chk(S, "Lomé 839 566 ; Maritime 1 760 389", "839566 / 1760389", f"{r10['LOME']} / {r10['MARITIME']}", ok=r10["LOME"] == 839566 and r10["MARITIME"] == 1760389)
chk(S, "36 préfectures hors Lomé (+ Lomé = 37 unités)", 36, len(p10))
chk(S, "Golfe 2010 = 731 942 ; Grand Lomé = 1 571 508", "731942 / 1571508", f"{g10['GOLFE']} / {r10['LOME'] + g10['GOLFE']}",
    ok=g10["GOLFE"] == 731942 and r10["LOME"] + g10["GOLFE"] == 1571508)
chk(S, "Kpendjal 155 091 (= somme des cantons) ; Oti 190 543", "155091 / 190543", f"{g10['KPENDJAL']} / {g10['OTI']}", ok=g10["KPENDJAL"] == 155091 and g10["OTI"] == 190543)
chk(S, "région = somme des préfectures (2010)", 0, sum(p10[p10.region_10 == r].valeur.sum() != r10[r] for r in ["MARITIME", "PLATEAUX", "CENTRALE", "KARA", "SAVANES"]))
chk(S, "7 libellés dupliqués dans 2010", 7, int(h10.libelle_brut.duplicated().sum()))
ag = h10[h10.libelle_brut.str.startswith(("AGOENYIVE", "VAKPOSSITO"))].valeur.sum()
ag22 = int(g["AGOE-NYIVE"]); tc = lambda a, b: ((b / a) ** (1 / 12) - 1) * 100
gl10, gl22 = int(r10["LOME"] + g10["GOLFE"]), int(reg["DAGL"])
chk(S, "[NOUVEAU] reconstitution Agoé-Nyivé par préfixes `AGOENYIVE =` + `VAKPOSSITO =` = flag MEDIUM", "MEDIUM",
    f"2010={fmt(ag)} → 2022={fmt(ag22)} (×{ag22/ag:.1f}, TCAM {tc(ag, ag22):.1f} %/an) vs Grand Lomé {tc(gl10, gl22):.1f} %/an",
    statut="ÉCART", note=f"2010 : {int(h10.libelle_brut.str.startswith(('AGOENYIVE','VAKPOSSITO')).sum())} localités préfixées couvrant {fmt(ag)} hab. ; 2022 : {int(((h22.niveau=='feuille')&(h22.prefecture=='AGOE-NYIVE')).sum())} quartiers sur 6 communes, {fmt(ag22)} hab. Périmètres non équivalents → proposé : LOW pour Golfe et Agoé-Nyivé séparés, HIGH pour le Grand Lomé fusionné.")

# ───────────────────────── 5. Électricité (§2.3) ─────────────────────────
e = rd("elec"); e.columns = ["indicateur", "unite_nom", "libelle", "unit", "annee", "valeur"]
e["valeur"] = e.valeur.astype(float); e["annee"] = e.annee.astype(int)
t = e[e.libelle.str.startswith("Taux")]; bt = e[e.libelle.str.startswith("Nombre")]
S = "§2.3"
chk(S, "282 lignes, 2018–2021, 2 indicateurs", "282 / 2018-2021 / 2", f"{len(e)} / {e.annee.min()}-{e.annee.max()} / {e.libelle.nunique()}", ok=len(e) == 282 and e.libelle.nunique() == 2)
bt21 = bt[bt.annee == 2021].unite_nom.tolist()
chk(S, "Abonnés BT : 2018–2020 seulement", "2018–2020", f"2018–2020 pour {bt[bt.annee==2020].unite_nom.nunique()} unités ; 2021 pour seulement {len(bt21)} d'entre elles ({', '.join(bt21)})",
    statut="ÉCART", note="Écart mineur sans impact sur l'IPT (BT non utilisé). Valeurs 2021 = 364 / 427 / 426.")
allu = set(e.unite_nom); regs = {u for u in allu if u.startswith("REGION")}
units = sorted(allu - regs - {"ENSEMBLE DU PAYS", "LOME COMMUNE + GOLFE"})
grp = [u for u in units if "+" in u]
chk(S, "33 unités d'analyse = 27 isolées + 6 groupes", "33 = 27 + 6", f"{len(units)} = {len(units)-len(grp)} + {len(grp)}", ok=len(units) == 33 and len(grp) == 6)
a = e[e.unite_nom == "LOME"].sort_values(["libelle", "annee"])[["libelle", "annee", "valeur"]].reset_index(drop=True)
b = e[e.unite_nom == "LOME COMMUNE + GOLFE"].sort_values(["libelle", "annee"])[["libelle", "annee", "valeur"]].reset_index(drop=True)
chk(S, "LOME ≡ LOME COMMUNE + GOLFE (doublon strict)", True, bool(a.equals(b)))
over = t[t.valeur > 100][["unite_nom", "annee", "valeur"]].values.tolist()
chk(S, "taux > 100 % : Agoé-Nyivé 2019 (106,52) ; Zio 2021 (106,84)", "2 valeurs", f"{len(over)} : {over}", ok=len(over) == 2)
chk(S, "BLITTA 2018 absent", True, not ((t.unite_nom == "BLITTA") & (t.annee == 2018)).any())
tw = t.pivot_table(index="unite_nom", columns="annee", values="valeur")
chk(S, "National 45,09 → 57,82", "45.09 → 57.82", f"{tw.loc['ENSEMBLE DU PAYS', 2018]} → {tw.loc['ENSEMBLE DU PAYS', 2021]}", ok=(tw.loc["ENSEMBLE DU PAYS", 2018], tw.loc["ENSEMBLE DU PAYS", 2021]) == (45.09, 57.82))
chk(S, "sauts Agoé-Nyivé 65,96→106,52 ; Yoto 41,29→62,40 ; Maritime 44,86→64,00 ; Kpélé 10,91→9,31", "oui", "oui",
    ok=(tw.loc["AGOENYIVE", 2018], tw.loc["AGOENYIVE", 2019], tw.loc["YOTO", 2020], tw.loc["YOTO", 2021], tw.loc["REGION MARITIME", 2018], tw.loc["REGION MARITIME", 2019], tw.loc["KPELE", 2018], tw.loc["KPELE", 2021]) == (65.96, 106.52, 41.29, 62.40, 44.86, 64.00, 10.91, 9.31))
# couverture 33 unités ↔ 39 préfectures
alias = {"LOME": "GOLFE", "AGOENYIVE": "AGOE NYIVE", "PLAINE DE MO": "MO"}
p22k = {norm(x): (x, v) for x, v in zip(pr.libelle_brut.replace({"TOTOAL AVE": "AVE"}), pr.valeur)}
mp = [(u, alias.get(norm(p), norm(p))) for u in units for p in u.split("+")]
cov = pd.DataFrame(mp, columns=["unite", "k"]); cov["ok"] = cov.k.isin(p22k)
chk(S, "33 unités couvrent les 39 préfectures, sans trou ni chevauchement", "39 / 0 chevauchement", f"{cov.k.nunique()} / {int(cov.k.duplicated().sum())}",
    ok=cov.ok.all() and cov.k.nunique() == 39 and not cov.k.duplicated().any(), note="12 préfectures dans des groupes, 27 hors groupe.")
pop_u = cov.assign(pop=cov.k.map(lambda k: p22k[k][1])).groupby("unite")["pop"].sum()
chk(S, "[NOUVEAU] somme des populations des 33 unités = total national", tot22, int(pop_u.sum()))
# cohérence régionale 2021 (contrôle §6.3)
reg5 = {"REGION DES SAVANES": "SAVANES", "REGION DE LA KARA": "KARA", "REGION CENTRALE": "CENTRALE", "REGION DES PLATEAUX": "PLATEAUX", "REGION MARITIME": "MARITIME"}
reg_of = h22[h22.niveau == "prefecture"].assign(k=lambda d: d.libelle_brut.replace({"TOTOAL AVE": "AVE"}).map(norm)).set_index("k").region_6.replace({"DAGL": "MARITIME"})
u2r = cov.assign(r5=cov.k.map(reg_of)).groupby("unite").r5.first()
tu = tw[2021].reindex(units); gap = []
for lab, r in reg5.items():
    us = u2r[u2r == r].index; w = (tu[us].clip(upper=100) * pop_u[us]).sum() / pop_u[us].sum()
    gap.append((r, round(w, 1), tw.loc[lab, 2021], round(w - tw.loc[lab, 2021], 1)))
natw = (tu.clip(upper=100) * pop_u[units]).sum() / pop_u[units].sum()
chk(S, "[NOUVEAU] cohérence taux régionaux 2021 vs moyenne pondérée des unités (pop. 2022)", "écart faible",
    "; ".join(f"{r}: {w} vs {p} ({d:+} pp)" for r, w, p, d in gap) + f" ; national {natw:.1f} vs 57,82",
    statut="ÉCART", note="Maritime +11,9 pp et national −3,3 pp non reproductibles → dénominateur/périmètre des taux inconnu (PROXY confirmé). Aucune explication retenue.")

# ───────────────────────── 6. Agences (§2.4) ─────────────────────────
ceet, tde = rd("ceet_2024"), rd("tde_2024")
S = "§2.4"
chk(S, "CEET 34 agences, TdE 59 agences, 14 colonnes", "34 / 59 / 14", f"{len(ceet)} / {len(tde)} / {ceet.shape[1]}", ok=(len(ceet), len(tde), ceet.shape[1]) == (34, 59, 14))
m1, m2 = rd("meta_ceet"), rd("meta_tde")
chk(S, "métadonnées : 204 champs (CEET et TdE identiques)", 204, len(m1), ok=len(m1) == 204 and m1.equals(m2))
al = pd.concat([ceet.assign(service="CEET"), tde.assign(service="TdE")], ignore_index=True)
al["statut"] = al.activite_statut.str.strip("{}").str.strip(); al["public"] = ~al.activite_categorie.str.contains("Admin|Technique")
al["pref_n"] = al.prefecture_nom_bdd.map(norm); al["com_n"] = al.commune_nom_bdd.map(norm)
sc = al.groupby(["service", "statut"]).size().to_dict()
chk(S, "Statuts CEET : Utilisé 27, N/a 4, Nsp 3", "27/4/3", f"{sc.get(('CEET','Utilise'))}/{sc.get(('CEET','N/a'))}/{sc.get(('CEET','Nsp'))}", ok=(sc.get(("CEET", "Utilise")), sc.get(("CEET", "N/a")), sc.get(("CEET", "Nsp"))) == (27, 4, 3))
chk(S, "Statuts TdE : Utilisé 47, Nsp 7, En constr. 2, Inachevé 2, N/a 1", "47/7/2/2/1",
    f"{sc.get(('TdE','Utilise'))}/{sc.get(('TdE','Nsp'))}/{sc.get(('TdE','En construction'))}/{sc.get(('TdE','Inacheve'))}/{sc.get(('TdE','N/a'))}",
    ok=(sc.get(("TdE", "Utilise")), sc.get(("TdE", "Nsp")), sc.get(("TdE", "En construction")), sc.get(("TdE", "Inacheve")), sc.get(("TdE", "N/a"))) == (47, 7, 2, 2, 1),
    note="Valeurs brutes entre accolades `{Utilise}` et sans accents ; à nettoyer à l'étape 1.")
nsp = al.etab_creation_date.value_counts()
chk(S, "[NOUVEAU] variantes de `Nsp` dans etab_creation_date", "1 forme", f"{[repr(k) for k in nsp.index if 'Nsp' in k]} → {[int(nsp[k]) for k in nsp.index if 'Nsp' in k]}", statut="ÉCART", note="`Nsp` et `Nsp ` (espace final) : strip obligatoire.")
chk(S, "Date de création aberrante 1076 (CEET)", "1 ligne", f"{int((al.etab_creation_date.str.strip()=='1076').sum())} : {al[al.etab_creation_date.str.strip()=='1076'].etab_nom.tolist()}", ok=(al.etab_creation_date.str.strip() == "1076").sum() == 1)
cat = al.groupby("activite_categorie").size().to_dict()
chk(S, "Catégories : 5 (3 publiques-types + Admin/Technique)", 5, len(cat), note=str(cat))
xy = al.geometry.str.extract(r"POINT \(([-\d\.]+) ([-\d\.]+)\)").astype(float); xy.columns = ["lon", "lat"]
chk(S, "coordonnées valides, dans la boîte du Togo, sans doublon", "0 / 0 / 0",
    f"{int(xy.lon.isna().sum())} / {int((~xy.lon.between(-0.2,1.9)|~xy.lat.between(6.0,11.2)).sum())} / {int(xy.duplicated().sum())}", ok=xy.isna().sum().sum() == 0 and not xy.duplicated().any())
prefset = {norm(x) for x in p22k}; comset = {norm(x) for x in co.libelle_brut.replace({"BINAH2": "BINAH 2"})} | {"DANYI 1", "DANYI 2"}
comset -= {"DANYI 1+DANYI 2", "DANYI 1 DANYI 2"}
chk(S, "jointure préfectures : 24 CEET / 33 TdE toutes appariées au référentiel", "24 / 33 / 100 %", f"{al[al.service=='CEET'].pref_n.nunique()} / {al[al.service=='TdE'].pref_n.nunique()} / {al.pref_n.isin(prefset).mean():.0%}",
    ok=al.pref_n.isin(prefset).all() and al[al.service == 'CEET'].pref_n.nunique() == 24 and al[al.service == 'TdE'].pref_n.nunique() == 33)
chk(S, "[NOUVEAU] jointure communes (noms normalisés + corrections documentées)", "100 %", f"{al.com_n.isin(comset).mean():.0%}", ok=al.com_n.isin(comset).all(), note="BINAH2→BINAH 2 ; AMOU 2(2e)→AMOU 3 ; EST-MONO 1(2e)→EST-MONO 3 ; DANYI 1+2 → Danyi 1 et Danyi 2 non séparables en population.")
def absents(d): 
    c, td = set(d[d.service == "CEET"].pref_n), set(d[d.service == "TdE"].pref_n)
    return [p for p in prefset if p not in c], [p for p in prefset if p not in td], [p for p in prefset if p not in c and p not in td]
dA, dC = absents(al), absents(al[al.public & (al.statut == "Utilise")])
chk(S, "15 préfectures sans CEET / 6 sans TdE / 4 sans aucun", "15 / 6 / 4", f"déf. A (toute ligne) : {len(dA[0])} / {len(dA[1])} / {len(dA[2])}", ok=(len(dA[0]), len(dA[1]), len(dA[2])) == (15, 6, 4))
chk(S, "[NOUVEAU] mêmes comptes avec 'agence OUVERTE' (public + Utilisé) = définition de c6 §7", "15 / 6 / 4", f"{len(dC[0])} / {len(dC[1])} / {len(dC[2])}",
    statut="ÉCART", note=f"Deux définitions de « sans agence » coexistent dans le prompt. Sans agence ouverte ET sans aucune : {sorted(dC[2])}")
c26, t26 = rd("ceet_2026"), rd("tde_2026")
same = lambda a_, b_: set(map(tuple, a_.drop(columns="FID").values.tolist())) == set(map(tuple, b_.drop(columns="FID").values.tolist()))
chk(S, "versions 2026 vs 2024 : même contenu ?", "à comparer", f"CEET identique hors FID : {same(ceet, c26)} ; TdE : {same(tde, t26)}", statut="INFO",
    note="Seul l'identifiant FID diffère (régénéré à l'export). Utiliser les CSV 2024 ; les JSON (GeoJSON, points seuls) et XLSX 2026 sont redondants.")

# ───────────────────────── 7. État civil (§2.5) ─────────────────────────
s = rd("etat_civil"); s.columns = ["indicateur_brut", "sexe", "unit", "annee", "valeur"]
s["valeur"] = s.valeur.astype(float); s["annee"] = s.annee.astype(int); s["ligne"] = np.arange(len(s)) + 2
s["ind"] = s.indicateur_brut.str.replace(r"\s+", " ", regex=True).str.strip()
s["rang"] = s.groupby(["indicateur_brut", "sexe", "annee"]).cumcount() + 1
S = "§2.5"
chk(S, "184 lignes, 11 indicateurs, sexes Tota/Homme/Femme, 2014–2019, pas de territoire", "184 / 11", f"{len(s)} / {s.indicateur_brut.nunique()}", ok=len(s) == 184 and s.indicateur_brut.nunique() == 11 and set(s.sexe) == {"Tota", "Homme", "Femme"})
dl = s[s.indicateur_brut.str.contains("scolaris")]
chk(S, "[NOUVEAU] un libellé brut porte DEUX séries (« enfants scolarisés ne disposant pas d'acte de naissance »)", "11 séries", f"12 séries : A lignes {dl[dl.rang==1].ligne.min()}–{dl[dl.rang==1].ligne.max()} (313 346–411 310) ; B lignes {dl[dl.rang==2].ligne.min()}–{dl[dl.rang==2].ligne.max()} (0–3 219)",
    statut="ÉCART", note="Ne jamais pivoter/moyenner sans `rang` (une moyenne naïve fusionne A et B). Sens de B non documenté → à clarifier ; ne pas agréger.")
sk = s[s.rang == 1].assign(ind_s=lambda d: d.ind)
def val(ind, sx, an, rg=1): 
    r = s[(s.ind.str.startswith(ind)) & (s.sexe == sx) & (s.annee == an) & (s.rang == rg)].valeur
    return float(r.iloc[0]) if len(r) else np.nan
x45 = [val("Nombre d'enfants enregistrés dans les délais", "Tota", y) for y in range(2014, 2020)]
chk(S, "enfants enregistrés < 45 j : 118 717 → 170 266 → 138 225 → 140 726 → 134 483 → 103 893", "6 valeurs", "identiques", ok=x45 == [118717, 170266, 138225, 140726, 134483, 103893])
mh = [val("Nombre d'enfants mort nés enregistrés hors", "Tota", y) for y in range(2014, 2020)]
chk(S, "2015 morts-nés hors FS = 438 210 (vs 93–333)", "438210 ; 93–333", f"{mh[1]:.0f} ; {min(mh[0], *mh[2:]):.0f}–{max(mh[0], *mh[2:]):.0f}", ok=mh[1] == 438210 and min(mh[0], *mh[2:]) == 93 and max(mh[0], *mh[2:]) == 333)
sa = [val("Nombre d'enfants scolarisés", "Tota", y) for y in range(2014, 2020)]
chk(S, "2015 scolarisés sans acte = 2 357 (série A ; vs 313 000–411 000)", "2357", f"{sa[1]:.0f} ; autres années {min(sa[0], *sa[2:]):.0f}–{max(sa[0], *sa[2:]):.0f}", ok=sa[1] == 2357)
vf = [val("Nombre de naissances vivantes enregistrées dans les formations", "Tota", y) for y in range(2014, 2020)]
chk(S, "2015 naissances vivantes en FS = 11 139 (vs 56 000–104 000)", "11139", f"{vf[1]:.0f} ; autres {min(vf[0], *vf[2:]):.0f}–{max(vf[0], *vf[2:]):.0f}", ok=vf[1] == 11139)
ne = [val("Nombre de naissances enregistrées", "Tota", y) for y in range(2014, 2020)]
chk(S, "Total « naissances enregistrées » = 0 en 2016, 2018, 2019", "0 / 0 / 0", f"{ne[2]} / {ne[4]} / {ne[5]}", ok=(ne[2], ne[4], ne[5]) == (0, 0, 0), note=f"Seule 2015 est renseignée ({ne[1]:.0f}) ; 2014 et 2017 absentes.")
sh19, sf19 = val("Nombre d'enfants scolarisés", "Homme", 2019), val("Nombre d'enfants scolarisés", "Femme", 2019)
chk(S, "2019 scolarisés sans acte : Homme 316 193 vs Femme 95 117 (série A)", "316193 / 95117", f"{sh19:.0f} / {sf19:.0f}", ok=sh19 == 316193 and sf19 == 95117)
js, jt = [val("Nombre de jugements supplétifs (", "Tota", 2017), val("Nombre de jugements supplétifs transcrits", "Tota", 2017)]
chk(S, "2017 jugements supplétifs = transcrits = 48 213", 48213, f"{js:.0f} = {jt:.0f}", ok=js == jt == 48213)
w = s.assign(serie=s.ind.str[:60] + np.where(s.rang > 1, " [B]", "")).pivot(index=["serie", "annee"], columns="sexe", values="valeur")
c = w.dropna(subset=["Tota", "Homme", "Femme"])
chk(S, "Hommes + Femmes = Total", 0, int(((c.Homme + c.Femme - c.Tota).abs() > .5).sum()), note=f"{len(c)} couples série×année testés.")
mq = w[w[["Homme", "Femme"]].isna().any(axis=1)].reset_index().groupby("annee").size().to_dict()
chk(S, "détail par sexe manquant surtout en 2014 et 2017", "2014, 2017", str(mq), ok=mq.get(2014, 0) >= 5 and mq.get(2017, 0) >= 5)
chk(S, "Aucun dénominateur de naissances attendues → taux d'enregistrement impossible", True, True, note="Aucune colonne de naissances attendues/estimées dans les 5 jeux.")

# ───────────────────────── 8. Identité (§2.6) ─────────────────────────
i = rd("identite"); i.columns = ["indicateur", "type", "unit", "annee", "valeur"]; i["valeur"] = i.valeur.astype(float); i["annee"] = i.annee.astype(int)
iw = i.pivot(index="annee", columns="type", values="valeur"); comp = [c_ for c_ in iw.columns if c_ != "TOTAL"]
both = iw.dropna(subset=["TOTAL"] + comp)
S = "§2.6"
chk(S, "33 lignes, 4 types, 2014–2022", "33 / 4", f"{len(i)} / {i.type.nunique()}", ok=len(i) == 33 and i.type.nunique() == 4)
chk(S, "2021 manquant pour CNI, cartes pro, TOTAL ; passeports 2021 = 66 938", "oui", f"manquants 2021 : {iw.loc[2021][iw.loc[2021].isna()].index.tolist()} ; passeports {iw.loc[2021,'Passeports']:.0f}", ok=iw.loc[2021, "Passeports"] == 66938 and iw.loc[2021].isna().sum() == 3)
chk(S, "TOTAL = somme des composantes là où tout est présent", f"{len(both)} années", f"{int((both.TOTAL == both[comp].sum(axis=1)).sum())}/{len(both)}", ok=(both.TOTAL == both[comp].sum(axis=1)).all(), note="Vérifié sur les 8 années disponibles (le prompt n'en citait que 2).")
chk(S, "Pic 2019 (281 285), « creux 2020 » (236 212), 2022 : 219 331", "281285 / 236212 / 219331", f"{iw.TOTAL.idxmax()}={iw.TOTAL.max():.0f} / 2020={iw.loc[2020,'TOTAL']:.0f} / 2022={iw.loc[2022,'TOTAL']:.0f}", statut="NUANCE",
    note=f"2022 est plus bas que 2020. Minimum de la série : {iw.TOTAL.idxmin()} ({iw.TOTAL.min():.0f}). CNI 2022 = {iw.loc[2022,'Cartes Nationales d’identité']:.0f} (−32 % vs 2019) ; passeports 2022 = {iw.loc[2022,'Passeports']:.0f} (+10 %).")

# ───────────────────────── 9. Crosswalk 2010→2022 proposé ─────────────────────────
# Indicateur de stabilité des LIBELLÉS (pas des périmètres) : part de la pop. 2010 de la préfecture
# couverte par des cantons retrouvés à l'identique dans la même préfecture en 2022.
l22 = fe.assign(k=fe.libelle_brut.map(norm), pk=fe.prefecture.replace({"TOTOAL AVE": "AVE"}).map(norm))
h10l = h10[(h10.niveau == "feuille") & (h10.region_10 != "LOME")].copy()
h10l["k"] = h10l.libelle_brut.map(lambda x: x.split("=")[-1]).map(norm)
h10l["pk"] = h10l.prefecture.replace({"Sous Prefecture de MO": "MO"}).map(norm)
s22 = l22.groupby("pk").k.apply(set).to_dict()
sib = {"KPENDJAL": {"KPENDJAL", "KPENDJAL OUEST"}, "OTI": {"OTI", "OTI SUD"}}
h10l["m"] = h10l.apply(lambda r: any(r.k in s22.get(p_, set()) for p_ in sib.get(r.pk, {r.pk})), axis=1)
covc = h10l.groupby("pk").apply(lambda d: d.loc[d.m, "valeur"].sum() / d.valeur.sum(), include_groups=False)
# Transfert inter-préfectures détecté (nom absent de Zio 2022, présent sous Agoé-Nyivé 2022) :
ADETI10 = h10l[h10l.k.str.contains("ADETI")]; ADETI22 = l22[l22.k.str.contains("ADETI")]
assert len(ADETI10) == 1 and (ADETI10.pk == "ZIO").all() and (ADETI22.pk == "AGOE NYIVE").all() and not l22[(l22.pk == "ZIO")].k.str.contains("ADETI").any()
# Reconstitution des scissions par cantons (alias documenté : PAPRI/KPENDJAGA → Kpendjal-Ouest)
ALIAS = {"PAPRI KPENDJAGA": "KPENDJAL OUEST"}
def recon(parent, part):
    c = h10l[h10l.pk == parent].copy()
    c["vers"] = [ALIAS.get(k) or next((q for q in sib[parent] if k in s22.get(q, set())), None) for k in c.k]
    return c, int(c.loc[c.vers == part, "valeur"].sum()), bool(c.vers.isna().sum() == 0), bool(c.k.isin(ALIAS).any() and (c.loc[c.k.isin(ALIAS), "vers"] == part).any())
tcam = lambda a_, b_: ((b_ / a_) ** (1 / 12) - 1) * 100
rows = []
def add(pref, origine, typ, p10_, p22_, flag, motif, niveau="préfecture"):
    rows.append(dict(pref_2022=pref, origine_2010=origine, niveau_comparaison=niveau, type_correspondance=typ, pop_2010=p10_, pop_2022=p22_,
                     tcam_pct=(tcam(p10_, p22_) if pd.notna(p10_) else np.nan), flag_propose=flag, motif=motif))
for k, (lab, pop22) in p22k.items():
    if k in ("AGOE NYIVE", "GOLFE"): continue
    if k in ("KPENDJAL", "KPENDJAL OUEST", "OTI", "OTI SUD"):
        parent = "KPENDJAL" if k.startswith("KPENDJAL") else "OTI"
        c, pop10, complet, alias_used = recon(parent, k)
        add(lab, f"{parent} (2010) — cantons {k.title()}", "scission", pop10, pop22, "MEDIUM" if (alias_used or not complet) else "HIGH",
            "Reconstitué par cantons" + (" avec alias PAPRI/KPENDJAGA→Kpendjal-Ouest (à valider)" if alias_used else " (tous les cantons appariés, sans alias)"))
        continue
    pc = float(covc.get(k, np.nan)); pop10 = int(g10[next(x for x in g10.index if norm(x.replace("Sous Prefecture de MO", "MO")) == k)])
    flag, motif = ("HIGH" if pc >= .90 else "MEDIUM"), f"{pc:.0%} de la pop. 2010 en cantons retrouvés à l'identique" + ("" if pc >= .90 else " (libellés hétérogènes)")
    if k == "ZIO": flag, motif = "MEDIUM", motif + " ; canton ADETI KOPE (20 238 hab., Zio 2010) retrouvé sous Agoé-Nyivé 2022 → périmètre modifié"
    add(lab, lab, "exacte", pop10, pop22, flag, motif)
for part, par in (("KPENDJAL", "KPENDJAL"), ("OTI", "OTI")):
    pa, pb = {"KPENDJAL": ("KPENDJAL", "KPENDJAL-OUEST"), "OTI": ("OTI", "OTI-SUD")}[part]
    add(f"{pa} + {pb}", f"{par} (2010)", "scission (union)", int(g10[par]), int(g[pa] + g[pb]), "HIGH", "Union exacte des deux préfectures issues de la scission", "union")
add("GRAND LOMÉ = Golfe + Agoé-Nyivé", "LOME + GOLFE (2010)", "fusion/scission (union)", gl10, gl22, "HIGH",
    "Union des 2 préfectures du DAGL vs Lomé + Golfe 2010 ; réserve : Adéti Kopé (~20 k hab., Zio 2010) est passé à Agoé-Nyivé (< 1,3 % de la base)", "union")
add("GOLFE", "LOME + GOLFE (2010)", "fusion/scission", np.nan, int(g["GOLFE"]), "LOW", "Pris seul, Golfe 2022 n'a pas d'équivalent 2010 : utiliser le Grand Lomé fusionné")
add("AGOE-NYIVE", "GOLFE (2010) — localités AGOENYIVE =/VAKPOSSITO =", "reconstitution", np.nan, ag22, "LOW",
    f"Reconstitution par préfixes = {fmt(ag)} hab. → TCAM implicite {tcam(ag, ag22):.1f} %/an, implausible : périmètres non équivalents")
xw = pd.DataFrame(rows)
xw["ordre"] = xw.flag_propose.map({"HIGH": 0, "MEDIUM": 1, "LOW": 2}); xw = xw.sort_values(["ordre", "niveau_comparaison", "pref_2022"]).drop(columns="ordre").reset_index(drop=True)
xw.to_csv(OUT / "crosswalk_propose_2010_2022.csv", index=False)

# ───────────────────────── 10. Sorties ─────────────────────────
Vdf = pd.DataFrame(V); Vdf.to_csv(OUT / "verification_affirmations.csv", index=False)
print("\n" + "═" * 100, "\n2. VÉRIFICATION DES AFFIRMATIONS DU §2 (par code)\n")
print(Vdf.statut.value_counts().to_string())
print("\n— Écarts, nuances et nouveautés :\n")
for _, r in Vdf[Vdf.statut.isin(["ÉCART", "NUANCE"])].iterrows():
    print(f"[{r.statut}] {r.section} {r.affirmation}\n     attendu : {r.attendu}\n     obtenu  : {r.obtenu}\n     note    : {r.note}\n")
print("═" * 100, "\n3. CROSSWALK 2010→2022 PROPOSÉ (préfectures)\n")
print(xw.assign(tcam_pct=xw.tcam_pct.round(2)).drop(columns=["motif", "origine_2010"]).to_string(index=False))
print("\nRépartition des flags proposés (lignes préfecture) :", xw[xw.niveau_comparaison == "préfecture"].flag_propose.value_counts().to_dict(),
      "| lignes union :", xw[xw.niveau_comparaison == "union"].flag_propose.value_counts().to_dict())
print("\nFichiers écrits dans", OUT.resolve())
