"""Préparation (nettoyage) des jeux de données. Les valeurs brutes sont TOUJOURS conservées ;
les anomalies sont signalées par des drapeaux et consignées dans `anomaly_log`, jamais corrigées en silence.
"""
import re
import numpy as np
import pandas as pd
from .territoire import norm

SEUIL_SAUT_PP = 15.0          # saut annuel du taux d'accès jugé suspect (points de pourcentage) — paramètre documenté
ALIAS_UNITE = {"LOME": "GOLFE", "AGOENYIVE": "AGOE NYIVE", "PLAINE DE MO": "MO"}   # nom du fichier électricité → préfecture 2022


def _a(fichier, ligne, champ, valeur, nature, traitement, impact):
    return dict(fichier=fichier, ligne=ligne, champ=champ, valeur=valeur, nature=nature, traitement=traitement, impact=impact)


# ═══════════════════════════ ÉLECTRICITÉ ═══════════════════════════
def prepare_electricity(df: pd.DataFrame, h22: pd.DataFrame):
    """Retourne (electricite_long, unites_electriques, unite_par_pref, anomalies)."""
    f = "observationdata-puncgpd.csv"
    e = df.copy()
    e.columns = ["indicateur_source", "unite_nom", "libelle", "unit", "annee", "valeur"]
    e["ligne"] = np.arange(len(e)) + 2
    e["valeur"] = e.valeur.astype(float)
    e["annee"] = e.annee.astype(int)
    an = []
    # doublon strict LOME ≡ LOME COMMUNE + GOLFE
    dbl = e[e.unite_nom == "LOME COMMUNE + GOLFE"]
    an.append(_a(f, f"{dbl.ligne.min()}–{dbl.ligne.max()}", "préfecture", "LOME COMMUNE + GOLFE", "Doublon strict de `LOME` (7 lignes identiques)",
                 "Lignes écartées de l'analyse (conservées dans le fichier brut)", "Évite un double comptage de Golfe"))
    e = e[e.unite_nom != "LOME COMMUNE + GOLFE"].copy()
    e["type_unite"] = np.where(e.unite_nom == "ENSEMBLE DU PAYS", "national", np.where(e.unite_nom.str.startswith("REGION"), "region_5", "unite"))
    e["indicateur"] = np.where(e.libelle.str.startswith("Taux"), "taux_acces", "abonnes_bt")
    # rattachement unités → préfectures 2022
    prefs = h22[h22.niveau == "prefecture"].copy()
    prefs["k"] = prefs.libelle.map(norm)
    pop_par_k = dict(zip(prefs.k, prefs.valeur))
    nom_par_k = dict(zip(prefs.k, prefs.libelle))
    reg5_par_k = {k: ("MARITIME" if r == "DAGL" else r) for k, r in zip(prefs.k, prefs.region_6)}
    unites = sorted(e[e.type_unite == "unite"].unite_nom.unique())
    rows, unite_par_pref = [], {}
    for u in unites:
        ks = [ALIAS_UNITE.get(norm(p), norm(p)) for p in u.split("+")]
        assert all(k in pop_par_k for k in ks), (u, ks)
        for k in ks:
            unite_par_pref[k] = u
        rows.append(dict(unite_electrique=u, groupe="+" in u, n_prefectures=len(ks), prefectures=" + ".join(nom_par_k[k] for k in ks),
                         cles_prefectures=",".join(ks), population_2022=sum(pop_par_k[k] for k in ks), region_5=reg5_par_k[ks[0]]))
    ue = pd.DataFrame(rows)
    # --- règles de tendance (taux) ---
    t = e[e.indicateur == "taux_acces"].pivot_table(index="unite_nom", columns="annee", values="valeur")
    motifs = {}
    for u, r in t.iterrows():
        m = []
        if (r > 100).any():
            m.append("taux brut > 100 % (" + ", ".join(f"{y}: {v:.2f}" for y, v in r[r > 100].items()) + ")")
        d = r.diff().dropna()
        for y, v in d[d.abs() >= SEUIL_SAUT_PP].items():
            m.append(f"saut de {v:+.1f} pp en {y}")
        if r[[2018, 2021]].isna().any():
            m.append(f"valeur manquante ({', '.join(str(y) for y in (2018, 2021) if pd.isna(r[y]))})")
        motifs[u] = " ; ".join(m)
    e["valide_pour_tendance"] = e.unite_nom.map(lambda u: motifs.get(u, "") == "")
    e["motif_tendance_invalide"] = e.unite_nom.map(lambda u: motifs.get(u, ""))
    e["taux_brut"] = np.where(e.indicateur == "taux_acces", e.valeur, np.nan)
    e["taux_plafonne"] = np.where(e.indicateur == "taux_acces", e.valeur.clip(upper=100), np.nan)
    e["depasse_100"] = (e.indicateur == "taux_acces") & (e.valeur > 100)
    ue = ue.merge(pd.DataFrame({"unite_electrique": list(motifs), "motif_tendance_invalide": list(motifs.values())}), on="unite_electrique", how="left")
    ue["valide_pour_tendance"] = ue.motif_tendance_invalide.fillna("") == ""
    # --- journal ---
    for r in e[e.depasse_100].itertuples():
        an.append(_a(f, r.ligne, "Value", r.valeur, f"Taux d'accès > 100 % ({r.unite_nom}, {r.annee})", "`taux_brut` conservé ; `taux_plafonne` = 100 pour l'affichage",
                     "Unité exclue des tendances (`valide_pour_tendance` = faux)"))
    for u, m in motifs.items():
        for part in [x for x in m.split(" ; ") if x.startswith("saut")]:
            y = int(re.search(r"en (\d{4})", part).group(1))
            ln = e[(e.unite_nom == u) & (e.annee == y) & (e.indicateur == "taux_acces")].ligne.iloc[0]
            an.append(_a(f, ln, "Value", f"{u} {y}", f"Saut suspect : {part}", "Valeur conservée ; unité exclue de la tendance 2018→2021 (c4 neutre)",
                         "Signalé dans l'app (message visible)"))
        if "manquante" in m:
            an.append(_a(f, "—", "Value", u, f"Taux d'accès absent ({m})", "Ligne inexistante, non imputée ; unité exclue de la tendance", "c4 neutre"))
    kp = t.loc["KPELE"]
    an.append(_a(f, int(e[(e.unite_nom == "KPELE") & (e.annee == 2021) & (e.indicateur == "taux_acces")].ligne.iloc[0]), "Value", f"KPELE {kp[2018]} → {kp[2021]}",
                 "Baisse du taux d'accès sur la période (seule unité en baisse nette)", "Conservée (signal réel possible, non exclue)", "Information pour c4 (stagnation)"))
    for r in e[(e.indicateur == "abonnes_bt") & (e.annee == 2021)].itertuples():
        an.append(_a(f, r.ligne, "Value", f"{r.unite_nom} : {r.valeur:.0f}", "Abonnés BT 2021 présents pour 3 unités seulement (2018–2020 ailleurs)",
                     "Conservé ; BT non utilisé dans l'IPT", "Aucun"))
    an.append(_a(f, "—", "préfecture", "régions du fichier", "Les 5 régions historiques (Maritime inclut Lomé) ≠ 6 régions 2022 (DAGL à part)",
                 "`region_5` / `region_6` dans dim_territoire ; bascule dans l'app", "Contrôle de cohérence seulement"))
    out = e.rename(columns={"unite_nom": "unite_electrique"})[["ligne", "unite_electrique", "type_unite", "indicateur", "annee", "valeur", "taux_brut",
                                                                "taux_plafonne", "depasse_100", "valide_pour_tendance", "motif_tendance_invalide"]]
    out = out.rename(columns={"valeur": "valeur_brute"}).reset_index(drop=True)
    return out, ue, unite_par_pref, an


# ═══════════════════════════ AGENCES ═══════════════════════════
STATUT = {"Utilise": "Utilisé", "En construction": "En construction", "Inacheve": "Inachevé", "Nsp": "Inconnu (Nsp)", "N/a": "Non applicable (N/a)"}


def prepare_agencies(ceet: pd.DataFrame, tde: pd.DataFrame, dim: pd.DataFrame):
    """Retourne (agences, anomalies). Jointure au référentiel par noms normalisés (aucune jointure spatiale)."""
    fc, ft = "file-agences-ceet-23-12-2024-11-06-42.csv", "file-agences-togolaise-des-eaux-tde-19-12-2024-17-48-23.csv"
    a = pd.concat([ceet.assign(service="CEET", fichier=fc, ligne=np.arange(len(ceet)) + 2),
                   tde.assign(service="TdE", fichier=ft, ligne=np.arange(len(tde)) + 2)], ignore_index=True)
    n_nsp_espace = int((a.etab_creation_date == "Nsp ").sum()); n_nsp_nu = int((a.etab_creation_date == "Nsp").sum())   # avant strip
    for c in a.columns:
        if a[c].dtype == object or str(a[c].dtype).startswith("str"):
            a[c] = a[c].astype(str).str.replace("\u00a0", " ").str.strip()
    an = []
    a["statut_brut"] = a.activite_statut
    a["statut"] = a.activite_statut.str.strip("{}").str.strip().map(STATUT)
    a["categorie"] = a.activite_categorie
    a["est_public"] = ~a.categorie.str.contains("Admin|Technique")
    a["ouverte_public"] = a.est_public & (a.statut == "Utilisé")
    a["ouverte_ou_inconnue_public"] = a.est_public & a.statut.isin(["Utilisé", "Inconnu (Nsp)"])       # variante de sensibilité (Nsp compté ouvert)
    # dates
    a["date_creation_brute"] = a.etab_creation_date
    num = a.etab_creation_date.str.fullmatch(r"\d{4}")
    a["date_creation"] = np.where(num, a.etab_creation_date, "").astype(object)
    a["date_creation"] = pd.to_numeric(a.date_creation, errors="coerce")
    a["date_creation_valide"] = a.date_creation.where((a.date_creation >= 1900) & (a.date_creation <= 2026))
    for r in a[a.date_creation.notna() & a.date_creation_valide.isna()].itertuples():
        an.append(_a(r.fichier, r.ligne, "etab_creation_date", r.date_creation_brute, f"Année de création aberrante ({r.etab_nom})",
                     "Valeur brute conservée ; `date_creation_valide` vide (aucune correction inventée)", "Aucun usage analytique des dates"))
    # Nsp avec espace final
    an.append(_a(f"{fc} ; {ft}", "—", "etab_creation_date", f"`Nsp ` (espace final) : {n_nsp_espace} occurrences vs `Nsp` : {n_nsp_nu}", "Deux formes d'une même modalité",
                 "Espaces rognés (`strip`) ; modalité unique `Nsp`", "Aucun"))
    an.append(_a(f"{fc} ; {ft}", "—", "activite_statut", "`{Utilise}`, `{Inacheve}`…", "Valeurs entre accolades, sans accents (export PostgreSQL)",
                 "Accolades retirées ; libellés français (Utilisé, Inachevé…)", "Aucun"))
    n_na = a[a.statut == "Non applicable (N/a)"]
    for r in n_na.itertuples():
        an.append(_a(r.fichier, r.ligne, "activite_statut", "N/a", f"Statut non applicable ({r.etab_nom}, {r.categorie})", "Traité comme NON ouverte ; distinct de `Nsp`", "Compté ni ouverte ni en construction"))
    nsp = a[a.statut == "Inconnu (Nsp)"]
    an.append(_a(f"{fc} ; {ft}", "—", "activite_statut", f"Nsp : {int((nsp.service=='CEET').sum())} CEET + {int((nsp.service=='TdE').sum())} TdE",
                 "Statut inconnu (« ne sait pas »)", "Traité comme INCONNU (≠ N/a) ; variante de sensibilité `ouverte_ou_inconnue_public`", "Testé dans la robustesse de l'IPT"))
    for r in a[~a.est_public].itertuples():
        an.append(_a(r.fichier, r.ligne, "activite_categorie", r.categorie, f"Site administratif/technique ({r.etab_nom})", "Exclu du décompte « accueil du public », compté à part", "Évite de surestimer l'offre"))
    for r in a[a.statut.isin(["En construction", "Inachevé"])].itertuples():
        an.append(_a(r.fichier, r.ligne, "activite_statut", r.statut, f"Agence non opérationnelle ({r.etab_nom})", "Conservée, non comptée comme ouverte", "Sous-estime l'offre future"))
    # coordonnées
    xy = a.geometry.str.extract(r"POINT \(([-\d\.]+) ([-\d\.]+)\)").astype(float)
    a["lon"], a["lat"] = xy[0], xy[1]
    a["coord_valides"] = a.lon.between(-0.2, 1.9) & a.lat.between(6.0, 11.2)
    # jointure référentiel
    dp = dim[dim.niveau == "prefecture"].assign(k=lambda d: d.prefecture.map(norm))
    dc = dim[dim.niveau == "commune"].assign(kp=lambda d: d.prefecture.map(norm), kc=lambda d: d.commune.map(norm))
    pid = dict(zip(dp.k, dp.territoire_id))
    cid = {(r.kp, r.kc): r.territoire_id for r in dc.itertuples()}
    for r in dc[dc.commune_fusionnee].itertuples():                    # DANYI 1+DANYI 2 : agences de Danyi 1 ou 2 rattachées au nœud fusionné
        cid[(r.kp, "DANYI 1")] = r.territoire_id
        cid[(r.kp, "DANYI 2")] = r.territoire_id
    a["prefecture_nk"] = a.prefecture_nom_bdd.map(norm)
    a["commune_nk"] = a.commune_nom_bdd.map(norm)
    a["prefecture_id"] = a.prefecture_nk.map(pid)
    a["commune_id"] = [cid.get((p, c)) for p, c in zip(a.prefecture_nk, a.commune_nk)]
    # canton (optionnel : libellés hétérogènes possibles)
    dk = dim[dim.niveau == "canton"].assign(kp=lambda d: d.prefecture.map(norm), kc=lambda d: d.commune.map(norm), kk=lambda d: d.canton.map(norm))
    kid = {(r.kp, r.kc, r.kk): r.territoire_id for r in dk.itertuples()}
    a["canton_id"] = [kid.get((p, c, norm(k))) for p, c, k in zip(a.prefecture_nk, a.commune_nk, a.canton_nom_bdd)]
    a["region_5"] = a.region_nom_bdd.map(norm).replace({"MARITIME": "MARITIME"})
    out = a.rename(columns={"etab_nom": "nom", "etab_adresse": "adresse", "etab_jour": "jours", "nom_localite": "localite", "toilette_type": "type_toilettes",
                            "prefecture_nom_bdd": "prefecture", "commune_nom_bdd": "commune", "canton_nom_bdd": "canton"})
    cols = ["fichier", "ligne", "service", "nom", "categorie", "est_public", "statut_brut", "statut", "ouverte_public", "ouverte_ou_inconnue_public",
            "region_5", "prefecture", "commune", "canton", "localite", "adresse", "jours", "date_creation_brute", "date_creation_valide", "type_toilettes",
            "lon", "lat", "coord_valides", "prefecture_id", "commune_id", "canton_id"]
    return out[cols].reset_index(drop=True), an


# ═══════════════════════════ ÉTAT CIVIL ═══════════════════════════
CODES_EC = [  # (motif regex, code, libellé court) — l'ordre compte (« transcrits » avant « supplétifs »)
    (r"délais de 45 jours non retirés", "actes_45j_non_retires", "Actes de naissance (45 j) non retirés"),
    (r"^Nombre d'enfants enregistrés dans les délais", "enfants_enreg_45j", "Enfants enregistrés dans les 45 jours"),
    (r"mort nés enregistrés dans les formations", "mort_nes_fs", "Mort-nés enregistrés en formation sanitaire"),
    (r"mort nés enregistrés hors", "mort_nes_hors_fs", "Mort-nés enregistrés hors formation sanitaire"),
    (r"scolarisés ne disposant pas", "scolarises_sans_acte", "Enfants scolarisés sans acte de naissance"),
    (r"jugements supplétifs transcrits", "jugements_transcrits", "Jugements supplétifs transcrits"),
    (r"^Nombre de jugements supplétifs", "jugements_suppletifs", "Jugements supplétifs"),
    (r"^Nombre de naissances enregistrées$", "naissances_enreg_total", "Naissances enregistrées (total)"),
    (r"naissances enregistrées dans les formation", "naissances_enreg_fs", "Naissances enregistrées en formation sanitaire"),
    (r"naissances vivantes enregistrées dans les formations", "naissances_vivantes_fs", "Naissances vivantes enregistrées en FS"),
    (r"naissances vivantes enregistrées hors", "naissances_vivantes_hors_fs", "Naissances vivantes enregistrées hors FS"),
]
SEXE = {"Tota": "Total", "Homme": "Homme", "Femme": "Femme"}


def prepare_civil_status(df: pd.DataFrame):
    """Retourne (etat_civil_long, anomalies). Séries identifiées par (code, série) : un même libellé brut porte DEUX séries (A et B)."""
    f = "observationdata-vrsicxf.csv"
    s = df.copy()
    s.columns = ["indicateur_brut", "sexe_brut", "unit", "annee", "valeur"]
    s["ligne"] = np.arange(len(s)) + 2
    s["valeur"] = s.valeur.astype(float)
    s["annee"] = s.annee.astype(int)
    lab = s.indicateur_brut.str.replace(r"\s+", " ", regex=True).str.strip()
    code = pd.Series(index=s.index, dtype=object)
    court = pd.Series(index=s.index, dtype=object)
    for pat, c, l in CODES_EC:
        m = lab.str.contains(pat, regex=True) & code.isna()
        code[m] = c; court[m] = l
    assert code.notna().all(), lab[code.isna()].unique()
    s["indicateur_code"], s["indicateur"] = code, court
    rang = s.groupby(["indicateur_brut", "sexe_brut", "annee"]).cumcount()
    s["serie"] = np.where(rang == 0, "A", "B")
    s["sexe"] = s.sexe_brut.map(SEXE)
    an = []
    # grille complète (série × sexe × année) pour rendre visibles les lacunes
    series = s[["indicateur_code", "indicateur", "serie"]].drop_duplicates()
    grid = series.merge(pd.DataFrame({"sexe": ["Total", "Homme", "Femme"]}), how="cross").merge(pd.DataFrame({"annee": range(2014, 2020)}), how="cross")
    g = grid.merge(s[["indicateur_code", "serie", "sexe", "annee", "valeur", "ligne"]], on=["indicateur_code", "serie", "sexe", "annee"], how="left")
    g["absent_du_fichier"] = g.valeur.isna()
    g = g.rename(columns={"valeur": "valeur_brute"})
    # --- règles ---
    tot = g[g.sexe == "Total"].pivot_table(index=["indicateur_code", "serie"], columns="annee", values="valeur_brute", dropna=False)
    flag = {}
    for (c, se), r in tot.iterrows():
        for y in r.index:
            v = r[y]
            if pd.isna(v):
                continue
            oth = r.drop(y).dropna(); oth = oth[oth > 0]
            if v == 0 and (r.drop(y).dropna() > 0).any():
                flag[(c, se, y)] = ("zero_suspect", None)
            elif len(oth) >= 3:
                q = v / oth.median()
                if q >= 10 or q <= 0.2:
                    flag[(c, se, y)] = ("aberrante", q)
                elif q >= 3 or q <= 1 / 3:
                    flag[(c, se, y)] = ("rupture", q)
    for y in range(2014, 2020):                                         # R2 : deux séries identiques la même année
        a_ = tot.loc[("jugements_suppletifs", "A"), y]; b_ = tot.loc[("jugements_transcrits", "A"), y]
        if pd.notna(a_) and a_ == b_:
            flag[("jugements_suppletifs", "A", y)] = ("doublon_inter_series", None)
            flag[("jugements_transcrits", "A", y)] = ("doublon_inter_series", None)
    g["anomalie"] = [flag.get((c, se, y), (None,))[0] for c, se, y in zip(g.indicateur_code, g.serie, g.annee)]
    g["ratio_mediane_autres_annees"] = [flag.get((c, se, y), (None, None))[1] for c, se, y in zip(g.indicateur_code, g.serie, g.annee)]
    # R4 : rapport H/F improbable (en dehors de [0,5 ; 2])
    hf = g.pivot_table(index=["indicateur_code", "serie", "annee"], columns="sexe", values="valeur_brute", dropna=False)
    hf["r"] = hf.Homme / hf.Femme
    impro = set(hf[(hf.r > 2.0) | (hf.r < 0.5)].index)
    g["hf_improbable"] = [(c, se, y) in impro and sx != "Total" for c, se, y, sx in zip(g.indicateur_code, g.serie, g.annee, g.sexe)]
    g["hors_analyse_serie_b"] = g.serie == "B"
    excl = g.anomalie.isin(["aberrante", "zero_suspect", "doublon_inter_series"])
    g["valide_pour_tendance"] = ~(excl | g.hors_analyse_serie_b | g.absent_du_fichier | g.hf_improbable)
    g["valeur_affichee"] = g.valeur_brute.where(~g.absent_du_fichier)
    g["rang_serie"] = g.serie
    # --- journal ---
    lib = dict(zip(series.indicateur_code, series.indicateur))
    for (c, se, y), (typ, q) in flag.items():
        r = g[(g.indicateur_code == c) & (g.serie == se) & (g.annee == y) & (g.sexe == "Total")].iloc[0]
        qs = f"{q:,.2f}" if q is not None else ""
        txt = {"aberrante": f"Valeur aberrante (×{qs} la médiane des autres années)", "rupture": f"Rupture de série (×{qs} la médiane des autres années)",
               "zero_suspect": "Total nul alors que des valeurs existent par ailleurs", "doublon_inter_series": "Valeur identique à une autre série la même année (suspect)"}[typ]
        trait = ("Conservée ; exclue des tendances (`valide_pour_tendance` = faux), affichée en évidence" if typ != "rupture"
                 else "Conservée et utilisée avec avertissement (rupture à interpréter avec prudence)")
        an.append(_a(f, int(r.ligne) if pd.notna(r.ligne) else "—", "Value", f"{lib[c]} {y} (série {se}) = {r.valeur_brute:,.0f}".replace(",", "\u202f"), txt, trait,
                     "Série restreinte aux années cohérentes" if typ != "rupture" else "Lecture prudente"))
    for (c, se, y) in sorted(impro):
        if True:
            h = g[(g.indicateur_code == c) & (g.serie == se) & (g.annee == y)]
            vh, vf_ = h[h.sexe == "Homme"].valeur_brute.iloc[0], h[h.sexe == "Femme"].valeur_brute.iloc[0]
            an.append(_a(f, int(h[h.sexe == "Homme"].ligne.iloc[0]), "Value", f"{lib[c]} {y} (série {se}) : H {vh:,.0f} / F {vf_:,.0f}".replace(",", "\u202f"),
                         f"Rapport H/F improbable ({vh / vf_:.1f})", "Détail par sexe exclu des tendances ; total conservé", "Pas d'analyse par sexe sur ce point"))
    b = s[s.serie == "B"]
    an.append(_a(f, f"{b.ligne.min()}–{b.ligne.max()}", "indicateur", "« Nombre d'enfants scolarisés ne disposant pas d'acte de naissance »",
                 "Un même libellé porte DEUX séries : A (313 346 à 411 310) et B (0 à 3 219) ; sens de B non documenté",
                 "Séries séparées (A / B) ; B conservée mais HORS analyse", "Une moyenne naïve fusionnerait A et B"))
    miss = g[g.absent_du_fichier & g.sexe.isin(["Homme", "Femme"]) & ~g.hors_analyse_serie_b]
    an.append(_a(f, "—", "sexe", f"{miss.groupby(['indicateur_code','annee']).ngroups} séries×années sans détail H/F (surtout 2014 et 2017)",
                 "Détail par sexe absent du fichier", "Lignes créées vides (`absent_du_fichier`), non imputées", "Analyse par sexe partielle"))
    an.append(_a(f, "—", "sexe", "Tota", "Faute de frappe (Total)", "Recodé « Total »", "Aucun"))
    an.append(_a(f, "—", "territoire", "aucune colonne territoriale", "Données NATIONALES uniquement ; aucun dénominateur de naissances attendues",
                 "Jamais territorialisées ; pas de taux d'enregistrement", "Hors IPT"))
    cols = ["indicateur_code", "indicateur", "serie", "sexe", "annee", "valeur_brute", "absent_du_fichier", "anomalie", "ratio_mediane_autres_annees",
            "hf_improbable", "hors_analyse_serie_b", "valide_pour_tendance", "ligne"]
    return g[cols].sort_values(["indicateur_code", "serie", "sexe", "annee"]).reset_index(drop=True), an


# ═══════════════════════════ IDENTITÉ ═══════════════════════════
TYPES_ID = {"Cartes Nationales d\u2019identité": "cni", "Passeports": "passeports", "Cartes professionnelles": "cartes_pro", "TOTAL": "total"}


def prepare_identity(df: pd.DataFrame):
    """Retourne (identite_long, anomalies). Flux de PRODUCTION (pas une couverture) ; 2021 manquant affiché explicitement."""
    f = "observationdata-fsemhj.csv"
    i = df.copy()
    i.columns = ["indicateur", "type_brut", "unit", "annee", "valeur"]
    i["ligne"] = np.arange(len(i)) + 2
    i["valeur"] = i.valeur.astype(float)
    i["annee"] = i.annee.astype(int)
    i["type"] = i.type_brut.map(TYPES_ID)
    assert i.type.notna().all()
    grid = pd.DataFrame([(t, y) for t in TYPES_ID.values() for y in range(2014, 2023)], columns=["type", "annee"])
    g = grid.merge(i[["type", "annee", "valeur", "ligne"]], on=["type", "annee"], how="left").rename(columns={"valeur": "valeur_brute"})
    g["lacune_source"] = g.valeur_brute.isna()
    w = g.pivot(index="annee", columns="type", values="valeur_brute")
    comp = w[["cni", "passeports", "cartes_pro"]]
    recalc = comp.sum(axis=1, min_count=3)
    g["total_recalcule"] = g.annee.map(recalc).where(g.type == "total")
    g["ecart_total_vs_composantes"] = (g.valeur_brute - g.total_recalcule).where(g.type == "total")
    g["libelle"] = g.type.map({"cni": "Cartes nationales d'identité", "passeports": "Passeports", "cartes_pro": "Cartes professionnelles", "total": "Total"})
    an = [
        _a(f, "—", "Value", "2021 : CNI, cartes professionnelles et TOTAL absents (passeports 2021 = 66 938 présents)", "Lacune de la source",
           "Lignes créées vides (`lacune_source`), non imputées, lacune affichée dans l'app ; TOTAL 2021 non recalculé", "Rupture visible dans les séries"),
        _a(f, "—", "type", "Cartes Nationales d’identité (apostrophe typographique)", "Libellé avec apostrophe typographique", "Recodé en `cni`", "Aucun"),
        _a(f, "—", "Value", "Flux de production annuels", "Pas un taux de couverture ; pas de dimension territoriale",
           "« Production pour 1 000 hab. » seulement en 2022 (RGPH 2022)", "Hors IPT"),
    ]
    return g[["type", "libelle", "annee", "valeur_brute", "lacune_source", "total_recalcule", "ecart_total_vs_composantes", "ligne"]].reset_index(drop=True), an
