"""Page « Priorités & recommandations » — objectif 5 : où faut-il agir, et pourquoi ? (Indice de Priorité Territoriale, robustesse, recommandations)."""
from __future__ import annotations

import html
import math

import numpy as np
import pandas as pd
import streamlit as st

from components import charts, gstate, insights, maps, tables
from components.kpi_cards import create_kpi_row
from components.recommendation_cards import create_priority_card
from components.sidebar import create_sidebar
from components.ui import flush_panel_css, page_title, panel
from data import loader as D, query as Q
from utils import story
from utils.formats import fmt_dec, fmt_int, fmt_pct, fmt_pp, liste_fr
from utils.priority import CODES, COMPOSANTES, SCENARIO_DEFAUT, SCENARIOS, SEUIL_ROBUSTE, compute_ipt

f = create_sidebar("priorites")
T = D.load_tables()
FU, FP, ROB, RECO, META = T["unite"], T["prefecture"], T["rob"], T["reco"], T["meta"]
page_title("fa-bullseye", "Priorités & recommandations", "Où agir en priorité ?")
CLASS_COL = {"Très haute": "#f20e36", "Haute": "#f58a1f", "Moyenne": "#fec902", "Faible": "#35a37a"}
CLASSES = list(CLASS_COL)

# ---- scénario de pondération (simulateur) --------------------------------------------------------------------------------
c0, c1, c2 = st.columns([2.6, 0.85, 1.35], gap="small")
with c0:
    with st.container(key="ctl_vue"):
        a, b = st.columns([0.2, 1.0], gap="small", vertical_alignment="center")
        a.markdown('<span class="ctl-label">Scénario</span>', unsafe_allow_html=True)
        scen = b.segmented_control("Scénario de pondération", list(SCENARIOS) + ["Personnalisé"], default=SCENARIO_DEFAUT, key="pr_scen", label_visibility="collapsed") or SCENARIO_DEFAUT
with c1:
    with st.container(key="ctl_top"):
        a, b = st.columns([0.35, 1.0], gap="small", vertical_alignment="center")
        a.markdown('<span class="ctl-label">Top</span>', unsafe_allow_html=True)
        top_n = b.segmented_control("Top N", [5, 10, 15, 20], default=10, key="pr_topn", label_visibility="collapsed") or 10
with c2:
    with st.container(key="ctl_view"):
        a, b, c = st.columns([0.45, 1.2, 0.3], gap="small", vertical_alignment="center")
        a.markdown('<span class="ctl-label">Afficher</span>', unsafe_allow_html=True)
        mode = b.segmented_control("Afficher", ["Carte", "Graphique", "Tableau"], default="Carte", key="pr_mode", label_visibility="collapsed") or "Carte"

# Les curseurs affichent TOUJOURS les pondérations du scénario actif (A, B, C ou D) ; ils ne sont modifiables qu'en mode « Personnalisé »,
# où ils repartent des valeurs du dernier scénario consulté (on ajuste une base connue plutôt que de repartir de zéro).
for code in CODES:
    if scen != "Personnalisé":
        st.session_state[f"pr_w_{code}"] = int(SCENARIOS[scen][code])
    elif f"pr_w_{code}" not in st.session_state:
        st.session_state[f"pr_w_{code}"] = int(SCENARIOS[SCENARIO_DEFAUT][code])
titre_pond = "Pondérations : voir et personnaliser" if scen == "Personnalisé" else f"Pondérations du scénario {scen} : voir et personnaliser"
with st.expander(titre_pond, expanded=(scen == "Personnalisé")):
    cols = st.columns(6)
    custom = {}
    for col_, code in zip(cols, CODES):
        custom[code] = col_.slider(COMPOSANTES[code][0], 0, 100, step=5, key=f"pr_w_{code}", disabled=(scen != "Personnalisé"), help=COMPOSANTES[code][1])
    if scen == "Personnalisé":
        tot = sum(custom.values())
        insights.nd_note(f"<b>Mode personnalisé</b> : déplacez les curseurs pour définir vos propres pondérations. Somme saisie : <b>{tot}</b>\u00a0" + ("→ pondérations <b>normalisées à 100 %</b> automatiquement." if tot != 100 else "(100 %).") + (" <b>Aucun poids : saisissez au moins une pondération.</b>" if tot == 0 else ""))
    else:
        insights.nd_note(f"<b>Lecture seule</b> : les curseurs affichent les pondérations du scénario <b>{scen}</b> (total 100 %). Choisissez « Personnalisé » pour les modifier à partir de ces valeurs ; "
                         "les poids des 4 scénarios sont comparés dans la section « Comment l'indice est calculé » plus bas.")
weights = custom if scen == "Personnalisé" else SCENARIOS[scen]
if sum(weights.values()) <= 0:
    insights.empty_state("Aucune pondération : le score ne peut pas être calculé.")
    flush_panel_css()
    st.stop()
wsum = sum(weights.values())

# ---- calcul de l'IPT (fonction pure et vectorisée, identique à celle du Data-Lab) ----------------------------------------------
ipt = compute_ipt(FU, weights)
ref_rank = compute_ipt(FU, SCENARIOS[SCENARIO_DEFAUT]).set_index("unite_electrique").rang_ipt
ipt["delta_rang"] = ipt.unite_electrique.map(ref_rank) - ipt.rang_ipt
ipt = ipt.drop(columns=[c for c in ("priority_stability_score", "stabilite", "rang_median", "variation_rang") if c in ipt.columns])      # évite les doublons de colonnes
ipt = ipt.merge(ROB[["unite_electrique", "priority_stability_score", "stabilite", "rang_median", "variation_rang"]], on="unite_electrique", how="left")
ipt["id"] = ipt.unite_electrique
view = ipt.copy()
if f["region"]:
    view = view[view.region_5 == f["region"]]
if f["prefecture"]:
    view = view[view.prefectures_raw.str.split(";").map(lambda L: f["prefecture"] in L)]
if f["classes"]:
    view = view[view.classe_priorite.isin(f["classes"])]
view = view.sort_values("ipt", ascending=False).reset_index(drop=True)
nom_sel = Q.titre_selection(f)
tn = float(T["meta"]["seuils_profils"]["tcam_national"])
ratio_nat = FP.agences_ouvertes_total.sum() / FP.population_2022.sum() * 1e5

# ---- KPI -------------------------------------------------------------------------------------------------------------------------
th = view[view.classe_priorite == "Très haute"]
create_kpi_row([
    {"title": f"Unités analysées · {nom_sel}", "value": f"{len(view)} sur {len(ipt)}", "icon": "fa-layer-group", "variant": "blue"},
    {"title": "Priorité « Très haute »", "value": fmt_int(len(th)) + " unités", "icon": "fa-bullseye", "variant": "red"},
    {"title": "Population de ces unités", "value": fmt_int(th.population_2022.sum()), "icon": "fa-users", "variant": "yellow"},
    {"title": "Sans accès dans ces unités (PROXY)", "value": fmt_int(th.pop_sans_acces_2021.sum()), "icon": "fa-bolt", "variant": "purple"},
    {"title": f"Unités robustes (Top 10 ≥ {int(SEUIL_ROBUSTE)} % des configurations)", "value": fmt_int(int((ROB.stabilite == "robuste").sum())) + " sur 33", "icon": "fa-scale-balanced", "variant": "teal"},
])
insights.nd_note(f"Scénario actif : <b>{scen}</b> · pondérations (en %) : " + ", ".join(f"{COMPOSANTES[c][0]} {w * 100 / wsum:.0f}" for c, w in weights.items()) +
                 ". L'indice est un <b>outil d'aide à la décision</b>, pas une vérité : les pondérations sont une <b>HYPOTHÈSE</b> de travail dont on mesure la sensibilité (section « Robustesse »).")

# ---- récit -----------------------------------------------------------------------------------------------------------------------
if view.empty:
    insights.empty_state()
    flush_panel_css()
    st.stop()
t3 = view.head(3)
rob_n = int((ROB.stabilite == "robuste").sum())
robustes_vue = view[view.stabilite == "robuste"]
insights.story_grid([
    ("retenir", f"Dans le scénario <b>{scen}</b>, les unités les plus prioritaires sont <b>{liste_fr(t3.unite_affichage, 3)}</b> (IPT de <b>{fmt_dec(t3.ipt.min(), 0)}</b> à <b>{fmt_dec(t3.ipt.max(), 0)}</b> sur 100)."),
    ("analyse", f"<b>{rob_n}</b> unités sur 33 restent dans le Top 10 dans au moins {int(SEUIL_ROBUSTE)} % des <b>{META['n_configurations']}</b> configurations testées (4 scénarios, "
                f"{META['n_configurations'] - 6} tirages de poids aléatoires, variantes). " + (f"Dans la sélection : <b>{liste_fr(robustes_vue.unite_affichage, 4)}</b>." if len(robustes_vue) else "Aucune unité robuste dans la sélection.")),
    ("attention", "Les unités dont le taux ou la croissance ne sont pas interprétables (taux supérieur à 100 %, saut brutal, périmètre non comparable) reçoivent une <b>valeur neutre</b> sur les composantes concernées : "
                  f"{int(ipt.neutre_c3.sum())} unités pour la croissance, {int(ipt.neutre_c4.sum())} pour la stagnation de l'accès."),
])

# ---- carte / graphique / tableau  |  classement ---------------------------------------------------------------------------
n_rank = min(top_n, len(view))
H_RANK, H_SIDE = 130 + 27 * n_rank, 470
c_main, c_side = st.columns([1.3, 1.0], gap="small")
sel_ids: list = []
with c_side:
    with panel("rank", f"Classement : les {n_rank} unités les plus prioritaires", "fa-ranking-star", height=H_RANK):
        top = view.head(top_n).copy()
        top["Libellé"] = top.unite_affichage
        sel_ids = charts.show_select(charts.create_rank_bar(top, "Libellé", "ipt", "id", fmt=lambda v: fmt_dec(v, 1), colors=top.classe_priorite.map(CLASS_COL).tolist(), height=40 + 27 * len(top), xtitle="Indice de priorité (0–100)"), "pr_rank")
        sel_ids = [i for i in sel_ids if i in set(ipt.id)]
        st.markdown('<div class="note">Couleur = niveau de priorité (quartiles de l\'indice : très haute = 25 % supérieurs). Cliquez une barre pour ouvrir sa fiche ci-dessous.</div>', unsafe_allow_html=True)
    with panel("comp", "Pourquoi ces unités ? Contribution des composantes", "fa-chart-simple", height=H_SIDE):
        top8 = top.head(min(8, len(top)))
        with st.container(key="cmp_chart_top"):
            st.markdown('<div class="chart-sub">Graphique · score de chaque unité décomposé par composante</div>', unsafe_allow_html=True)
            charts.show(charts.create_stacked_components(top8, "Libellé", COMPOSANTES, weights, 50 + 30 * len(top8)), "pr_stack")
        st.markdown(charts.stacked_legend(COMPOSANTES, weights), unsafe_allow_html=True)
        insights.nd_note("Lecture : la longueur de chaque segment = points apportés au score par la composante (poids × valeur normalisée) ; le nombre en bout de barre est le score total.")
H_MAIN = H_RANK + H_SIDE + 14
with c_main:
    if mode == "Carte":
        with panel("map", f"Niveaux de priorité · {scen}", "fa-map", height=H_MAIN):
            fp = FP.merge(ipt[["unite_electrique", "classe_priorite", "ipt"]], on="unite_electrique", how="left")
            fp = fp[fp.unite_electrique.isin(view.unite_electrique)]
            rows = []
            for _, r in fp.iterrows():
                for nm in D.polygons_of_prefecture().get(r.prefecture_raw, []):
                    rows.append(dict(code=nm, Territoire=r.prefecture_nom, Valeur=r.ipt, cls=CLASSES.index(r.classe_priorite), id=r.unite_electrique, tip=f"{r.prefecture_nom} · unité « {r.unite_electrique.title()} »"))
            pf = pd.DataFrame(rows)
            hl = set(pf[pf.id.isin(sel_ids)].code) if sel_ids and len(pf) else None
            _ur = FP.groupby("unite_electrique").region_6.agg(lambda x: x.iloc[0] if x.nunique() == 1 else None).to_dict()     # unité → sa région (si unique)
            gstate.handle_click("map_pr", maps.create_map("Préfecture", pf, maps.PRIORITY_LEGEND, key="map_pr", height=H_MAIN - 70, value_label="Indice de priorité", fmt=lambda v: fmt_dec(v, 1), highlight=hl),
                                lambda i: dict(region=_ur[i], prefecture=None, commune=None, canton=None) if _ur.get(i) else None)
            insights.nd_note("Chaque préfecture <b>hérite du score de son unité électrique</b> (une unité peut regrouper plusieurs préfectures). Préfectures grisées : hors sélection.")
    elif mode == "Graphique":
        with panel("graph", "Score, population sans accès et stabilité", "fa-chart-simple", height=H_MAIN):
            g = view.head(top_n)
            charts.show(charts.create_rank_bar(g.assign(Libellé=g.unite_affichage), "Libellé", "priority_stability_score", "id", fmt=lambda v: fmt_pct(v, 0), height=H_MAIN - 110, xtitle=f"Stabilité : part des configurations où l'unité est dans le Top 10 (%)",
                                               colors=["#016b4b" if s == "robuste" else "#fec902" for s in g.stabilite], selected=sel_ids, ref=SEUIL_ROBUSTE, ref_label=f"Robuste ≥ {int(SEUIL_ROBUSTE)} %"), "pr_stab")
            insights.nd_note(f"Vert = robuste (≥ {int(SEUIL_ROBUSTE)} % des configurations), jaune = sensible aux pondérations. Une unité très prioritaire mais sensible doit être confirmée avant engagement.")
    else:
        with panel("tab", "Valeurs normalisées des composantes (0–100, 100 = situation la plus défavorable)", "fa-table", height=H_MAIN):
            t = view[["unite_affichage"] + [f"{c}_norm" for c in CODES] + ["ipt"]].rename(columns={"unite_affichage": "Unité", **{f"{c}_norm": COMPOSANTES[c][0] for c in CODES}, "ipt": "IPT"})
            st.markdown(f'<div class="list-scroll" style="max-height:{H_MAIN - 80}px">' + tables.create_table(t, formats={c: (lambda v: fmt_dec(v, 0)) for c in t.columns if c != "Unité"} | {"IPT": lambda v: fmt_dec(v, 1)}, num_cols=tuple(c for c in t.columns if c != "Unité")) + "</div>", unsafe_allow_html=True)
            insights.nd_note("Normalisation : winsorisation aux percentiles 5 et 95 puis min–max. Valeur neutre = médiane des unités renseignées (cas non interprétables).")

# ---- classement complet ---------------------------------------------------------------------------------------------------------
with panel("classement", "Classement des territoires prioritaires", "fa-ranking-star", height=None):
    t = view.copy()
    t["Rang"] = t.rang_ipt
    t["Priorité"] = t.classe_priorite.map(insights.priority_badge)
    t["Stabilité"] = t.apply(lambda r: insights.badge(f"{r.stabilite} · {fmt_pct(r.priority_stability_score, 0)}", "high" if r.stabilite == "robuste" else "medium"), axis=1)
    t["Δ rang"] = t.delta_rang.map(lambda v: "—" if v == 0 else (f"↑ {int(v)}" if v > 0 else f"↓ {int(-v)}"))
    out = t[["Rang", "unite_affichage", "ipt", "population_2022", "taux_plaf_2021", "agences_par_100k_total", "Priorité", "Stabilité", "Δ rang"]].rename(columns={
        "unite_affichage": "Territoire (unité électrique)", "ipt": "Score", "population_2022": "Population", "taux_plaf_2021": "Accès 2021 (%)", "agences_par_100k_total": "Services (agences / 100 000 hab.)"})
    st.markdown('<div class="list-scroll" style="max-height:460px">' + tables.create_table(out, formats={"Rang": lambda v: str(int(v)), "Score": lambda v: fmt_dec(v, 1), "Population": fmt_int, "Accès 2021 (%)": lambda v: fmt_pct(v, 1),
                "Services (agences / 100 000 hab.)": lambda v: fmt_dec(v, 2)}, raw_cols=("Priorité", "Stabilité"), num_cols=("Rang", "Score", "Population", "Accès 2021 (%)", "Services (agences / 100 000 hab.)")) + "</div>", unsafe_allow_html=True)
    insights.nd_note(f"Δ rang = écart avec le scénario de référence ({SCENARIO_DEFAUT}). Quartiles de l'indice : très haute &gt; {fmt_dec(ipt.ipt.quantile(.75), 1)} · haute &gt; {fmt_dec(ipt.ipt.quantile(.5), 1)} · moyenne &gt; {fmt_dec(ipt.ipt.quantile(.25), 1)}.")
with c2:
    with c:
        exp = out.drop(columns=["Priorité", "Stabilité"]).assign(Priorité=view.classe_priorite.values, Stabilité=view.stabilite.values)
        st.download_button("Exporter", Q.csv_bytes(exp), "priorites_ipt.csv", "text/csv", key="dl_btn", help="Exporter le classement affiché (CSV, filtres et pondérations actifs)", width="stretch")

# ---- fiche territoire : pourquoi et que faire -------------------------------------------------------------------------------------
# La sélection d'une barre ne pilote la fiche que lorsqu'elle CHANGE : sinon elle écraserait à chaque rerun le choix fait dans la liste déroulante.
if sel_ids and sel_ids != st.session_state.get("pr_sel_prev"):
    st.session_state["pr_unit"] = sel_ids[-1]
st.session_state["pr_sel_prev"] = list(sel_ids)
ids = list(view.unite_electrique)
if st.session_state.get("pr_unit") not in ids:
    st.session_state["pr_unit"] = ids[0]
with panel("fiche", "Sélection d'un territoire : indicateurs, interprétation et recommandation", "fa-bullseye", height=None):
    choice = st.selectbox("Territoire (unité électrique)", ids, format_func=lambda u: view.set_index("unite_electrique").loc[u, "unite_affichage"], key="pr_unit", help="Choisissez une unité, ou cliquez une barre du classement.")
    u = view[view.unite_electrique == choice].iloc[0]
    k1, k2 = st.columns([1.0, 1.35], gap="medium")
    with k1:
        st.markdown(charts.create_indicator_rows([
            ("fa-users", "Population 2022", fmt_int(u.population_2022), f"{fmt_pct(u.poids_national_pct, 1)} du pays"),
            ("fa-chart-line", "Croissance 2010–2022", fmt_pct(u.tcam_pct, 2) + "/an" if u.tcam_pct == u.tcam_pct else "N/D", {"HIGH": "comparable", "MEDIUM": "prudence", "LOW": "non comparable"}.get(u.flag_croissance, "")),
            ("fa-bolt", "Taux d'accès 2021", fmt_pct(u.taux_plaf_2021, 1), f"{fmt_pp(u.ecart_national_pp_2021)} vs national"),
            ("fa-triangle-exclamation", "Population sans accès (PROXY)", fmt_int(u.pop_sans_acces_2021), f"rang {int(u.rang_pop_sans_acces)} sur 33"),
            ("fa-store", "Agences CEET · TdE ouvertes", f"{int(u.ceet_ouvertes)} · {int(u.tde_ouvertes)}", f"{fmt_dec(u.agences_par_100k_total, 2)} / 100 000 hab."),
            ("fa-circle-info", "Autres sites (admin./technique) · en projet", f"{int(u.admin_technique)} · {int(u.ceet_en_construction + u.ceet_inachevees + u.tde_en_construction + u.tde_inachevees)}", "non comptés comme ouverts"),
            ("fa-scale-balanced", "Score · rang · stabilité", f"{fmt_dec(u.ipt, 1)} · {int(u.rang_ipt)}ᵉ", f"{u.stabilite} ({fmt_pct(u.priority_stability_score, 0)})"),
        ]), unsafe_allow_html=True)
    contrib = {c: u[f"{c}_norm"] * weights[c] / wsum for c in CODES}
    principaux = sorted(contrib, key=contrib.get, reverse=True)[:3]
    PH = {
        "c1_deficit_acces": f"un taux d'accès de <b>{fmt_pct(u.taux_plaf_2021, 1)}</b> ({fmt_pp(u.ecart_national_pp_2021)} par rapport au taux national publié de {fmt_pct(D.TAUX_NATIONAL[2021], 1)})",
        "c2_pop_sans_acces": f"<b>{fmt_int(u.pop_sans_acces_2021)}</b> personnes sans accès (PROXY), au rang <b>{int(u.rang_pop_sans_acces)}</b> sur 33",
        "c3_croissance": ("une croissance démographique non comparable (valeur neutre appliquée)" if u.neutre_c3 else f"une croissance de <b>{fmt_pct(u.tcam_pct, 1)}</b> par an contre <b>{fmt_pct(tn, 2)}</b> pour le pays"),
        "c4_stagnation_acces": ("une tendance 2018→2021 non interprétable (valeur neutre appliquée)" if u.neutre_c4 else f"un taux qui n'évolue que de <b>{fmt_pp(u.delta_pp_2018_2021, 1)}</b> entre 2018 et 2021"),
        "c5_deficit_equipement": f"seulement <b>{fmt_dec(u.agences_par_100k_total, 2)}</b> agence(s) ouverte(s) pour 100 000 habitants contre <b>{fmt_dec(ratio_nat, 2)}</b> au niveau national",
        "c6_absence_service": f"en moyenne <b>{fmt_pct(u.c6_part_pop_sans_service_pct, 0)}</b> de la population vivant dans une préfecture sans agence CEET ou TdE ouverte",
    }
    manque = max(0, math.ceil(u.population_2022 * ratio_nat / 1e5) - int(u.agences_ouvertes_total))
    a_raccorder = max(0, u.population_2022 * (D.TAUX_NATIONAL[2021] - u.taux_plaf_2021) / 100)
    acces_dom = {"c1_deficit_acces", "c2_pop_sans_acces", "c4_stagnation_acces"} & set(principaux)
    serv_dom = {"c5_deficit_equipement", "c6_absence_service"} & set(principaux)
    reco = []
    if acces_dom:
        reco.append(f"un programme d'électrification de <b>{u.unite_affichage}</b> visant au moins le taux national, soit environ <b>{fmt_int(a_raccorder)}</b> personnes à raccorder" if a_raccorder > 0 else "le suivi de l'accès à l'électricité")
    if serv_dom:
        reco.append(f"l'ouverture ou le renforcement de points de service CEET / TdE ({'environ <b>' + str(manque) + '</b> agence(s) de plus pour atteindre le ratio national' if manque else 'ratio déjà proche du national : cibler les préfectures sans agence'})")
    if not reco:
        reco.append("un renforcement progressif du service, la priorité étant davantage liée à la croissance démographique")
    prio_h = {"Très haute": "court à moyen terme (1–2 ans)", "Haute": "moyen terme (2–3 ans)", "Moyenne": "moyen terme", "Faible": "suivi simple"}[u.classe_priorite]
    with k2:
        insights.story("analyse", f"<b>{u.unite_affichage}</b> est classée <b>{u.classe_priorite.lower()}</b> priorité (score <b>{fmt_dec(u.ipt, 1)}</b>, rang <b>{int(u.rang_ipt)}</b> sur {len(ipt)}) à cause de : " + " ; ".join(PH[c] for c in principaux) + ".")
        insights.story("recommandation", "Prévoir " + " et ".join(reco) + f" ; horizon : <b>{prio_h}</b>." + (f" <b>Priorité sensible aux pondérations</b> (stabilité {fmt_pct(u.priority_stability_score, 0)}) : à confirmer avant engagement." if u.stabilite == "sensible" else f" Priorité <b>robuste</b> ({fmt_pct(u.priority_stability_score, 0)} des configurations)."))
        one = pd.DataFrame([u]).assign(Libellé="Score")
        with st.container(key="cmp_chart_one"):
            st.markdown(f'<div class="chart-sub">Graphique · contribution des composantes au score de {u.unite_affichage}</div>', unsafe_allow_html=True)
            charts.show(charts.create_stacked_components(one, "Libellé", COMPOSANTES, weights, 96), "pr_one")
        st.markdown(charts.stacked_legend(COMPOSANTES, weights, values=contrib), unsafe_allow_html=True)

# ---- robustesse ------------------------------------------------------------------------------------------------------------------
with panel("robust", "Robustesse du classement", "fa-scale-balanced", height=None):
    r = ROB.merge(FU[["unite_electrique", "unite_affichage"]], on="unite_electrique").sort_values("priority_stability_score", ascending=False)
    rr = r[["unite_affichage", "priority_stability_score", "rang_median", "rang_min", "rang_max", "stabilite"]].head(15).rename(columns={
        "unite_affichage": "Unité", "priority_stability_score": "Dans le Top 10 (%)", "rang_median": "Rang médian", "rang_min": "Meilleur rang", "rang_max": "Pire rang", "stabilite": "Verdict"})
    st.markdown('<div class="list-scroll" style="max-height:380px">' + tables.create_table(rr, formats={"Dans le Top 10 (%)": lambda v: fmt_pct(v, 0), "Rang médian": lambda v: fmt_dec(v, 0), "Meilleur rang": lambda v: fmt_int(v), "Pire rang": lambda v: fmt_int(v)},
                num_cols=("Dans le Top 10 (%)", "Rang médian", "Meilleur rang", "Pire rang")) + "</div>", unsafe_allow_html=True)
    insights.nd_note(f"{META['n_configurations']} configurations : 4 scénarios, {META['n_configurations'] - 6} tirages de poids aléatoires (Dirichlet, graine 42), variante où les agences au statut inconnu comptent comme ouvertes, et normalisation par rang. "
                     f"<b>Corrélations entre composantes :</b> {META['correlation_verdict']}")

# ---- recommandations (cartes) ------------------------------------------------------------------------------------------------------
GROUPES = [
    ("Priorités IPT · robustes", "fa-bullseye", "Priorités robustes — agir sans regret (stables dans ≥ 80 % des configurations)", lambda d: d[(d.Axe == "Priorités IPT") & (d.Robustesse == "robuste")], "Priorité très haute · robuste"),
    ("Priorités IPT · sensibles", "fa-scale-balanced", "Priorités sensibles — à confirmer avant engagement (dépendent des pondérations)", lambda d: d[(d.Axe == "Priorités IPT") & (d.Robustesse != "robuste")], "Priorité très haute · sensible"),
    ("Agences", "fa-store", "Services CEET / TdE (complémentaire) : ouvrir et renforcer les points d'accueil", lambda d: d[d.Axe == "Agences"], "Complémentaire"),
    ("Démographie", "fa-users", "Petits cantons (complémentaire) : accès de proximité", lambda d: d[d.Axe == "Démographie"], "Complémentaire"),
    ("État civil", "fa-id-card", "État civil et identité : renforcer le système d'enregistrement", lambda d: d[d.Axe == "État civil"], "Nationale"),
    ("Données", "fa-book-open", "Données : documenter pour mieux cibler", lambda d: d[d.Axe == "Données"], "Nationale"),
]
syn_txt = story.phrase_synthese_priorites(story.synthese_priorites(FU))
st.markdown('<div class="note" style="margin:6px 0 4px 2px;font-size:13.5px"><b>Recommandations territorialisées</b> : elles découlent mécaniquement du classement IPT. '
            f'{syn_txt} Les lignes « complémentaire » portent sur d\'autres axes et ne revendiquent aucune classe IPT.</div>', unsafe_allow_html=True)
for i_g, (cle, icone, titre, sel_fn, badge) in enumerate(GROUPES):
    d = sel_fn(RECO)
    if d.empty:
        continue
    acts = []
    for j, (_, r) in enumerate(d.iterrows()):
        rang = f" · rang IPT {int(r['Rang IPT'])}/33" if r["Rang IPT"] == r["Rang IPT"] else ""
        acts.append((f"{cle[0]}{j + 1}" if i_g > 1 else f"#{int(r['Rang IPT'])}", f"{r.Territoire}{rang}",
                     f"{r.Problème}. {r.Recommandation} Preuve : {r.Preuve}. Horizon : {r.Horizon}. Suivi : {r['KPI de suivi']}."))
    st.markdown(create_priority_card(f'<i class="fa-solid {icone}"></i>', titre, "#003f8c", badge, acts), unsafe_allow_html=True)
st.download_button("Exporter les recommandations (CSV)", Q.csv_bytes(RECO.drop(columns=["Unité IPT"], errors="ignore")), "recommandations.csv", "text/csv", key="dl_reco")

# ---- méthode de l'indice (formule, composantes, pondérations, limites) --------------------------------------------------------------
with panel("methode_ipt", "Comment l'indice est calculé", "fa-circle-info", height=None):
    st.markdown("<div class='note' style='font-size:14px;color:#1e3a4c'><b>Formule :</b> IPT = Σ (poids × composante normalisée) ÷ Σ poids, sur 33 unités électriques ; chaque composante est ramenée à 0–100 "
                "(100 = situation la plus défavorable) par winsorisation aux percentiles 5 et 95 puis min–max. <b>Niveaux :</b> quartiles de l'indice. <b>Unité :</b> les préfectures regroupées dans une même unité (ex. Haho + Moyen-Mono) "
                "ne peuvent pas être dissociées sans inventer de données.</div>", unsafe_allow_html=True)
    comp = T["comp"].rename(columns={"libelle": "Composante", "formule": "Formule", "sens": "Sens", "etiquette": "Nature"})[["Composante", "Formule", "Sens", "Nature"]]
    st.markdown('<div class="list-scroll" style="max-height:300px">' + tables.create_table(comp) + "</div>", unsafe_allow_html=True)
    sc = T["scen"].copy()
    sc.columns = [("Scénario" if c == "scenario" else (COMPOSANTES[c][0] if c in COMPOSANTES else "Total")) for c in sc.columns]
    st.markdown('<div class="tbl-note"><b>Pondérations des scénarios (%)</b></div>', unsafe_allow_html=True)
    st.markdown(tables.create_table(sc, num_cols=tuple(c for c in sc.columns if c != "Scénario"), formats={c: fmt_int for c in sc.columns if c != "Scénario"}), unsafe_allow_html=True)
    insights.nd_note("<b>Justification des pondérations :</b> aucune pondération officielle ou d'expert n'est fournie avec les données ; le scénario C (équilibre) donne des poids voisins aux trois familles (accès, démographie, équipement) et sert de référence ; "
                     "A, B et D déplacent l'accent vers l'accès, la population ou l'équipement. C'est une <b>HYPOTHÈSE</b> : la page mesure sa sensibilité plutôt que de la défendre. "
                     "<b>Limites :</b> le taux d'accès a un dénominateur non documenté (la population sans accès est un PROXY) ; la croissance n'est pas comparable pour Golfe et Agoè-Nyivé (valeur neutre) ; aucune donnée d'état civil territorialisée n'entre dans l'indice.")
flush_panel_css()
