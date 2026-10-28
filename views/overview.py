"""Page « Vue d'ensemble » — comprendre le territoire en quelques secondes : chiffres clés, carte synthétique, classement, concentration, constats."""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from components import charts, gstate, insights, maps, tables
from components.fiche import fiche_territoire
from components.kpi_cards import create_kpi_row
from components.sidebar import create_sidebar
from components.ui import flush_panel_css, page_title, panel
from data import loader as D, query as Q
from utils import story
from utils.formats import fmt_dec, fmt_int, fmt_pct, fmt_pp, liste_fr

f = create_sidebar("overview")
T = D.load_tables()
K, FP, FU, ROB = T["kpi"], T["prefecture"], T["unite"], T["rob"]
page_title("fa-house", "Vue d'ensemble", "Le Togo en un coup d'œil.")

# ---- résumé en 30 secondes (3 messages calculés + accès direct aux priorités) -----------------------------------------------
_reg = T["region"][T["region"].decoupage == D.DEC6]
_sous = int((FP.taux_plaf_2021 < D.TAUX_NATIONAL[2021]).sum())
_syn = story.synthese_priorites(FU)
def _rs_card(tag: str, ico: str, color: str, big: str, label: str, detail: str) -> str:
    return (f'<div class="rs-card" style="--c:{color}"><div class="rs-tag"><i class="fa-solid {ico}"></i>{tag}</div>'
            f'<div class="rs-big">{big}</div><div class="rs-lab">{label}</div></div>')


_top2 = _reg.sort_values("population_2022", ascending=False).head(2)
_nsans = int(FP.sans_aucun_service.sum())
_rob3 = story.liste_fr(_syn["robustes"], 3)
with st.container(key="resume30"):
    st.markdown('<div class="resume-h"><i class="fa-solid fa-clock"></i> Résumé en 30 secondes</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3, gap="small")
    c1.markdown(_rs_card("1 · À retenir", "fa-lightbulb", "#016b4b", fmt_pct(_top2.poids_national_pct.sum()), "de la population dans 2 régions",
                         f"{story.liste_fr(_top2.nom)}. Le Grand Lomé pèse à lui seul <b>{fmt_pct(K['part_grand_lome_pct'])}</b> du pays."), unsafe_allow_html=True)
    c2.markdown(_rs_card("2 · Point d'attention", "fa-triangle-exclamation", "#c4102f", fmt_int(FU.pop_sans_acces_2021.sum()), "personnes sans accès à l'électricité (PROXY)",
                         f"Taux national publié <b>{fmt_pct(D.TAUX_NATIONAL[2021])}</b> ; <b>{_sous}</b> préfectures sur 39 sont en dessous et <b>{_nsans}</b> n'ont aucune agence CEET ni TdE ouverte."), unsafe_allow_html=True)
    c3.markdown(_rs_card("3 · Où agir", "fa-compass", "#a36f00", f"{_syn['n']} unités", "en priorité « très haute »",
                         f"<b>{_syn['n_robustes']}</b> robustes, à traiter sans regret ({_rob3}…) et <b>{_syn['n_sensibles']}</b> sensibles, à confirmer."), unsafe_allow_html=True)
    if c1.button("Explorer la carte interactive →", key="go_carte", width="stretch", help="Ouvre la carte multi-couches (population, accès, agences, IPT)."):
        st.switch_page("views/carte.py")
    if c2.button("Voir l'accès aux services →", key="go_serv", width="stretch", help="Ouvre la page Services de base (électricité, agences CEET et TdE)."):
        st.switch_page("views/services_base.py")
    if c3.button("Voir les priorités →", key="go_prio", type="primary", width="stretch", help="Ouvre la page Priorités & recommandations (classement IPT, robustesse, actions chiffrées)."):
        st.switch_page("views/recommandations.py")

# ---- sélection ---------------------------------------------------------------------------------------------
sel = Q.appliquer(FP, f, "prefecture", pref_col="prefecture_raw", use_commune=False)
filtre_actif = bool(f["region"] or f["prefecture"])
nom_sel = Q.titre_selection(f)
rc, labs = f["region_col"], D.labels(f["decoupage"])
pop = float(sel.population_2022.sum())
taux_sel = float((sel.taux_plaf_2021 * sel.population_2022).sum() / pop) if pop else np.nan
taux_aff = D.TAUX_NATIONAL[2021] if not filtre_actif else taux_sel
n_com = int(sel.prefecture_raw.map(T["hier"].groupby("pref_raw").size()).sum())
n_com += int(T["commune"].commune_fusionnee.sum()) if not filtre_actif else 0
ag_ceet, ag_tde = int(sel.ceet_ouvertes.sum()), int(sel.tde_ouvertes.sum())

create_kpi_row([
    {"title": f"Population 2022 · {nom_sel}", "value": fmt_int(pop) if pop else "N/D", "icon": "fa-users", "variant": "green"},
    {"title": "Régions" if not filtre_actif else "Régions concernées", "value": fmt_int(sel[rc].nunique()), "icon": "fa-layer-group", "variant": "blue"},
    {"title": "Préfectures", "value": fmt_int(len(sel)), "icon": "fa-building", "variant": "yellow"},
    {"title": "Communes", "value": fmt_int(n_com), "icon": "fa-city", "variant": "purple"},
], key="kpi_row")
create_kpi_row([
    {"title": "Taux d'accès à l'électricité 2021" + (" (publié)" if not filtre_actif else " (moyenne pondérée)"), "value": fmt_pct(taux_aff), "icon": "fa-bolt", "variant": "teal"},
    {"title": "Population sans accès (PROXY)", "value": fmt_int(sel.pop_sans_acces_2021.sum()) if pop else "N/D", "icon": "fa-triangle-exclamation", "variant": "red"},
    {"title": "Agences CEET ouvertes", "value": fmt_int(ag_ceet), "icon": "fa-bolt", "variant": "green"},
    {"title": "Agences TdE ouvertes", "value": fmt_int(ag_tde), "icon": "fa-droplet", "variant": "blue"},
], key="kpi_row2")
insights.nd_note("Hors filtre, le taux d'accès est le taux national <b>publié</b> ; avec un filtre, c'est la moyenne des taux des unités pondérée par la population (indicative). "
                 "« Population sans accès » = population 2022 × (1 − taux 2021) : un <b>PROXY</b> : le dénominateur du taux (≈ 12,8 % de la population 2022, nature non documentée) n'est pas la population. Le taux publié et la moyenne pondérée par la population diffèrent donc : voir « Méthode » › Réconciliation.")

# ---- récit : observer / comparer (utilisé par le résumé en 30 secondes, affiché avant les KPI) ------------------------
reg_nat = T["region"][T["region"].decoupage == f["decoupage"]]
n_sous = int((FP.taux_plaf_2021 < D.TAUX_NATIONAL[2021]).sum())
sans = FP[FP.sans_aucun_service]
syn = story.synthese_priorites(FU)
# ---- barre de contrôle -------------------------------------------------------------------------------------------
METRICS = {
    "Population 2022": dict(col="population_2022", agg="sum", fmt=fmt_int, pal=maps.SEQ_LEGEND, hi_first=True, tag="OBSERVATION"),
    "Taux d'accès à l'électricité 2021": dict(col="taux_plaf_2021", agg="wmean", fmt=lambda v: fmt_pct(v, 1), pal=maps.ACCESS_LEGEND_COLORS, hi_first=True, tag="OBSERVATION"),
    "Population sans accès (PROXY)": dict(col="pop_sans_acces_2021", agg="sum", fmt=fmt_int, pal=maps.DEFICIT_LEGEND_COLORS, hi_first=True, tag="PROXY"),
    "Indice de priorité territoriale (0–100)": dict(col="unite_ipt", agg=None, fmt=lambda v: fmt_dec(v, 1), pal=maps.DEFICIT_LEGEND_COLORS, hi_first=True, tag="CALCUL"),
}
c1, c2 = st.columns([1.55, 1.15], gap="small")
level = st.session_state["ov_level"]
with c1:
    with st.container(key="ctl_ind"):
        a, b = st.columns([0.28, 1.0], gap="small", vertical_alignment="center")
        a.markdown('<span class="ctl-label">Indicateur</span>', unsafe_allow_html=True)
        metric = b.selectbox("Indicateur", list(METRICS), key="ov_metric", label_visibility="collapsed")
M = METRICS[metric]
if M["agg"] is None and level == "Région":
    level = "Préfecture"                                           # l'IPT n'existe qu'au niveau des unités / préfectures
with c2:
    with st.container(key="ctl_view"):
        a, b = st.columns([0.45, 1.1], gap="small", vertical_alignment="center")
        a.markdown('<span class="ctl-label">Afficher</span>', unsafe_allow_html=True)
        mode = b.segmented_control("Afficher", ["Carte", "Tableau"], default="Carte", key="ov_mode", label_visibility="collapsed") or "Carte"

# ---- tableau du niveau choisi --------------------------------------------------------------------------------------
if level == "Préfecture":
    lv = pd.DataFrame(dict(id=sel.prefecture_id, Territoire=sel.prefecture_nom, Région=sel[rc].map(labs), Valeur=sel[M["col"]], prefecture_raw=sel.prefecture_raw, Population=sel.population_2022,
                           Taux=sel.taux_plaf_2021, Priorité=sel.unite_classe_priorite))
else:
    g = sel.groupby(rc)
    val = g.apply(lambda x: (x.taux_plaf_2021 * x.population_2022).sum() / x.population_2022.sum(), include_groups=False) if M["agg"] == "wmean" else g[M["col"]].sum()
    lv = pd.DataFrame(dict(id=val.index, Territoire=[labs[c] for c in val.index], Région=[labs[c] for c in val.index], Valeur=val.values, Population=g.population_2022.sum().values))
lv = lv.sort_values("Valeur", ascending=False).reset_index(drop=True)

# ---- corps ---------------------------------------------------------------------------------------------------------
c_main, c_side = st.columns([1.35, 1.0], gap="small")
sel_ids: list = []
with c_side:
    top_n = min(8, max(len(lv), 1))
    with panel("rank", f"Classement · {metric}", "fa-ranking-star", height=130 + 27 * top_n):
        if lv.empty:
            insights.empty_state()
        else:
            top = lv.head(top_n).copy()
            top["Libellé"] = top.Territoire
            ref = D.TAUX_NATIONAL[2021] if "Taux" in metric else None
            sel_ids = charts.show_select(charts.create_rank_bar(top, "Libellé", "Valeur", "id", fmt=M["fmt"], height=40 + 27 * len(top), xtitle=metric,
                                                                 ref=ref, ref_label=f"National : {fmt_pct(ref, 1)}" if ref else ""), "ov_rank")
            sel_ids = [i for i in sel_ids if i in set(lv.id)]
    with panel("conc", "Concentration de la population", "fa-chart-simple", height=330):
        if len(sel) >= 4:
            if level == "Région":
                cum = sel.groupby(rc).population_2022.sum()
                charts.show(charts.create_cumulative(cum.values, [labs[c] for c in cum.index], 270, k_marks=(2,)), "ov_conc")
            else:
                charts.show(charts.create_cumulative(sel.population_2022.values, sel.prefecture_nom.values, 270, k_marks=(5,)), "ov_conc")
        else:
            insights.empty_state("Trop peu de territoires pour mesurer la concentration.")

h_main = 130 + 27 * top_n + 330 + 14
with c_main:
    if mode == "Carte":
        with panel("map", f"{metric} · carte par {level.lower()}", "fa-map", height=h_main):
            if lv.dropna(subset=["Valeur"]).empty:
                insights.empty_state()
            else:
                pf = Q.poly_frame(lv.assign(prefecture_raw=lv.get("prefecture_raw", "")), level, f)
                cls, leg = maps.legend_from_values(lv.Valeur, M["pal"], M["fmt"], higher_is_first=M["hi_first"])
                pf["cls"] = pf.id.map(dict(zip(lv.id, cls)))
                hl = set(pf[pf.id.isin(sel_ids)].code) if sel_ids else None
                clicked = maps.create_map("Préfecture", pf, leg, key=f"map_ov_{level}", height=h_main - 70, value_label=metric, fmt=M["fmt"], highlight=hl)
                _pn = dict(zip(FP.prefecture_id, FP.prefecture_nom))
                gstate.handle_click(f"map_ov_{level}", clicked, lambda i: gstate.hierarchy_for("prefecture", _pn[i]) if level == "Préfecture" and i in _pn else ({"region": i, "prefecture": None, "commune": None, "canton": None} if level == "Région" else None))
                insights.nd_note("<b>Cliquez un territoire</b> pour filtrer toutes les pages et ouvrir sa fiche. Contours indicatifs ; au niveau « Région », chaque préfecture prend la valeur de sa région. Taux et score hérités du groupe d'unités électriques : voir « Méthode ».")
    else:
        with panel("tab", f"{metric} · détail par {level.lower()}", "fa-table", height=h_main):
            show = lv[lv.id.isin(sel_ids)] if sel_ids else lv
            cols = [c for c in ("Territoire", "Région", "Valeur", "Population", "Taux", "Priorité") if c in show.columns]
            fm = {"Valeur": M["fmt"], "Population": fmt_int, "Taux": lambda v: fmt_pct(v, 1)}
            st.markdown(f'<div class="list-scroll" style="max-height:{h_main - 80}px">' + tables.create_table(show[cols].rename(columns={"Valeur": metric}), formats={**{k if k != "Valeur" else metric: v for k, v in fm.items()}}) + "</div>", unsafe_allow_html=True)

# ---- principaux constats (Constat → Preuve → Implication) ----------------------------------------------------------
ipt_msgs = story.messages_cles(FU, FP, T["commune"], K, ROB, T["comparaison"], T["idn"])
fiche_territoire(f, "fiche_ov")
with st.expander("Tous les constats chiffrés (Constat → Preuve → Implication)", expanded=False):
    for m in ipt_msgs[:6]:
        st.markdown(f'<div class="ind-row" style="align-items:flex-start"><div class="ind-ico"><i class="fa-solid fa-circle-info"></i></div><div style="flex:1">'
                    f'<div class="ind-lab" style="font-weight:800;color:#003f8c">{m["constat"]}</div>'
                    f'<div class="note" style="font-size:13.5px;color:#1e3a4c">{m["preuve"]}</div>'
                    f'<div class="note"><b>Implication :</b> {m["implication"]}</div></div></div>', unsafe_allow_html=True)
    insights.nd_note("Les autres constats (état civil, comparabilité, qualité des données) sont détaillés dans les pages thématiques et « Méthode & données ».")
st.download_button(
    "Exporter",
    Q.csv_bytes(lv.drop(columns=[c for c in ("id", "prefecture_raw") if c in lv.columns]).rename(columns={"Valeur": metric})),
    "vue_ensemble.csv",
    "text/csv",
    key="dl_btn",
    help="Exporter les données affichées (CSV, filtres actifs inclus)",
)
flush_panel_css()
