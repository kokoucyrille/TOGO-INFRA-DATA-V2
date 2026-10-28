"""Page « Méthode & données » — sources, périodes, niveaux, indicateurs, formules, comparabilité, qualité, limites, glossaire."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from components import charts, insights, tables
from components.kpi_cards import create_kpi_row
from components.sidebar import create_sidebar
from components.ui import flush_panel_css, page_title, panel
from data import loader as D, query as Q
from utils.formats import fmt_dec, fmt_int, fmt_pct, fmt_pp
from utils.io import load_data
from utils.quality import audit_data
from utils.territoire import norm

f = create_sidebar("methode")
T = D.load_tables()
page_title("fa-book-open", "Méthode & données", "Sources, définitions, limites.")


@st.cache_data(show_spinner=False)
def inventaire() -> pd.DataFrame:
    return audit_data(load_data())


INV = inventaire().set_index("fichier")
DIM, FP, CW, META = T["dim"], T["prefecture"], T["crosswalk"], T["meta"]
tests, anom = T["quality"], T["anomalies"]
pref_cw = CW[CW.niveau_comparaison == "préfecture"]
n_hm = int(pref_cw.comparability_flag.isin(["HIGH", "MEDIUM"]).sum())
create_kpi_row([
    {"title": "Fichiers sources", "value": fmt_int(len(INV)), "icon": "fa-table", "variant": "blue"},
    {"title": "Contrôles qualité (PASS · WARNING · FAIL)", "value": " · ".join(str(int((tests.statut == s).sum())) for s in ("PASS", "WARNING", "FAIL")), "icon": "fa-scale-balanced", "variant": "green"},
    {"title": "Anomalies consignées", "value": fmt_int(len(anom)), "icon": "fa-triangle-exclamation", "variant": "yellow"},
    {"title": "Préfectures comparables 2010–2022", "value": f"{n_hm} sur {len(pref_cw)}", "icon": "fa-chart-line", "variant": "purple"},
    {"title": "Unités de l'indice de priorité", "value": "33", "icon": "fa-bullseye", "variant": "teal"},
])
insights.story_grid([
    ("retenir", "Toutes les valeurs affichées proviennent des fichiers fournis (recensements 2010 et 2022, électricité, agences CEET et TdE, état civil, documents d'identité). <b>Aucune donnée n'est inventée</b> : une valeur absente est notée <b>N/D</b>, jamais remplacée par zéro."),
    ("attention", "Les anomalies de la source (taux supérieurs à 100 %, années aberrantes, séries dupliquées…) sont <b>conservées</b>, signalées et exclues des tendances, jamais corrigées en silence."),
    ("implication", "Chaque chiffre porte une étiquette de nature : <b>OBSERVATION</b> (valeur du fichier), <b>CALCUL</b> (dérivé par formule), <b>PROXY</b> (ordre de grandeur), <b>ESTIMATION</b>, <b>HYPOTHÈSE</b> (choix de travail)."),
])

c1, c2 = st.columns([3.2, 1.0], gap="small")
with c1:
    with st.container(key="ctl_vue"):
        a, b = st.columns([0.14, 1.0], gap="small", vertical_alignment="center")
        a.markdown('<span class="ctl-label">Section</span>', unsafe_allow_html=True)
        sec = b.segmented_control("Section", ["Sources & niveaux", "Indicateurs & formules", "Comparabilité 2010–2022", "Réconciliation du taux", "Qualité & limites", "Glossaire"], default="Sources & niveaux", key="me_sec", label_visibility="collapsed") or "Sources & niveaux"
export_df = pd.DataFrame()

# ═══════════ Sources & niveaux ═══════════
if sec == "Sources & niveaux":
    SRC = [
        ("pop2022", "Population 2022 (RGPH-5)", "2022", "Région, préfecture, commune, canton / quartier", "Liste plate sans colonne de niveau : la hiérarchie est reconstruite par l'ordre des lignes et validée par somme (parent = somme des enfants)."),
        ("pop2010", "Population 2010 (RGPH-4)", "2010", "Région, préfecture, canton (Lomé : arrondissement, quartier)", "Découpage 2010 : 36 préfectures + Lomé ; communes absentes."),
        ("elec", "Électricité : taux d'accès et abonnés BT", "2018–2021", "33 unités (27 préfectures + 6 groupes), 5 régions, national", "Taux publiés ; dénominateur implicite reconstitué (abonnés ÷ taux), nature non documentée ; une valeur dépasse 100 %."),
        ("ceet", "Agences CEET (électricité)", "extrait du 23/12/2024", "Point (coordonnées), commune, préfecture", "Statuts : Utilisé, en construction, inachevé, inconnu (Nsp), non applicable."),
        ("tde", "Agences TdE (eau)", "extrait du 19/12/2024", "Point (coordonnées), commune, préfecture", "Même structure que CEET."),
        ("etat_civil", "État civil (naissances, jugements…)", "2014–2019", "National uniquement", "11 libellés, dont un porte deux séries (A et B) ; années aberrantes en 2015."),
        ("identite", "Documents d'identité (CNI, passeports, cartes pro)", "2014–2022", "National uniquement", "2021 absent pour la CNI, les cartes professionnelles et le total."),
    ]
    with panel("src", "Sources, périodes et niveaux géographiques", "fa-table", height=None):
        t = pd.DataFrame([dict(Source=s[1], Fichier=s[0], Période=s[2], Niveau=s[3], Lignes=int(INV.loc[s[0], "lignes"]), Colonnes=int(INV.loc[s[0], "colonnes"]), Remarque=s[4]) for s in SRC])
        st.markdown('<div class="list-scroll" style="max-height:420px">' + tables.create_table(t.drop(columns="Fichier"), formats={"Lignes": fmt_int, "Colonnes": fmt_int}, num_cols=("Lignes", "Colonnes")) + "</div>", unsafe_allow_html=True)
        insights.nd_note("Versions 2026 des fichiers d'agences : identiques aux extraits de 2024 (seul l'identifiant interne diffère) ; les extraits 2024 sont utilisés. Les métadonnées décrivent 204 champs, dont seule une partie figure dans les extraits.")
        export_df = t
    with panel("niv", "Niveaux territoriaux de référence (2022)", "fa-layer-group", height=None):
        niv = pd.DataFrame([
            ("Régions", "6 (Grand Lomé à part) · 5 historiques (Maritime incluant le Grand Lomé)", "Les fichiers d'électricité et d'agences utilisent les 5 régions historiques."),
            ("Préfectures", fmt_int((DIM.niveau == "prefecture").sum()), "39 en 2022 contre 36 + Lomé en 2010 (Kpendjal, Oti scindées ; Agoè-Nyivé créée)."),
            ("Communes", f"{int((DIM.niveau == 'commune').sum())} lignes = {int((DIM.niveau == 'commune').sum()) + int(DIM.commune_fusionnee.sum())} communes", "La ligne « Danyi 1 + Danyi 2 » regroupe deux communes non séparables."),
            ("Cantons", fmt_int(((DIM.niveau == "canton") & (DIM.niveau_feuille == "canton")).sum()), "Hors Grand Lomé."),
            ("Quartiers", fmt_int(((DIM.niveau == "canton") & (DIM.niveau_feuille == "quartier")).sum()), "Feuilles du Grand Lomé, traitées à part des cantons."),
            ("Unités électriques", "33", "27 préfectures isolées + 6 groupes ; les préfectures d'un groupe héritent du taux du groupe."),
        ], columns=["Niveau", "Effectif", "Précision"])
        st.markdown(tables.create_table(niv), unsafe_allow_html=True)
    with panel("carte", "Cartes : contours et positions", "fa-map", height=None):
        insights.nd_note(f"Les contours des préfectures et des régions sont des <b>contours indicatifs</b> fournis avec le gabarit du tableau de bord (reconstitués, non officiels) : ils situent les territoires, ils ne mesurent pas de surfaces. "
                         f"Les positions des cantons sont <b>approximatives</b> : {META['geo']['cantons_positionnes']} cantons sur {META['geo']['cantons_2022']} ({fmt_pct(META['geo']['part_population_pct'], 0)} de la population des cantons) sont positionnés ; "
                         "les quartiers du Grand Lomé ne le sont pas. Position d'une commune = barycentre de ses cantons positionnés. Le fond de carte nécessite une connexion internet.")

# ═══════════ Indicateurs & formules ═══════════
elif sec == "Indicateurs & formules":
    IND = [
        ("Population 2022 ; poids relatif", "Valeur du recensement ; poids = population du territoire ÷ population nationale (8 095 498)", "OBSERVATION · CALCUL", "Démographie"),
        ("Taille des communes et des cantons", "Médiane, moyenne, écart-type, Top 10 ; cantons « petits » : moins de 5 000 habitants (seuil de travail)", "CALCUL · HYPOTHÈSE", "Démographie"),
        ("Concentration (Lorenz, Gini)", "Gini = 0 si tous les territoires ont la même taille, proche de 1 si un seul concentre presque tout", "CALCUL", "Démographie"),
        ("Variation, TCAM, contribution", "Variation relative = pop. 2022 ÷ pop. 2010 − 1 ; TCAM = (pop. 2022 ÷ pop. 2010)^(1/12) − 1 ; contribution = variation du territoire ÷ accroissement national", "CALCUL", "Évolution"),
        ("Taux d'accès à l'électricité", "Taux publié par unité ; plafonné à 100 % pour l'affichage (valeur brute conservée)", "OBSERVATION", "Services de base"),
        ("Population sans accès", "Population 2022 × (1 − taux d'accès) ; ordre de grandeur : le dénominateur du taux (≈ 12,8 % de la population) n'est pas la population", "PROXY", "Services de base"),
        ("Agences ouvertes", "Agences accueillant le public (catégorie publique) au statut « Utilisé » ; sites administratifs ou techniques exclus ; statut inconnu ≠ ouvert", "CALCUL", "Services de base"),
        ("Agences pour 100 000 hab. ; habitants par agence", "Agences ouvertes ÷ population × 100 000 ; population ÷ agences ouvertes (N/D si aucune agence)", "CALCUL", "Services de base"),
        ("Profils d'unités", "Seuils = médianes des 33 unités (population, taux d'accès, agences / 100 000 hab.)", "CALCUL · HYPOTHÈSE", "Services de base"),
        ("Variation annuelle (état civil, identité)", "Calculée seulement entre deux années consécutives toutes deux valides", "CALCUL", "État civil & identité"),
        ("Indice de priorité territoriale (IPT)", "Moyenne pondérée de 6 composantes normalisées 0–100 (voir la page Priorités)", "CALCUL · HYPOTHÈSE", "Priorités"),
        ("Stabilité du classement", "Part des configurations (scénarios, poids aléatoires, variantes) où l'unité est dans le Top 10 ; robuste si ≥ 80 %", "CALCUL", "Priorités"),
    ]
    with panel("ind", "Indicateurs, formules et nature de la donnée", "fa-sliders", height=None):
        t = pd.DataFrame(IND, columns=["Indicateur", "Définition / formule", "Nature", "Page"])
        st.markdown('<div class="list-scroll" style="max-height:520px">' + tables.create_table(t) + "</div>", unsafe_allow_html=True)
        export_df = t
    with panel("ipt", "Indice de priorité : composantes et pondérations", "fa-bullseye", height=None):
        comp = T["comp"].rename(columns={"libelle": "Composante", "formule": "Formule", "sens": "Sens", "etiquette": "Nature"})[["Composante", "Formule", "Sens", "Nature"]]
        st.markdown('<div class="list-scroll" style="max-height:300px">' + tables.create_table(comp) + "</div>", unsafe_allow_html=True)
        sc = T["scen"].copy()
        sc.columns = [("Scénario" if c == "scenario" else ({"c1_deficit_acces": "Déficit d'accès", "c2_pop_sans_acces": "Population sans accès", "c3_croissance": "Croissance", "c4_stagnation_acces": "Stagnation de l'accès",
                                                            "c5_deficit_equipement": "Déficit d'équipement", "c6_absence_service": "Absence de service"}.get(c, "Total"))) for c in sc.columns]
        st.markdown('<div class="tbl-note"><b>Pondérations (%) des quatre scénarios</b> — HYPOTHÈSE de travail, aucune pondération officielle n\'étant fournie</div>', unsafe_allow_html=True)
        st.markdown(tables.create_table(sc, num_cols=tuple(c for c in sc.columns if c != "Scénario"), formats={c: fmt_int for c in sc.columns if c != "Scénario"}), unsafe_allow_html=True)
        insights.nd_note(f"Robustesse : {META['n_configurations']} configurations (4 scénarios, {META['n_configurations'] - 6} tirages Dirichlet de graine 42, variante statut inconnu, normalisation par rang). Corrélations entre composantes : {META['correlation_verdict']}")

# ═══════════ Comparabilité 2010–2022 ═══════════
elif sec == "Comparabilité 2010–2022":
    with panel("cmp", "Crosswalk 2010 → 2022 : correspondance des territoires", "fa-scale-balanced", height=None):
        insights.nd_note("Entre 2010 et 2022, Kpendjal et Oti ont chacune été scindées en deux préfectures, et le Grand Lomé a été recomposé (Lomé commune + Golfe 2010 → Golfe + Agoè-Nyivé). "
                         "On ne compare <b>jamais</b> deux territoires sur leur seul nom : on construit des unités de comparaison, reconstituées par cantons lorsque c'est possible. "
                         "<b>HIGH</b> : au moins 90 % de la population 2010 couverte par des cantons retrouvés à l'identique ; <b>MEDIUM</b> : libellés hétérogènes ou petit transfert de canton ; <b>LOW</b> : pas d'équivalent exact (jamais classé).")
        t = CW[["id_comparaison", "territoire_2022", "niveau_comparaison", "type_correspondance", "comparability_flag", "niveau_incertitude", "couverture_cantons_pct", "pop_2010", "pop_2022", "tcam_pct", "motif"]].rename(columns={
            "id_comparaison": "Id", "territoire_2022": "Territoire 2022", "niveau_comparaison": "Niveau", "type_correspondance": "Correspondance", "comparability_flag": "Fiabilité", "niveau_incertitude": "Incertitude",
            "couverture_cantons_pct": "Cantons retrouvés (%)", "pop_2010": "Pop. 2010", "pop_2022": "Pop. 2022", "tcam_pct": "TCAM (%/an)", "motif": "Motif"})
        t["Fiabilité"] = t["Fiabilité"].map(insights.flag_badge)
        st.markdown('<div class="list-scroll" style="max-height:480px">' + tables.create_table(t, formats={"Cantons retrouvés (%)": lambda v: fmt_pct(v, 0), "Pop. 2010": fmt_int, "Pop. 2022": fmt_int, "TCAM (%/an)": lambda v: fmt_pct(v, 2)},
                                                                                                    raw_cols=("Fiabilité",), num_cols=("Cantons retrouvés (%)", "Pop. 2010", "Pop. 2022", "TCAM (%/an)")) + "</div>", unsafe_allow_html=True)
        insights.nd_note("N/D : non calculable (territoire non comparable). Sensibilité : Zio et Grand Lomé font l'objet d'une ESTIMATION indicative du transfert du canton Adéti Kopé de Zio vers Agoè-Nyivé (colonnes de la table <code>crosswalk_2010_2022</code>).")
        export_df = CW
    with panel("transf", "Transferts de cantons entre préfectures examinés", "fa-magnifying-glass", height=None):
        insights.nd_note("Une heuristique de noms repère les cantons de 2010 qui réapparaissent sous une autre préfecture en 2022. Résultat après examen : <b>un seul transfert confirmé</b> (Adéti Kopé : Zio → Agoè-Nyivé, 20 238 habitants en 2010) ; "
                         "les autres rapprochements (Kamina, Agotimé, Assahoun) sont des homonymes ou des variantes d'orthographe.")

# ═══════════ Réconciliation du taux d'accès ═══════════
elif sec == "Réconciliation du taux":
    RN, RR, RS = T["recon_nat"], T["recon_reg"], T["recon_res"]
    pub21 = float(RN[RN.scenario == "P"].taux_2021.iloc[0])
    s2 = RN[RN.scenario == "S2"].iloc[0]
    s8 = RN[RN.scenario == "S8"].iloc[0]
    s6 = RN[RN.scenario == "S6"].iloc[0]
    create_kpi_row([
        {"title": "Taux national publié 2021 (OBSERVATION)", "value": fmt_pct(pub21, 2), "icon": "fa-bolt", "variant": "green"},
        {"title": "Pondéré par la population 2022 (CALCUL)", "value": fmt_pct(s2.taux_2021, 2), "icon": "fa-users", "variant": "blue"},
        {"title": "Écart de pondération 2021", "value": fmt_pp(s2.ecart_2021, 2), "icon": "fa-scale-balanced", "variant": "red"},
        {"title": "Avec les dénominateurs de la source 2021 (ESTIMATION)", "value": fmt_pct(s8.taux_2021, 2), "icon": "fa-check", "variant": "teal"},
    ], key="kpi_recon")
    insights.story_grid([
        ("retenir", f"Le taux publié n'est <b>pas</b> une moyenne pondérée par la population : c'est Σ abonnés BT ÷ Σ (abonnés ÷ taux). Avec ces dénominateurs, on retrouve <b>{fmt_pct(s6.taux_2019, 2)}</b> en 2019 et <b>{fmt_pct(s6.taux_2020, 2)}</b> en 2020, soit exactement les valeurs publiées (écart {fmt_pp(s6.ecart_2019, 2)} et {fmt_pp(s6.ecart_2020, 2)})."),
        ("analyse", f"Ce dénominateur vaut {fmt_int(RS['2020']['total'])} en 2020, soit <b>{fmt_pct(RS['2020']['part_pop_2022_pct'], 1)}</b> de la population 2022 : sa nature (ménages ? localités électrifiables ?) n'est pas documentée. Il surpondère Lomé (≈ 25 % du dénominateur pour 16 % de la population), d'où un taux publié plus élevé."),
        ("attention", f"En 2021, aucun abonné par unité n'est publié : le <b>{fmt_pct(s8.taux_2021, 2)}</b> obtenu avec un dénominateur extrapolé est une <b>ESTIMATION</b> (écart {fmt_pp(s8.ecart_2021, 2)} au publié). Le tableau de bord affiche donc les deux valeurs : {fmt_pct(pub21, 2)} publié et {fmt_pct(s2.taux_2021, 2)} pondéré par la population, sans en masquer aucune."),
    ])
    with panel("recon_t", "Scénarios testés : taux national recalculé et écart au taux publié", "fa-scale-balanced", height=None):
        lib = {"CALCUL": "CALCUL", "ESTIMATION": "ESTIMATION", "OBSERVATION": "OBSERVATION", "N/D": "N/D"}
        t = RN.copy()
        out = pd.DataFrame({"Scénario": t.scenario, "Pondération / dénominateur testé": t.libelle, "Nature": t.nature.map(lib),
                            **{str(a): t[f"taux_{a}"] for a in (2018, 2019, 2020, 2021)}, "Écart 2021 (pp)": t.ecart_2021, "Écart 2019–2020 (pp)": t[["ecart_2019", "ecart_2020"]].abs().max(axis=1, skipna=False)})
        fm = {str(a): (lambda v: fmt_dec(v, 2)) for a in (2018, 2019, 2020, 2021)}
        fm["Écart 2021 (pp)"] = lambda v: fmt_dec(v, 2)
        fm["Écart 2019–2020 (pp)"] = lambda v: fmt_dec(v, 2)
        st.markdown('<div class="list-scroll" style="max-height:470px">' + tables.create_table(out, formats=fm, num_cols=tuple(fm)) + "</div>", unsafe_allow_html=True)
        insights.nd_note("Lecture : N/D = scénario non calculable avec les fichiers fournis (jamais remplacé par 0). Le scénario S9 (ménages) est <b>non testable</b> : aucune donnée de ménages n'est fournie. "
                         "S1 à S5 s'écartent de 2 à 22 points : ni la population 2022, ni la population 2010, ni les régions ne reproduisent le taux publié. S6 à S8 le reproduisent, parce qu'ils utilisent le dénominateur de la source.")
        export_df = RN
    with panel("recon_g", "Scénarios 2021 comparés au taux publié", "fa-chart-simple", height=330):
        g = RN[(RN.scenario != "P") & RN.taux_2021.notna()].assign(Libellé=lambda d: d.scenario + " · " + d.libelle.str.slice(0, 48))
        charts.show(charts.create_rank_bar(g, "Libellé", "taux_2021", "scenario", fmt=lambda v: fmt_dec(v, 2) + " %", height=270, ref=pub21, ref_label=f"Publié : {fmt_dec(pub21, 2)} %", xtitle="Taux d'accès national 2021 (%)"), "me_recon_bar")
    with panel("recon_r", "Taux régionaux : publié, recalculé avec les dénominateurs de la source, pondéré par la population", "fa-layer-group", height=None):
        r = RR[RR.annee == 2020].assign(Région=lambda d: d.region.str.capitalize())
        outr = pd.DataFrame({"Région": r.Région, "Publié 2020": r.publie, "Recalculé (Σ abonnés ÷ Σ dénominateurs)": r.recalcule_denominateur_source, "Écart (pp)": r.ecart_denominateur_pp,
                             "Pondéré population 2022": r.pondere_population_2022, "Écart (pp) ": r.ecart_population_pp})
        fm = {c: (lambda v: fmt_dec(v, 2)) for c in outr.columns if c != "Région"}
        st.markdown(tables.create_table(outr, formats=fm, num_cols=tuple(fm)), unsafe_allow_html=True)
        insights.nd_note("Les 5 taux régionaux publiés sont reproduits au centième près en 2019 et 2020. <b>La « Région Maritime » publiée exclut l'unité Lomé (Golfe)</b> : c'est l'origine de l'écart de +11,9 points signalé jusqu'ici. "
                         "Particularité : Centrale 2018 (24,69 % publié) ne se reproduit pas (29,59 %) car l'unité Blitta n'a pas de taux en 2018 dans le fichier ; l'écart est conservé tel quel.")
        st.markdown('<div class="note"><b>Ce qui reste inexpliqué :</b> la nature du dénominateur de la source (≈ 12,8 % de la population 2022), l\'absence d\'abonnés par unité en 2021 (le 57,82 % n\'est reproduit que par estimation), '
                    'et l\'absence de données de ménages pour tester une pondération par ménages. La population sans accès reste donc un <b>PROXY</b>.</div>', unsafe_allow_html=True)

# ═══════════ Qualité & limites ═══════════
elif sec == "Qualité & limites":
    with panel("qual", "Contrôles qualité (PASS · WARNING · FAIL)", "fa-check", height=None):
        q = tests[["n", "test", "resultat", "statut", "commentaire"]].rename(columns={"n": "N°", "test": "Test", "resultat": "Résultat", "statut": "Statut", "commentaire": "Commentaire"})
        q["Statut"] = q["Statut"].map(lambda s: insights.badge(s, {"PASS": "high", "WARNING": "medium", "FAIL": "p-tres-haute"}.get(s, "nd")))
        st.markdown('<div class="list-scroll" style="max-height:460px">' + tables.create_table(q, raw_cols=("Statut",)) + "</div>", unsafe_allow_html=True)
        insights.nd_note("WARNING = anomalie connue, traitée et documentée (pas une erreur de calcul). Aucun contrôle FAIL n'est ignoré.")
        export_df = tests
    with panel("lim", "Données manquantes et limites", "fa-triangle-exclamation", height=None):
        LIM = [
            ("Taux d'accès à l'électricité", "Nature du dénominateur non documentée (≈ 12,8 % de la population 2022) ; taux nationaux et régionaux reproduits avec les dénominateurs de la source (Réconciliation), mais pas avec la population ; valeur supérieure à 100 % pour Zio en 2021.", "La population sans accès est un PROXY."),
            ("Unités exclues des tendances", "Agoè-Nyivé, Zio, Yoto (saut ou taux > 100 %) et Blitta (2018 absent).", "Affichées, mais évolution non interprétée ; valeur neutre dans l'indice."),
            ("État civil", "Données nationales ; années 2014–2019 ; 2015 aberrante pour plusieurs indicateurs ; un libellé porte deux séries (série B hors analyse) ; détail par sexe parfois absent.", "Aucun taux d'enregistrement ni analyse territoriale."),
            ("Documents d'identité", "2021 absent pour la CNI, les cartes professionnelles et le total.", "Année laissée vide (N/D), jamais estimée."),
            ("Agences", "Agences au statut inconnu (Nsp) ou non applicable ; une année de création aberrante conservée en brut ; aucun effectif, horaire fiable ou service rendu.", "Offre mesurée en nombre d'agences, pas en capacité."),
            ("Découpage", "Communes absentes en 2010 ; Danyi 1 et 2 non séparables ; Golfe et Agoè-Nyivé non comparables séparément.", "Évolution par commune impossible."),
            ("Cartes", "Contours indicatifs ; coordonnées de cantons approximatives et partielles.", "Pas de calcul de surface ni de distance."),
            ("Deux recensements seulement", "2010 et 2022 : aucune trajectoire intermédiaire.", "La ligne 2010 → 2022 n'est pas une courbe observée."),
        ]
        t = pd.DataFrame(LIM, columns=["Domaine", "Limite", "Conséquence dans le tableau de bord"])
        st.markdown('<div class="list-scroll" style="max-height:440px">' + tables.create_table(t) + "</div>", unsafe_allow_html=True)
    with panel("anom", "Journal des anomalies (consultable)", "fa-magnifying-glass", height=None):
        q = st.text_input("Rechercher dans le journal", key="me_search", placeholder="Fichier, champ, nature, traitement…", label_visibility="collapsed")
        j = anom
        if q:
            j = anom[anom.apply(lambda r: norm(q) in norm(" ".join(map(str, r.values))), axis=1)]
        if j.empty:
            insights.empty_state()
        else:
            st.markdown('<div class="list-scroll" style="max-height:420px">' + tables.create_table(j[["fichier", "ligne", "champ", "valeur", "nature", "traitement", "impact"]].head(150).rename(columns={"fichier": "Fichier", "ligne": "Ligne", "champ": "Champ", "valeur": "Valeur", "nature": "Nature", "traitement": "Traitement", "impact": "Impact"})) + "</div>", unsafe_allow_html=True)
            insights.nd_note(f"{len(j)} entrées" + (" (150 premières affichées)" if len(j) > 150 else "") + " sur " + fmt_int(len(anom)) + ". L'export contient l'intégralité des entrées filtrées.")
            export_df = j

# ═══════════ Glossaire ═══════════
else:
    from utils.glossaire import GL
    with panel("glo", "Glossaire", "fa-book-open", height=None):
        t = pd.DataFrame(GL, columns=["Terme", "Définition"])
        st.markdown(tables.create_table(t), unsafe_allow_html=True)
        export_df = t
    with panel("repro", "Reproduire les résultats", "fa-chart-line", height=None):
        v = T["version"]
        insights.nd_note(f"Données construites le <b>{v['date_construction']}</b> à partir des fichiers bruts du dossier <code>data/raw</code> par la commande <code>python tools/build_tables.py</code> ; l'application lit uniquement <code>outputs/data</code>. "
                         "Les calculs (référentiel, démographie, crosswalk, services, indice) sont dans <code>utils/</code>, testés dans <code>tests/</code>, et le notebook <code>notebook/Defi2_Togo.ipynb</code> documente le raisonnement.")

with c2:
    if len(export_df):
        st.download_button("Exporter", Q.csv_bytes(export_df if isinstance(export_df, pd.DataFrame) else pd.DataFrame(export_df)), "methode_donnees.csv", "text/csv", key="dl_btn", help="Exporter le tableau de la section affichée (CSV)", width="stretch")
flush_panel_css()
