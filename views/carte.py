"""Page « Carte interactive » — une carte multi-couches (population, accès, personnes sans accès, IPT, agences) ; un clic filtre tout le tableau de bord."""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from components import charts, gstate, insights, maps, tables
from components.fiche import fiche_territoire
from components.sidebar import create_sidebar
from components.ui import flush_panel_css, page_title, panel
from data import loader as D, query as Q
from utils.formats import fmt_dec, fmt_int, fmt_pct

f = create_sidebar("carte")
T = D.load_tables()
FP = T["prefecture"]
page_title("fa-map", "Carte interactive", "Couches, agences et territoires cliquables.")

COUCHES = {
    "Population 2022": dict(col="population_2022", agg="sum", fmt=fmt_int, pal=maps.SEQ_LEGEND, tag="OBSERVATION", aide="Population résidente (RGPH-5)."),
    "Taux d'accès à l'électricité 2021": dict(col="taux_plaf_2021", agg="wmean", fmt=lambda v: fmt_pct(v, 1), pal=maps.ACCESS_LEGEND_COLORS, tag="OBSERVATION", aide="Taux publié par unité électrique, plafonné à 100 % ; hérité par les préfectures d'un groupe."),
    "Population sans accès (PROXY)": dict(col="pop_sans_acces_2021", agg="sum", fmt=fmt_int, pal=maps.DEFICIT_LEGEND_COLORS, tag="PROXY", aide="Population 2022 × (1 − taux 2021) : ordre de grandeur."),
    "Agences ouvertes pour 100 000 hab.": dict(col="agences_par_100k_total", agg="ratio", fmt=lambda v: fmt_dec(v, 2), pal=maps.ACCESS_LEGEND_COLORS, tag="CALCUL", aide="Agences CEET + TdE ouvertes ÷ population × 100 000 (0 = aucune agence ouverte)."),
    "Indice de priorité territoriale (0–100)": dict(col="unite_ipt", agg=None, fmt=lambda v: fmt_dec(v, 1), pal=maps.DEFICIT_LEGEND_COLORS, tag="CALCUL", aide="IPT du scénario C ; la préfecture hérite du score de son unité électrique."),
}
c1, c2 = st.columns([1.5, 1.4], gap="small")
with c1:
    with st.container(key="ctl_ind"):
        a, b = st.columns([0.28, 1.0], gap="small", vertical_alignment="center")
        a.markdown('<span class="ctl-label">Couche</span>', unsafe_allow_html=True)
        couche = b.selectbox("Couche", list(COUCHES), key="ca_couche", label_visibility="collapsed", help="Indicateur coloré sur la carte. Les agences se superposent avec les cases à droite.")
with c2:
    with st.container(key="ctl_view"):
        a, b, c = st.columns([0.30, 0.8, 0.8], gap="small", vertical_alignment="center")
        a.markdown('<span class="ctl-label">Niveau</span>', unsafe_allow_html=True)
        niveau = b.segmented_control("Niveau", ["Préfecture", "Région"], default="Préfecture", key="ca_niveau", label_visibility="collapsed", help="Région : valeurs agrégées ; chaque préfecture prend la valeur de sa région.") or "Préfecture"
        show_ceet = c.checkbox("Agences CEET", key="ca_ceet", help="Points des agences CEET (pastille noire pleine = ouverte, creuse = non ouverte).")
        show_tde = c.checkbox("Agences TdE", key="ca_tde", help="Points des agences TdE (losange violet plein = ouvert, creux = non ouvert).")
M = COUCHES[couche]
if M["agg"] is None:
    niveau = "Préfecture"                                           # l'IPT n'existe qu'à l'échelle des unités / préfectures

sel = Q.appliquer(FP, f, "prefecture", pref_col="prefecture_raw", use_commune=False)
rc, labs = f["region_col"], D.labels(f["decoupage"])
if niveau == "Préfecture":
    lv = pd.DataFrame(dict(id=sel.prefecture_id, Territoire=sel.prefecture_nom, Région=sel[rc].map(labs), Valeur=sel[M["col"]], prefecture_raw=sel.prefecture_raw, Population=sel.population_2022))
else:
    g = sel.groupby(rc)
    if M["agg"] == "wmean":
        val = g.apply(lambda x: (x.taux_plaf_2021 * x.population_2022).sum() / x.population_2022.sum(), include_groups=False)
    elif M["agg"] == "ratio":
        val = g.apply(lambda x: x.agences_ouvertes_total.sum() / x.population_2022.sum() * 1e5, include_groups=False)
    else:
        val = g[M["col"]].sum()
    lv = pd.DataFrame(dict(id=val.index, Territoire=[labs[c] for c in val.index], Région=[labs[c] for c in val.index], Valeur=val.values, Population=g.population_2022.sum().values))
lv = lv.sort_values("Valeur", ascending=False).reset_index(drop=True)

c_map, c_side = st.columns([1.7, 1.0], gap="small")
sel_ids: list = []
with c_side:
    fiche_territoire(f, "fiche_ca")
    with panel("rank_ca", f"Classement · {couche}", "fa-ranking-star", height=None):
        if lv.dropna(subset=["Valeur"]).empty:
            insights.empty_state()
        else:
            top = lv.dropna(subset=["Valeur"]).head(10).copy()
            top["Libellé"] = top.Territoire
            sel_ids = charts.show_select(charts.create_rank_bar(top, "Libellé", "Valeur", "id", fmt=M["fmt"], height=40 + 27 * len(top), xtitle=couche), "ca_rank")
            sel_ids = [i for i in sel_ids if i in set(lv.id)]
            st.markdown('<div class="note">Cliquez une barre pour sélectionner le territoire (filtre global).</div>', unsafe_allow_html=True)
with c_map:
    with panel("map_ca", f"{couche} · carte par {niveau.lower()}", "fa-map", height=None):
        if lv.dropna(subset=["Valeur"]).empty:
            insights.empty_state()
        else:
            pf = Q.poly_frame(lv.assign(prefecture_raw=lv.get("prefecture_raw", "")), niveau, f)
            cls, leg = maps.legend_from_values(lv.Valeur, M["pal"], M["fmt"], higher_is_first=True)
            pf["cls"] = pf.id.map(dict(zip(lv.id, cls)))
            pf["Valeur"] = pf.id.map(dict(zip(lv.id, lv.Valeur)))
            actif = f.get("prefecture")
            hl_ids = set(sel_ids) | ({int(FP[FP.prefecture_raw == actif].prefecture_id.iloc[0])} if actif and niveau == "Préfecture" else set()) | ({f["region"]} if f.get("region") and niveau == "Région" else set())
            hl = set(pf[pf.id.isin(hl_ids)].code) if hl_ids else None
            ag = T["agences"]
            services = tuple(s for s, on in (("CEET", show_ceet), ("TdE", show_tde)) if on)
            extra = maps.agency_traces(ag, services) if services else []
            clicked = maps.create_map("Préfecture", pf, leg, key=f"map_ca_{niveau}", height=560, value_label=couche, fmt=M["fmt"], highlight=hl, extra_traces=extra)
            _pn = dict(zip(FP.prefecture_id, FP.prefecture_nom))
            gstate.handle_click(f"map_ca_{niveau}", clicked, lambda i: gstate.hierarchy_for("prefecture", _pn[i]) if niveau == "Préfecture" and i in _pn
                                else ({"region": i, "prefecture": None, "commune": None, "canton": None} if niveau == "Région" else None))
            insights.nd_note(f"<b>{M['tag']}</b> · {M['aide']} Classes d'effectif équilibré (5 classes de rang), du plus haut au plus bas. Gris : hors sélection ou valeur absente (N/D). Contour bleu : territoire sélectionné. "
                             "Contours indicatifs : ils situent les territoires, ils ne mesurent pas de surfaces. Survolez un territoire pour lire sa valeur ; l'icône en haut à droite exporte la carte en PNG.")
            if services:
                n_ouv = int(ag[ag.service.isin(services) & ag.ouverte_public.astype(bool)].shape[0])
                insights.nd_note(f"Agences superposées : {n_ouv} ouvertes sur les services affichés ({', '.join(services)}) ; pastille creuse = agence non ouverte.")
st.download_button("Exporter (CSV)", Q.csv_bytes(lv.drop(columns=[c for c in ("id", "prefecture_raw") if c in lv.columns]).rename(columns={"Valeur": couche})), "carte_interactive.csv", "text/csv", key="dl_btn",
                   help="Valeurs de la couche pour le périmètre filtré (CSV, filtres actifs inclus).")
flush_panel_css()
