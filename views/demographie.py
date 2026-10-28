"""Page « Démographie » — objectif 1 : profil démographique (population 2022, poids relatif, tailles des communes et des cantons)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from components import charts, gstate, insights, maps, tables
from components.kpi_cards import create_kpi_row
from components.sidebar import create_sidebar
from components.ui import flush_panel_css, page_title, panel
from data import loader as D, query as Q
from utils import story
from utils.formats import fmt_dec, fmt_int, fmt_pct, liste_fr
from utils.territoire import norm

f = create_sidebar("demographie")
T = D.load_tables()
K = T["kpi"]
sel_nom = Q.titre_selection(f)
page_title("fa-users", "Démographie", "Où vit la population ?")

# ---- données de la sélection (communes / cantons filtrés) ------------------------------------------------
com_f = Q.appliquer(T["commune"], f, "commune")
can_all = T["canton"][T["canton"].niveau_feuille == "canton"]
can_f = Q.appliquer(can_all, f, "canton")
NAT = K["population_totale"]
pop_sel = float(can_f.population_2022.sum()) if f["canton"] else float(com_f.population_2022.sum())
st_com = Q.demo_stats(com_f) if len(com_f) else {}

# ---- KPI (titre + valeur uniquement) ---------------------------------------------------------------------
create_kpi_row([
    {"title": f"Population 2022 · {sel_nom}", "value": fmt_int(pop_sel) if pop_sel else "N/D", "icon": "fa-users", "variant": "green"},
    {"title": "Poids dans la population nationale", "value": fmt_pct(pop_sel / NAT * 100, 2 if pop_sel / NAT < 0.1 else 1) if pop_sel else "N/D", "icon": "fa-chart-simple", "variant": "blue"},
    {"title": "Communes dans la sélection", "value": fmt_int(len(com_f) + int(com_f.commune_fusionnee.sum()) if len(com_f) else 0), "icon": "fa-city", "variant": "yellow"},
    {"title": "Taille médiane d'une commune", "value": fmt_int(st_com.get("mediane")) if st_com else "N/D", "icon": "fa-location-crosshairs", "variant": "purple"},
    {"title": "Les 10 plus grandes communes", "value": fmt_pct(st_com.get("top10_pct")) if st_com and st_com["n"] >= 10 else "N/D", "icon": "fa-ranking-star", "variant": "teal"},
])

# ---- Récit : observer / comparer -------------------------------------------------------------------------
reg_nat = T["region"][T["region"].decoupage == f["decoupage"]]
items = [("retenir", story.phrase_concentration_regions(reg_nat, 2) + " " + story.phrase_top_communes(T["commune"], 10) + " <i>(pays entier, indépendant des filtres)</i>")]
if f["region"] or f["prefecture"] or f["commune"] or f["canton"]:
    if len(com_f) >= 2:
        g, p = com_f.loc[com_f.population_2022.idxmax()], com_f.loc[com_f.population_2022.idxmin()]
        items.append(("analyse", f"<b>{sel_nom}</b> compte <b>{fmt_int(pop_sel)}</b> habitants, soit <b>{fmt_pct(pop_sel / NAT * 100, 2 if pop_sel / NAT < 0.1 else 1)}</b> du pays, répartis dans "
                                 f"<b>{len(com_f)}</b> communes. La plus peuplée, <b>{g.nom}</b> ({fmt_int(g.population_2022)}), compte <b>{fmt_dec(g.population_2022 / p.population_2022, 1)} fois</b> la plus petite, <b>{p.nom}</b> ({fmt_int(p.population_2022)})."))
    elif len(com_f) == 1:
        c = com_f.iloc[0]
        items.append(("analyse", f"<b>{c.nom}</b> compte <b>{fmt_int(c.population_2022)}</b> habitants (<b>{fmt_pct(c.poids_national_pct, 2)}</b> du pays), au rang <b>{int(c.rang_national)}</b> sur 116 lignes-communes, "
                                 f"avec <b>{int(c.nb_feuilles)}</b> {'quartiers' if c.niveau_feuille == 'quartier' else 'cantons'}."))
else:
    items.append(("analyse", f"Les tailles de communes vont de <b>{fmt_int(K['pop_commune_moins_peuplee'])}</b> ({K['commune_moins_peuplee']}) à <b>{fmt_int(K['pop_commune_plus_peuplee'])}</b> ({K['commune_plus_peuplee']}), "
                             f"soit un rapport de <b>{fmt_dec(K['rapport_max_min_communes'], 1)}</b>. Gini des communes : <b>{fmt_dec(K['gini_communes'], 2)}</b>."))
items.append(("attention", f"<b>{K['n_petits_cantons']}</b> cantons ({fmt_pct(K['part_petits_cantons_pct'], 0)} des cantons) comptent moins de <b>{fmt_int(K['seuil_petit_canton'])}</b> habitants, "
                           f"mais pèsent seulement <b>{fmt_pct(K['part_pop_petits_cantons_pct'])}</b> de la population des cantons. Seuil de 5 000 habitants : choix documenté, à discuter."))
insights.story_grid(items)

# ---- Barre de contrôle : Indicateur | Afficher + recherche ------------------------------------------------
c1, c2 = st.columns([0.95, 1.15], gap="small")
level = st.session_state["demo_level"]
top_n = 10
with c1:
    with st.container(key="ctl_ind"):
        a, b = st.columns([0.45, 1.0], gap="small", vertical_alignment="center")
        a.markdown('<span class="ctl-label">Indicateur</span>', unsafe_allow_html=True)
        indic = b.selectbox("Indicateur", ["Population 2022", "Poids relatif (%)"], key="demo_ind", label_visibility="collapsed")
with c2:
    with st.container(key="ctl_view"):
        a, b = st.columns([0.3, 0.95], gap="small", vertical_alignment="center")
        a.markdown('<span class="ctl-label">Afficher</span>', unsafe_allow_html=True)
        mode = b.segmented_control("Afficher", ["Carte", "Graphique", "Tableau"], default="Carte", key="demo_mode", label_visibility="collapsed") or "Carte"

lv = Q.demo_frame(f, level)
search = st.text_input("Rechercher un territoire", key="demo_search", placeholder=f"Rechercher parmi les {level.lower()}s…", label_visibility="collapsed")
if search:
    lv = lv[lv.Territoire.map(norm).str.contains(norm(search), regex=False)]
use_pct = indic.startswith("Poids")
lv["Valeur"] = lv.Poids if use_pct else lv.Population
vfmt = (lambda v: fmt_pct(v, 2)) if use_pct else fmt_int

# ---- Corps : carte / graphique / tableau | classement + concentration -------------------------------------
c_main, c_side = st.columns([1.3, 1.0], gap="small")
sel_ids: list = []
with c_side:
    with panel("rank", f"Classement : les {min(top_n, max(len(lv), 1))} {level.lower()}s les plus {'peuplées' if level in ('Région', 'Préfecture', 'Commune') else 'peuplés'}", "fa-ranking-star", height=130 + 27 * min(top_n, max(len(lv), 1))):
        if lv.empty:
            insights.empty_state()
        else:
            top = lv.sort_values("Valeur", ascending=False).head(top_n).copy()
            top["Libellé"] = top.Territoire
            sel_ids = charts.show_select(charts.create_rank_bar(top, "Libellé", "Valeur", "id", fmt=vfmt, height=40 + 27 * len(top), xtitle=indic), "demo_rank")
            sel_ids = [i for i in sel_ids if i in set(lv.id)]
            st.markdown('<div class="note">Cliquez sur une ou plusieurs barres : la carte, le tableau et les indicateurs se calent sur votre sélection.</div>', unsafe_allow_html=True)
    sub = lv[lv.id.isin(sel_ids)] if sel_ids else lv
    with panel("conc", "Concentration et dispersion des tailles", "fa-chart-simple", height=330):
        if len(sub) >= 3:
            from utils.demography import gini, part_top
            p = sub.Population
            share10 = part_top(p, 10) if len(p) >= 10 else 100.0
            st.markdown(charts.create_indicator_rows([
                ("fa-location-crosshairs", f"Médiane ({len(sub)} {level.lower()}s)", fmt_int(p.median()), f"moyenne : {fmt_int(p.mean())}"),
                ("fa-chart-simple", "Dispersion (écart-type)", fmt_int(p.std()), f"min {fmt_int(p.min())} · max {fmt_int(p.max())}"),
                ("fa-ranking-star", "Part des 10 plus grands", fmt_pct(share10), "de la population affichée"),
                ("fa-scale-balanced", "Indice de Gini", fmt_dec(gini(p), 2), "0 = tailles égales ; 1 = un seul territoire"),
            ]), unsafe_allow_html=True)
        else:
            insights.empty_state("Trop peu de territoires pour mesurer la concentration (moins de 3).")

with c_main:
    if mode == "Carte":
        h_map = 130 + 27 * min(top_n, max(len(lv), 1)) + 330 + 14
        with panel("map", f"Population par {level.lower()}" if not use_pct else f"Poids relatif par {level.lower()}", "fa-map", height=h_map):
            if lv.empty:
                insights.empty_state()
            elif level in ("Région", "Préfecture"):
                pf = Q.poly_frame(lv, level, f)
                v = lv.set_index("id").Valeur
                cls, leg = maps.legend_from_values(lv.Valeur, maps.SEQ_LEGEND, vfmt)
                pf["cls"] = pf.id.map(dict(zip(lv.id, cls)))
                hl = set(pf[pf.id.isin(sel_ids)].code) if sel_ids else None
                gstate.handle_click(f"map_demo_{level}", maps.create_map("Préfecture", pf, leg, key=f"map_demo_{level}", height=h_map - 70, value_label=indic, fmt=vfmt, highlight=hl), gstate.resolver_for(level, lv))
                insights.nd_note("Contours indicatifs fournis avec le template : ils servent à situer les territoires, pas à mesurer des surfaces.")
            else:
                pos = lv.dropna(subset=["lat", "lon"]).copy()
                if pos.empty:
                    insights.empty_state(f"Aucun {level.lower()} positionné pour cette sélection.")
                else:
                    pos["cls"], leg = maps.legend_from_values(pos.Valeur, maps.SEQ_LEGEND, vfmt)
                    hl = set(pos[pos.id.isin(sel_ids)].Territoire) if sel_ids else None
                    gstate.handle_click(f"map_demo_{level}", maps.create_map("Commune", pos, leg, key=f"map_demo_{level}", height=h_map - 96, value_label=indic, fmt=vfmt, highlight=hl), gstate.resolver_for(level, pos))
                    manq = len(lv) - len(pos)
                    insights.nd_note(f"{len(pos)} {level.lower()}s positionnés sur {len(lv)}" + (f" : {manq} sans coordonnées (N/D), dont les quartiers du Grand Lomé." if manq else ".")
                                     + (" Position d'une commune = barycentre de ses cantons positionnés (approximation)." if level == "Commune" else " Coordonnées approximatives fournies avec le template."))
    elif mode == "Graphique":
        with panel("graph", f"Répartition de la population entre {level.lower()}s", "fa-chart-simple", height=130 + 27 * min(top_n, max(len(lv), 1)) + 330 + 14):
            if len(lv) < 3:
                insights.empty_state("Trop peu de territoires pour tracer une distribution (moins de 3).")
            else:
                g1, g2 = st.columns(2, gap="small")
                with g1:
                    st.markdown('<div class="ctl-label" style="margin-bottom:4px">Courbe de Lorenz</div>', unsafe_allow_html=True)
                    charts.show(charts.create_lorenz(lv.Population, 300), "demo_lorenz")
                with g2:
                    st.markdown('<div class="ctl-label" style="margin-bottom:4px">Distribution des tailles</div>', unsafe_allow_html=True)
                    charts.show(charts.create_size_histogram(lv.Population, height=300), "demo_hist")
                insights.nd_note("Lorenz : plus la courbe s'éloigne de la diagonale, plus quelques territoires concentrent la population. Histogramme : nombre de territoires par classe de taille (échelle logarithmique).")
    else:
        sub = lv[lv.id.isin(sel_ids)] if sel_ids else lv
        with panel("tab", f"Détail des {level.lower()}s" + (" sélectionnés" if sel_ids else ""), "fa-table", height=130 + 27 * min(top_n, max(len(lv), 1)) + 330 + 14):
            if sub.empty:
                insights.empty_state()
            else:
                cols = [c for c in ("Rang", "Territoire", "Commune", "Préfecture", "Région", "Population", "Poids") if c in sub.columns]
                show = sub[cols].rename(columns={"Poids": "Poids (%)"})
                st.markdown(f'<div class="list-scroll" style="max-height:{130 + 27 * min(top_n, max(len(lv), 1)) + 250}px">' + tables.create_table(show, formats={"Population": fmt_int, "Poids (%)": lambda v: fmt_pct(v, 2), "Rang": lambda v: str(int(v))}) + "</div>", unsafe_allow_html=True)
                insights.nd_note(f"{len(sub)} {level.lower()}s affichés" + (" (sélection du classement)." if sel_ids else "."))

# ---- Forage (drill-down) : descendre d'un niveau sur le territoire sélectionné --------------------------
NEXT = {"Région": "Préfecture", "Préfecture": "Commune", "Commune": "Canton"}


def _drill(level: str, row: dict) -> None:
    ss = st.session_state
    pre = "w_demographie_"
    dec = f["decoupage"]
    if level == "Région":
        ss[pre + "region"] = D.labels(dec)[row["id"]]
    elif level == "Préfecture":
        ss[pre + "region"] = D.labels(dec)[row["region_code"]]
        ss[pre + "prefecture"] = row["Territoire"]
    elif level == "Commune":
        ss[pre + "region"] = D.labels(dec)[row["region_code"]]
        ss[pre + "prefecture"] = row["Préfecture"]
        ss[pre + "commune"] = row["Territoire"]
    ss["demo_level"] = NEXT[level]
    ss["demo_sig"] = None


if level in NEXT and len(sel_ids) == 1:
    row = lv[lv.id == sel_ids[0]].iloc[0].to_dict()
    hier = T["hier"]
    if level == "Préfecture":
        row["region_code"] = hier[hier.pref_raw == row["prefecture_raw"]][f["region_col"]].iloc[0]
    elif level == "Commune":
        row["region_code"] = hier[hier.com_raw == row["commune_raw"]][f["region_col"]].iloc[0]
    st.button(f"Explorer {row['Territoire']} : voir les {NEXT[level].lower()}s", key="demo_drill", on_click=_drill, args=(level, row), type="primary",
              help="Forage : applique la sélection comme filtre (cascade) et passe au niveau inférieur.")

# ---- Récit : interpréter / agir --------------------------------------------------------------------------
petits = can_f[can_f.petit_canton == True] if len(can_f) else can_f
insights.story_grid([
    ("implication", f"Avec un Gini de <b>{fmt_dec(K['gini_communes'], 2)}</b> entre communes, une dotation <b>identique par commune</b> ne suit pas la population : "
                    f"la plus grande commune compte <b>{fmt_dec(K['rapport_max_min_communes'], 1)} fois</b> la plus petite."),
    ("recommandation", f"Allouer les moyens <b>par habitant</b> (et non par commune), avec un <b>plancher</b> pour les {K['n_petits_cantons']} petits cantons, dont l'enjeu est l'accès de proximité plus que le volume. "
                       + (f"Dans la sélection : <b>{len(petits)}</b> petits cantons ({fmt_int(petits.population_2022.sum())} habitants)." if len(can_f) else "")),
])
exp = lv[[x for x in ("Rang", "Territoire", "Préfecture", "Commune", "Région", "Population", "Poids") if x in lv.columns]].rename(columns={"Poids": "Poids national (%)"})
st.download_button(
    "Exporter",
    Q.csv_bytes(exp),
    f"demographie_{norm(level).lower()}.csv",
    "text/csv",
    key="dl_btn",
    help="Exporter les données affichées (CSV, filtres actifs inclus)",
)
flush_panel_css()
