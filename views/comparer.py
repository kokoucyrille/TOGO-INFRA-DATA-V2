"""Page « Comparer » — 2 à 4 territoires côte à côte : radar (rangs percentiles) ou barres normalisées, tableau et export CSV."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components import charts, insights
from components.sidebar import create_sidebar
from components.ui import flush_panel_css, page_title, panel
from data import loader as D, query as Q
from utils.formats import fmt_dec, fmt_int, fmt_pct

f = create_sidebar("comparer")
T = D.load_tables()
FP = T["prefecture"].copy()
page_title("fa-scale-balanced", "Comparer 2 à 4 territoires", "2 à 4 territoires, mêmes indicateurs.")

METR = {  # libellé : (colonne, format, sens, nature)
    "Population 2022": ("population_2022", fmt_int, "+", "OBSERVATION"),
    "Taux d'accès 2021 (%)": ("taux_plaf_2021", lambda v: fmt_pct(v, 1), "+", "OBSERVATION"),
    "Population sans accès (PROXY)": ("pop_sans_acces_2021", fmt_int, "-", "PROXY"),
    "Agences ouvertes / 100 000 hab.": ("agences_par_100k_total", lambda v: fmt_dec(v, 2), "+", "CALCUL"),
    "Croissance annuelle 2010-2022 (%)": ("tcam_pct", lambda v: fmt_dec(v, 2), "+", "CALCUL"),
    "Indice de priorité (0-100)": ("unite_ipt", lambda v: fmt_dec(v, 1), "-", "CALCUL"),
}
c1, c2, c3 = st.columns([0.7, 1.9, 0.9], gap="small")
with c1:
    niveau = st.segmented_control("Niveau", ["Préfecture", "Région"], default="Préfecture", key="cp_niveau", help="Comparer des préfectures ou des régions (valeurs agrégées).") or "Préfecture"
rc, labs = f["region_col"], D.labels(f["decoupage"])
if niveau == "Préfecture":
    base = FP.assign(id=FP.prefecture_nom, nom=FP.prefecture_nom)
    cols = list(METR)
else:
    g = FP.groupby(rc)
    base = pd.DataFrame(dict(population_2022=g.population_2022.sum(),
                             taux_plaf_2021=g.apply(lambda x: (x.taux_plaf_2021 * x.population_2022).sum() / x.population_2022.sum(), include_groups=False),
                             pop_sans_acces_2021=g.pop_sans_acces_2021.sum(),
                             agences_par_100k_total=g.agences_ouvertes_total.sum() / g.population_2022.sum() * 1e5))
    base["id"] = base.index; base["nom"] = [labs[i] for i in base.index]
    cols = [k for k in METR if METR[k][0] in base.columns]
opts = sorted(base.nom)
defaut = list(base.sort_values("population_2022", ascending=False).nom.head(2))      # les 2 territoires les plus peuplés
with c2:
    choix = st.multiselect("Territoires (2 à 4)", opts, default=defaut, max_selections=4, key=f"cp_sel_{niveau}", help="Choisissez entre 2 et 4 territoires. Au-delà de 4, la lecture devient difficile.")
with c3:
    mode = st.segmented_control("Affichage", ["Radar", "Barres"], default="Radar", key="cp_mode", help="Radar : profil d'ensemble. Barres : une barre par territoire et indicateur, en rang percentile.") or "Radar"
if len(choix) < 2:
    insights.nd_note("Sélectionnez au moins 2 territoires pour lancer la comparaison.")
    flush_panel_css(); st.stop()

sub = base[base.nom.isin(choix)].set_index("nom").loc[choix]
rang = {}
for k in cols:
    c, _, sens, _ = METR[k]
    pct = base[c].rank(pct=True, method="average") * 100
    pct = pct.where(base[c].notna())
    pct.index = base.nom
    rang[k] = pct.reindex(choix)
R = pd.DataFrame(rang)                                    # N/D reste NaN (jamais 0)

with panel("cmp_viz", "Profil comparé (rang percentile parmi les " + ("39 préfectures" if niveau == "Préfecture" else "régions") + ")", "fa-scale-balanced", height=None):
    fig = go.Figure()
    pal = charts.COMP_COLORS
    if mode == "Radar":
        for i, n in enumerate(choix):
            fig.add_trace(go.Scatterpolar(r=R.loc[n].tolist() + [R.loc[n].iloc[0]], theta=cols + [cols[0]], name=n, fill="toself", opacity=0.45, line=dict(color=pal[i % len(pal)], width=2),
                                          hovertemplate="%{theta}<br>rang percentile : %{r:.0f}<extra>" + n + "</extra>"))
        fig.update_layout(polar=dict(radialaxis=dict(range=[0, 100], tickvals=[0, 50, 100], tickfont=dict(size=11))), height=430, margin=dict(l=70, r=70, t=30, b=30), legend=dict(orientation="h", y=-0.08))
    else:
        for i, n in enumerate(choix):
            fig.add_trace(go.Bar(y=cols, x=R.loc[n].values, name=n, orientation="h", marker_color=pal[i % len(pal)], hovertemplate="%{y}<br>rang percentile : %{x:.0f}<extra>" + n + "</extra>"))
        fig.update_layout(barmode="group", height=120 + 60 * len(cols), xaxis=dict(range=[0, 100], title="Rang percentile (0 = plus bas, 100 = plus haut)"), yaxis=dict(autorange="reversed"), margin=dict(l=10, r=10, t=10, b=40), legend=dict(orientation="h", y=1.08))
    charts.show(fig, "cp_fig")
    insights.nd_note("Rang percentile = part des territoires dont la valeur est inférieure ou égale. <b>Attention au sens</b> : pour la population sans accès et l'IPT, un rang élevé signale un besoin plus fort ; pour l'accès et les agences, un meilleur niveau. Valeur absente (N/D) : axe laissé vide, jamais 0.")

rows = []
for k in cols:
    c, fm, _, nat = METR[k]
    r = {"Indicateur": k, "Nature": nat}
    for n in choix:
        v = sub.loc[n, c]
        r[n] = fm(v) if pd.notna(v) else "N/D"
    rows.append(r)
tab = pd.DataFrame(rows)
with panel("cmp_tab", "Valeurs côte à côte", "fa-table", height=None):
    st.dataframe(tab, hide_index=True, width="stretch")
st.download_button("Exporter (CSV)", Q.csv_bytes(tab), "comparaison_territoires.csv", "text/csv", key="dl_btn", help="Tableau comparatif des territoires choisis (CSV).")
flush_panel_css()
