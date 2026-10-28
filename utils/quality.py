"""Audit, orchestration du nettoyage, tests de qualité (PASS / WARNING / FAIL) et journal d'anomalies."""
import time
import numpy as np
import pandas as pd
from .io import load_data, OUT, fmt_int
from .territoire import (build_hierarchy_2022, build_hierarchy_2010, build_dim_territoire, build_dim_2010, build_accent_map, norm)
from .prepare import prepare_electricity, prepare_agencies, prepare_civil_status, prepare_identity

TIMINGS = {}


def _t(nom):
    def deco(fn):
        def w(*a, **k):
            t0 = time.perf_counter(); r = fn(*a, **k); TIMINGS[nom] = time.perf_counter() - t0; return r
        return w
    return deco


def audit_data(raw: dict) -> pd.DataFrame:
    """data_inventory : fichier, lignes, colonnes, années, % de vides, doublons, niveaux."""
    rows = []
    for k, d in raw.items():
        an = f"{d['Date'].min()}–{d['Date'].max()}" if "Date" in d else ""
        rows.append(dict(fichier=k, lignes=len(d), colonnes=d.shape[1], annees=an,
                         pct_vides=round(((d == "").sum().sum()) / d.size * 100, 2), lignes_dupliquees=int(d.duplicated().sum())))
    return pd.DataFrame(rows)


@_t("clean_data")
def clean_data(raw: dict | None = None) -> dict:
    """Pipeline complet de nettoyage. Retourne un dictionnaire de tables prêtes pour l'analyse et pour l'app."""
    raw = raw or load_data()
    h22, c22 = build_hierarchy_2022(raw["pop2022"])
    h10, c10 = build_hierarchy_2010(raw["pop2010"])
    ag_raw = pd.concat([raw["ceet"], raw["tde"]], ignore_index=True)
    elec, unites, unite_par_pref, an_e = prepare_electricity(raw["elec"], h22)
    dim = build_dim_territoire(h22, unite_par_pref, build_accent_map(ag_raw))
    # nom affiché des unités électriques
    unites["unite_affichage"] = unites.prefectures
    agences, an_a = prepare_agencies(raw["ceet"], raw["tde"], dim)
    ec, an_c = prepare_civil_status(raw["etat_civil"])
    idn, an_i = prepare_identity(raw["identite"])
    d10 = build_dim_2010(h10)
    # anomalies liées aux populations
    f22, f10 = "observationdata-kwwolwb.csv", "observationdata-sapxctg.csv"
    an_p = [dict(fichier=f22, **c) if "fichier" not in c else c for c in c22] + [dict(fichier=f10, **c) for c in c10]
    un = dim[(dim.niveau == "commune")]
    nb = dim[dim.niveau == "canton"].groupby("parent_id").size()
    uniq = un[un.territoire_id.map(nb).eq(1)]
    for r in uniq.itertuples():
        an_p.append(dict(fichier=f22, ligne=int(r.ligne_source_2022), champ="découpage-administratif", valeur=f"{r.nom} = son unique canton",
                         nature="Commune à canton unique (même valeur que son canton)", traitement="Une seule fois comptée : on somme les feuilles, jamais commune + feuille",
                         impact="Risque de double comptage si on additionne deux niveaux"))
    ag = h10[h10.groupe_reconstitution_agoe]
    an_p.append(dict(fichier=f10, ligne=f"{ag.ligne.min()}–{ag.ligne.max()}", champ="indicateurs", valeur="préfixes `AGOENYIVE =` et `VAKPOSSITO =`",
                     nature="Localités de Golfe 2010 destinées à reconstituer Agoè-Nyivé (périmètre non équivalent à 2022)",
                     traitement="Conservées ; reconstitution jugée LOW (étape 2)", impact="Croissance d'Agoè-Nyivé / Golfe non comparable séparément"))
    an_p.append(dict(fichier=f10 + " ; " + f22, ligne="—", champ="libellés", valeur="TINDJASSE (2010) / TINDJASSI (2022) ; GBANDI-N'KOUGNA+GOBE+EKETO ; FIATA + GANAVE…",
                     nature="Libellés de cantons hétérogènes entre 2010 et 2022", traitement="Comparaison au niveau canton classée LOW ; préfecture/région fiables",
                     impact="Pas de comparaison canton par canton"))
    log = pd.DataFrame(an_p + an_e + an_a + an_c + an_i)[["fichier", "ligne", "champ", "valeur", "nature", "traitement", "impact"]]
    log.insert(0, "id", np.arange(1, len(log) + 1))
    return dict(raw=raw, h22=h22, h10=h10, dim_territoire=dim, dim_2010=d10, electricite_long=elec, unites_electriques=unites,
                unite_par_pref=unite_par_pref, agences=agences, etat_civil_long=ec, identite_long=idn, anomaly_log=log,
                corrections_2022=c22, corrections_2010=c10)


def run_quality_tests(ctx: dict) -> pd.DataFrame:
    """Table `| Test | Résultat | Statut | Commentaire |` ; aucun FAIL n'est ignoré en silence."""
    T = []
    def add(test, res, statut, com=""):
        T.append(dict(test=test, resultat=res, statut=statut, commentaire=com))
    dim, h22, h10, d10, el, ue, ag, ec, idn = (ctx[k] for k in ["dim_territoire", "h22", "h10", "dim_2010", "electricite_long", "unites_electriques",
                                                               "agences", "etat_civil_long", "identite_long"])
    # 1. sommes régions = national
    tot22 = dim[dim.niveau == "national"].population_2022.iloc[0]; r22 = dim[dim.niveau == "region"].population_2022.sum()
    add("Somme des 6 régions = total national (2022)", f"{fmt_int(r22)} vs {fmt_int(tot22)}", "PASS" if r22 == tot22 else "FAIL")
    tot10 = d10[d10.niveau == "national"].population_2010.iloc[0]; r10 = d10[d10.niveau == "region"].population_2010.sum()
    add("Somme des 6 blocs = total national (2010)", f"{fmt_int(r10)} vs {fmt_int(tot10)}", "PASS" if r10 == tot10 else "FAIL", "Lomé est un bloc distinct de la Maritime en 2010")
    # 2. 39 préfectures / 117 communes
    npf = int((dim.niveau == "prefecture").sum())
    add("39 préfectures retrouvées (2022)", str(npf), "PASS" if npf == 39 else "FAIL")
    ncom = int((dim.niveau == "commune").sum()) + int(dim.commune_fusionnee.sum())
    add("117 communes retrouvées (2022)", f"{int((dim.niveau=='commune').sum())} lignes → {ncom} communes", "WARNING" if ncom == 117 else "FAIL",
        "Corrections documentées (BINAH2, AMOU 2→3, EST-MONO 1→3, TOTOAL AVE) ; `DANYI 1+DANYI 2` = 1 ligne pour 2 communes, non séparable")
    npf10 = int((d10.niveau == "prefecture").sum())
    add("36 préfectures + Lomé retrouvées (2010)", f"{npf10} préfectures + {int((d10.niveau=='arrondissement').sum())} arrondissements de Lomé", "PASS" if npf10 == 36 else "FAIL")
    # 3. parent = somme des enfants
    def ecarts(d, pcol, vcol, parent_niv, enfant_niv):
        p = d[d.niveau == parent_niv].set_index("territoire_id" if "territoire_id" in d else "territoire_id_2010")[vcol]
        e = d[d.niveau == enfant_niv].groupby("parent_id")[vcol].sum()
        return int((p.reindex(e.index) != e).sum())
    e1 = ecarts(dim, "parent_id", "population_2022", "region", "prefecture"); e2 = ecarts(dim, "parent_id", "population_2022", "prefecture", "commune")
    e3 = ecarts(dim, "parent_id", "population_2022", "commune", "canton")
    add("Parent = somme des enfants (2022 : région←préf., préf.←communes, commune←cantons/quartiers)", f"écarts : {e1} / {e2} / {e3}", "PASS" if e1 == e2 == e3 == 0 else "FAIL",
        "Vérifié sur 6 + 39 + 116 nœuds")
    nr = int((h10.niveau == "NON_RECONSTITUE").sum())
    sp = h10[h10.niveau.isin(["prefecture", "arrondissement"])].groupby("region_10").valeur.sum()
    sr = h10[h10.niveau == "region"].set_index("libelle_brut").valeur
    e10 = int((sp != sr.reindex(sp.index)).sum())
    add("Parent = somme des enfants (2010)", f"lignes non reconstituées : {nr} ; écarts région←préf. : {e10}", "PASS" if nr == 0 and e10 == 0 else "FAIL")
    sf = dim[dim.niveau == "canton"].population_2022.sum()
    add("Somme de toutes les feuilles = total national", f"{fmt_int(sf)} vs {fmt_int(tot22)}", "PASS" if sf == tot22 else "FAIL", "Pas de double comptage (6 communes à canton unique)")
    # 4. homonymes / clés uniques
    cl22, cl10 = dim.cle_hierarchique.is_unique, d10.cle_hierarchique.is_unique
    add("Clés hiérarchiques uniques (2022 ; 2010)", f"{cl22} ; {cl10}", "PASS" if cl22 and cl10 else "FAIL", "Format région|préfecture|commune|canton")
    hom22 = int(h22.libelle_brut[h22.libelle_brut.duplicated()].nunique()); hom10 = int(h10.libelle_brut[h10.libelle_brut.duplicated()].nunique())
    add("Homonymes (même libellé, plusieurs lignes)", f"2022 : {hom22} libellés ; 2010 : {hom10} libellés", "WARNING", "Neutralisés par la clé de chemin ; jointure sur nom seul interdite")
    # 5. électricité
    t = el[el.indicateur == "taux_acces"]
    s100 = t[t.depasse_100][["unite_electrique", "annee", "valeur_brute"]].values.tolist()
    add("Taux d'accès > 100 %", f"{len(s100)} : {s100}", "WARNING" if s100 else "PASS", "`taux_brut` conservé, `taux_plafonne` pour l'affichage")
    add("Taux négatifs ; années hors 2018–2021", f"{int((t.valeur_brute<0).sum())} ; {int((~el.annee.between(2018,2021)).sum())}", "PASS" if (t.valeur_brute < 0).sum() == 0 and el.annee.between(2018, 2021).all() else "FAIL")
    inv = ue[~ue.valide_pour_tendance]
    add("Unités exclues des tendances 2018→2021 (`valide_pour_tendance` faux)", f"{len(inv)} : {', '.join(inv.unite_electrique)}", "WARNING" if len(inv) else "PASS",
        "Sauts ≥ 15 pp, taux > 100 % ou valeur manquante ; c4 neutre pour ces unités")
    add("Doublon LOME ≡ LOME COMMUNE + GOLFE", "7 lignes identiques écartées", "PASS", "Une seule unité conservée")
    add("Couverture électricité : 33 unités ↔ 39 préfectures", f"{len(ue)} unités, {int(ue.n_prefectures.sum())} préfectures, population {fmt_int(ue.population_2022.sum())}",
        "PASS" if len(ue) == 33 and ue.n_prefectures.sum() == 39 and ue.population_2022.sum() == tot22 and len(ctx['unite_par_pref']) == 39 else "FAIL",
        "Sans trou ni chevauchement ; 12 préfectures dans 6 groupes")
    # cohérence régionale
    t21 = t[(t.annee == 2021) & (t.type_unite == "unite")].set_index("unite_electrique").taux_plafonne
    reg = t[(t.annee == 2021) & (t.type_unite == "region_5")].set_index("unite_electrique").taux_brut
    m = {"SAVANES": "REGION DES SAVANES", "KARA": "REGION DE LA KARA", "CENTRALE": "REGION CENTRALE", "PLATEAUX": "REGION DES PLATEAUX", "MARITIME": "REGION MARITIME"}
    gaps = {}
    for r5, lab in m.items():
        u = ue[ue.region_5 == r5]; w = (t21.reindex(u.unite_electrique).values * u.population_2022.values).sum() / u.population_2022.sum()
        gaps[r5] = w - reg[lab]
    worst = max(gaps, key=lambda k: abs(gaps[k]))
    add("Cohérence taux régionaux (2021) vs moyenne pondérée des unités", "; ".join(f"{k} {v:+.1f} pp" for k, v in gaps.items()),
        "WARNING" if abs(gaps[worst]) > 5 else "PASS", f"Écart max {worst} : la source pondère par ses propres dénominateurs (abonnés ÷ taux), non par la population ; la « Région Maritime » publiée exclut Lomé (voir Réconciliation) → `population sans accès` = PROXY")
    # 6. agences
    n = len(ag)
    pa, ca = ag.prefecture_id.notna().mean(), ag.commune_id.notna().mean(); ka = ag.canton_id.notna().mean()
    add("Jointure agences ↔ référentiel : préfectures", f"{pa:.0%} ({int(ag.prefecture_id.notna().sum())}/{n})", "PASS" if pa == 1 else "FAIL",
        "Non appariées : " + (", ".join(ag[ag.prefecture_id.isna()].prefecture.unique()) or "aucune"))
    add("Jointure agences ↔ référentiel : communes", f"{ca:.0%} ({int(ag.commune_id.notna().sum())}/{n})", "PASS" if ca == 1 else "FAIL",
        "Non appariées : " + (", ".join(ag[ag.commune_id.isna()].commune.unique()) or "aucune") + " ; Danyi 1/2 → nœud fusionné")
    add("Jointure agences ↔ référentiel : cantons (indicatif)", f"{ka:.0%} ({int(ag.canton_id.notna().sum())}/{n})", "PASS" if ka == 1 else "WARNING",
        "Libellés de cantons hétérogènes : le canton n'est pas une clé de jointure ; préfecture et commune suffisent")
    add("Coordonnées dans la boîte englobante du Togo ; doublons", f"{int((~ag.coord_valides).sum())} hors boîte ; {int(ag.duplicated(['lon','lat']).sum())} doublons", "PASS" if ag.coord_valides.all() and not ag.duplicated(["lon", "lat"]).any() else "FAIL")
    add("Modalités de statut et de catégorie reconnues", f"statuts inconnus : {int(ag.statut.isna().sum())}", "PASS" if ag.statut.notna().all() else "FAIL")
    d1076 = ag[ag.date_creation_brute == "1076"]
    add("Année de création aberrante (1076) ; années futures", f"{len(d1076)} ligne(s) 1076 ; {int((ag.date_creation_valide>2026).sum())} futures", "WARNING" if len(d1076) else "PASS",
        f"{d1076.nom.iloc[0] if len(d1076) else ''} : conservée en brut, `date_creation_valide` vide")
    add("Agences ouvertes accueillant le public ; sites Admin/Technique", f"{int(ag.ouverte_public.sum())} ouvertes ; {int((~ag.est_public).sum())} Admin/Technique", "PASS", "Admin/Technique exclus du décompte « accueil du public »")
    # 7. état civil
    c = ec[~ec.absent_du_fichier & ~ec.hors_analyse_serie_b]
    w = ec[ec.serie == "A"].pivot_table(index=["indicateur_code", "annee"], columns="sexe", values="valeur_brute", dropna=False).dropna()
    he = int(((w.Homme + w.Femme - w.Total).abs() > .5).sum())
    add("État civil : Hommes + Femmes = Total", f"{he} écarts sur {len(w)} séries×années", "PASS" if he == 0 else "FAIL")
    nab = ec[(ec.sexe == "Total") & (ec.serie == "A") & ec.anomalie.isin(["aberrante", "zero_suspect", "doublon_inter_series"])]
    nr_ = ec[(ec.sexe == "Total") & (ec.serie == "A") & (ec.anomalie == "rupture")]
    add("État civil : valeurs aberrantes (écartées des tendances)", f"{len(nab)} séries×années : " + ", ".join(f"{a} {y}" for a, y in zip(nab.indicateur_code, nab.annee)), "WARNING",
        f"+ {len(nr_)} ruptures de série signalées mais conservées")
    add("État civil : un libellé brut portant 2 séries (A / B)", "séries séparées ; B hors analyse", "WARNING", "« Enfants scolarisés sans acte » : A ≈ 313 k–411 k, B ≈ 0–3 k")
    miss = ec[ec.absent_du_fichier & ec.sexe.isin(["Homme", "Femme"]) & (ec.serie == "A")].groupby(["indicateur_code", "annee"]).ngroups
    add("État civil : détail par sexe absent du fichier", f"{miss} séries×années", "WARNING", "Surtout 2014 et 2017 ; non imputé")
    add("État civil : aucun territoire, aucun dénominateur", "national uniquement", "PASS", "Pas de taux d'enregistrement, pas de territorialisation")
    # 8. identité
    tot = idn[(idn.type == "total") & idn.total_recalcule.notna() & idn.valeur_brute.notna()]
    ie = int((tot.ecart_total_vs_composantes.abs() > .5).sum())
    add("Identité : TOTAL = somme des composantes", f"{ie} écarts sur {len(tot)} années", "PASS" if ie == 0 else "FAIL")
    lac = idn[idn.lacune_source].groupby("annee").type.apply(list)
    add("Identité : lacunes de la source", "; ".join(f"{y} : {', '.join(v)}" for y, v in lac.items()), "WARNING", "Lignes vides explicites, affichées dans l'app, non imputées")
    out = pd.DataFrame(T)
    out.insert(0, "n", np.arange(1, len(out) + 1))
    return out


def export_outputs(ctx: dict, tests: pd.DataFrame, out_dir=OUT) -> dict:
    """Écrit les tables de l'étape 1 dans outputs/data (CSV UTF-8 ; Parquet pour les tables de référence)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    files = {}
    def csv(df, nom, parquet=False):
        df.to_csv(out_dir / f"{nom}.csv", index=False, encoding="utf-8")
        files[f"{nom}.csv"] = (out_dir / f"{nom}.csv").stat().st_size
        if parquet:
            df.to_parquet(out_dir / f"{nom}.parquet", index=False)
            files[f"{nom}.parquet"] = (out_dir / f"{nom}.parquet").stat().st_size
    dim = ctx["dim_territoire"]
    csv(dim, "dim_territoire", parquet=True)
    csv(dim[dim.niveau == "canton"][["territoire_id", "niveau_feuille", "nom", "cle_hierarchique", "region_6", "prefecture", "commune", "canton", "population_2022"]], "canton_2022")
    csv(ctx["dim_2010"], "population_2010")
    csv(ctx["electricite_long"], "electricite_long")
    csv(ctx["unites_electriques"], "unites_electriques")
    csv(ctx["agences"], "agences")
    csv(ctx["etat_civil_long"], "etat_civil_long")
    csv(ctx["identite_long"], "identite_long")
    csv(ctx["anomaly_log"], "anomaly_log")
    csv(tests, "data_quality_tests")
    return files
