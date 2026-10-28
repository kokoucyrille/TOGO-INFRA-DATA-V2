"""Page « Évolution 2010–2022 » — objectif 2 : évolution de la population à découpage maîtrisé (crosswalk, flags HIGH / MEDIUM / LOW)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from components import charts, gstate, insights, maps, tables
from components.kpi_cards import create_kpi_row
from components.sidebar import create_sidebar
from components.ui import flush_panel_css, page_title, panel
from data import loader as D, query as Q
from utils.formats import fmt_dec, fmt_int, fmt_pct, fmt_signe, liste_fr
from utils.territoire import norm

f = create_sidebar("evolution")
T = D.load_tables()
CP, CW = T["comparaison"], T["crosswalk"]
rc, labs = f["region_col"], D.labels(f["decoupage"])
page_title("fa-chart-line", "Évolution 2010–2022", "Population 2010 → 2022.")

U = CP[CP.niveau == "unité de comparaison"]
tn = float(((U.pop_2022.sum() / U.pop_2010.sum()) ** (1 / 12) - 1) * 100)
d_nat = float(U.pop_2022.sum() - U.pop_2010.sum())
flags = list(f["comparabilite"])
SIGNE0 = lambda v: fmt_signe(v, 0, "")

# ---- niveau d'analyse ------------------------------------------------------------------------------------------
c1, c2, c3 = st.columns([1.2, 0.8, 1.1], gap="small")
level = st.session_state["ev_level"]
IND = {"TCAM (%/an)": ("tcam_pct", lambda v: fmt_pct(v, 2)), "Variation relative (%)": ("variation_rel_pct", lambda v: fmt_signe(v, 1)),
       "Variation absolue (hab.)": ("variation_abs", SIGNE0), "Contribution à la croissance (%)": ("contribution_croissance_pct", lambda v: fmt_pct(v, 1)), "Population 2022": ("pop_2022", fmt_int)}
with c1:
    with st.container(key="ctl_ind"):
        a, b = st.columns([0.42, 1.0], gap="small", vertical_alignment="center")
        a.markdown('<span class="ctl-label">Indicateur</span>', unsafe_allow_html=True)
        ind = b.selectbox("Indicateur", list(IND), key="ev_ind", label_visibility="collapsed")
with c2:
    with st.container(key="ctl_top"):
        a, b = st.columns([0.35, 1.0], gap="small", vertical_alignment="center")
        a.markdown('<span class="ctl-label">Top</span>', unsafe_allow_html=True)
        top_n = b.segmented_control("Top N", [5, 10, 15, 20], default=10, key="ev_topn", label_visibility="collapsed") or 10
with c3:
    with st.container(key="ctl_view"):
        a, b = st.columns([0.45, 1.2], gap="small", vertical_alignment="center")
        a.markdown('<span class="ctl-label">Afficher</span>', unsafe_allow_html=True)
        mode = b.segmented_control("Afficher", ["Carte", "Graphique", "Tableau"], default="Carte", key="ev_mode", label_visibility="collapsed") or "Carte"
col, vfmt = IND[ind]

# ---- tableau du niveau (unités comparables ; régions à périmètre constant) -----------------------------------------
if level == "Région":
    niv = "région 2022 (6)" if f["decoupage"] == D.DEC6 else "région historique (5)"
    d = CP[CP.niveau == niv].copy()
    d["id"] = d[rc]
    code = f["region"] or (Q.region_of_pref(f, f["prefecture"]) if f["prefecture"] else None)
    d = d[d[rc] == code] if code else d
    d = d[d.comparability_flag.isin(flags)]
elif level == "Préfecture":
    d = U.copy()
    d["id"] = d.id_comparaison
    if f["region"]:
        d = d[d[rc] == f["region"]]
    if f["prefecture"]:
        d = d[d.prefectures_raw.fillna("").str.split(";").map(lambda L: f["prefecture"] in L)]
    d = d[d.comparability_flag.isin(flags)]
    if "LOW" in flags:                                                   # non comparables : présentés avec N/D, jamais classés
        low = CW[(CW.comparability_flag == "LOW") & (CW.niveau_comparaison == "préfecture")]
        if f["region"]:
            low = low[low[rc] == f["region"]]
        if f["prefecture"]:
            low = low[low.prefectures_raw == f["prefecture"]]
        d = pd.concat([d, pd.DataFrame(dict(id=low.id_comparaison, nom=low.territoire_2022, prefectures_raw=low.prefectures_raw, region_6=low.region_6, region_5=low.region_5, pop_2010=np.nan,
                                            pop_2022=low.pop_2022, comparability_flag="LOW", motif=low.motif, classement_autorise=False))], ignore_index=True)
else:
    d = pd.DataFrame()
d = d.reset_index(drop=True)
if len(d):
    d["Valeur"] = d[col]
nom_sel = Q.titre_selection(f)

# ---- KPI ----------------------------------------------------------------------------------------------------------
base = d[d.comparability_flag.isin(["HIGH", "MEDIUM"])] if len(d) else d
if level == "Commune" or base.empty:
    base = U[U.comparability_flag.isin(["HIGH", "MEDIUM"])] if level == "Commune" else base
p10, p22 = float(base.pop_2010.sum()) if len(base) else np.nan, float(base.pop_2022.sum()) if len(base) else np.nan
var_abs = p22 - p10
tc = ((p22 / p10) ** (1 / 12) - 1) * 100 if p10 else np.nan
create_kpi_row([
    {"title": "Population 2010 (périmètre comparable)", "value": fmt_int(p10), "icon": "fa-users", "variant": "blue"},
    {"title": "Population 2022", "value": fmt_int(p22), "icon": "fa-users", "variant": "green"},
    {"title": "Variation absolue", "value": SIGNE0(var_abs), "icon": "fa-chart-simple", "variant": "yellow"},
    {"title": "Variation relative · TCAM", "value": f"{fmt_signe((p22 / p10 - 1) * 100, 1) if p10 else 'N/D'}<br>{fmt_pct(tc, 2)}/an", "icon": "fa-chart-line", "variant": "purple", "value_style": "font-size:20px; white-space:normal; line-height:1.15;"},
    {"title": "Contribution à la croissance nationale", "value": fmt_pct(var_abs / d_nat * 100, 1) if p10 else "N/D", "icon": "fa-ranking-star", "variant": "teal"},
])
insights.nd_note(f"Sélection : <b>{nom_sel}</b>" + (f" · seules les unités comparables (HIGH / MEDIUM) entrent dans ces totaux · période : <b>2010 → 2022</b> (deux recensements, 12 ans)." if True else ""))

# ---- récit ---------------------------------------------------------------------------------------------------------
gl = U[U.nom.str.startswith("Grand Lomé")].iloc[0]
top_unit = U[U.classement_autorise].sort_values("tcam_pct", ascending=False).iloc[0]
reg5 = CP[CP.niveau == "région historique (5)"].sort_values("tcam_pct", ascending=False)
n_hm = int(CW[CW.niveau_comparaison == "préfecture"].comparability_flag.isin(["HIGH", "MEDIUM"]).sum())
zio, gln = CW[CW.territoire_2022 == "Zio"].iloc[0], CW[CW.territoire_2022.str.startswith("Grand Lomé")].iloc[0]
insights.story_grid([
    ("retenir", f"Le pays gagne <b>{fmt_int(d_nat)}</b> habitants en 12 ans (<b>{fmt_pct(tn, 2)}</b> par an). Le <b>Grand Lomé</b> explique <b>{fmt_pct(gl.contribution_croissance_pct, 0)}</b> de cette hausse pour "
                f"<b>{fmt_pct(gl.pop_2022 / U.pop_2022.sum() * 100, 0)}</b> de la population."),
    ("analyse", f"<b>{top_unit.nom}</b> croît le plus vite (<b>{fmt_pct(top_unit.tcam_pct, 1)}</b>/an). Parmi les 5 régions historiques, <b>{reg5.iloc[0].nom}</b> progresse le plus ({fmt_pct(reg5.iloc[0].tcam_pct, 1)}/an) "
                f"et <b>{reg5.iloc[-1].nom}</b> le moins ({fmt_pct(reg5.iloc[-1].tcam_pct, 1)}/an)."),
    ("attention", f"Seules <b>{n_hm}</b> préfectures sur 39 sont comparables (HIGH/MEDIUM) ; <b>Golfe</b> et <b>Agoè-Nyivé</b> ne le sont qu'<b>ensemble</b> (Grand Lomé). La croissance de Zio est probablement "
                  f"<b>sous-estimée</b> ({fmt_pct(zio.tcam_pct, 2)} → {fmt_pct(zio.tcam_sensibilite_pct, 2)} si l'on tient compte du transfert d'Adéti Kopé : ESTIMATION)."),
])

# ---- commune : non comparable ---------------------------------------------------------------------------------------
if level == "Commune":
    with panel("commune", "Évolution par commune", "fa-triangle-exclamation", height=None):
        st.markdown('<div class="story attention"><div class="s-ico"><i class="fa-solid fa-ban"></i></div><div><div class="s-tag">Comparaison impossible</div><div class="s-txt">'
                    '<b>Les communes n\'existent pas en 2010</b> : le recensement 2010 est publié par région, préfecture et canton, jamais par commune. Aucune évolution communale ne peut être calculée sans inventer des données. '
                    'Choisissez « Préfecture » ou « Région » pour comparer 2010 et 2022.</div></div></div>', unsafe_allow_html=True)
    d = pd.DataFrame()

# ---- corps ---------------------------------------------------------------------------------------------------------
sel_ids: list = []
rankable = d[d.comparability_flag.isin(["HIGH", "MEDIUM"])].dropna(subset=["Valeur"]) if len(d) else d
n_rank = min(top_n, max(len(rankable), 1))
H_RANK, H_SIDE = 130 + 27 * n_rank, 430
if level != "Commune":
    c_main, c_side = st.columns([1.3, 1.0], gap="small")
    with c_side:
        with panel("rank", f"Classement : {ind}", "fa-ranking-star", height=H_RANK):
            if rankable.empty:
                insights.empty_state()
            else:
                top = rankable.sort_values("Valeur", ascending=False).head(top_n).copy()
                top["Libellé"] = top.nom + " · " + top.comparability_flag
                sel_ids = charts.show_select(charts.create_rank_bar(top, "Libellé", "Valeur", "id", fmt=vfmt, colors=[D_FLAG for D_FLAG in top.comparability_flag.map({"HIGH": "#016b4b", "MEDIUM": "#fec902"})],
                                                                     height=40 + 27 * len(top), xtitle=ind, ref=(tn if col == "tcam_pct" else None), ref_label=f"Togo : {fmt_pct(tn, 2)}"), "ev_rank")
                sel_ids = [i for i in sel_ids if i in set(d.id)]
                st.markdown('<div class="note">Vert = comparable (HIGH) · jaune = prudence (MEDIUM). Les territoires non comparables (LOW) ne sont jamais classés. Cliquez une barre pour la mettre en évidence.</div>', unsafe_allow_html=True)
        with panel("evol", "Population 2010 → 2022", "fa-chart-line", height=H_SIDE):
            sub = rankable[rankable.id.isin(sel_ids)] if sel_ids else rankable.sort_values("pop_2022", ascending=False).head(min(top_n, 8))
            if sub.empty:
                insights.empty_state()
            else:
                pop_values = sub[["pop_2010", "pop_2022"]].to_numpy(dtype=float)
                min_pop, max_pop = pop_values.min(), pop_values.max()
                log_x = bool(min_pop > 0 and max_pop / min_pop > 8)
                charts.show(charts.create_population_comparison_chart(sub, height=360, log_x=log_x), "ev_lines")
                insights.nd_note("Deux recensements seulement : la ligne relie 2010 et 2022, elle ne décrit pas l'évolution intermédiaire." + (" Échelle logarithmique." if log_x else ""))
    H_MAIN = H_RANK + H_SIDE + 14
    with c_main:
        if mode == "Carte":
            with panel("map", f"{ind} · carte par {level.lower()}", "fa-map", height=H_MAIN):
                if d.empty:
                    insights.empty_state()
                else:
                    legend_mode = "flag"
                    pf = pd.DataFrame(columns=["code", "Territoire", "Valeur", "id"])
                    rows = []
                    if level == "Région":
                        for _, r in d.iterrows():
                            for pref in T["hier"][T["hier"][rc] == r["id"]].pref_raw.unique():
                                for nm in D.polygons_of_prefecture().get(pref, []):
                                    rows.append(dict(code=nm, Territoire=r.nom, Valeur=r.Valeur, tip=r.nom, id=r["id"], flag=r.comparability_flag))
                    else:
                        for _, r in d[d.comparability_flag != "LOW"].iterrows():
                            for pref in str(r.prefectures_raw).split(";"):
                                for nm in D.polygons_of_prefecture().get(pref, []):
                                    rows.append(dict(code=nm, Territoire=r.nom, Valeur=r.Valeur, tip=r.nom, id=r["id"], flag=r.comparability_flag))
                    pf = pd.DataFrame(rows)
                    base_v = pf.drop_duplicates("id")
                    cls, leg = maps.legend_from_values(base_v.Valeur, maps.SEQ_LEGEND, vfmt)
                    pf["cls"] = pf.id.map(dict(zip(base_v.id, cls)))
                    hl = set(pf[pf.id.isin(sel_ids)].code) if sel_ids else None
                    gstate.handle_click(f"map_ev_{level}", maps.create_map("Préfecture", pf, leg, key=f"map_ev_{level}", height=H_MAIN - 70, value_label=ind, fmt=vfmt, highlight=hl), gstate.resolver_for(level, base_v, idcol="id"))
                    insights.nd_note("Les polygones sans couleur ne sont pas comparables ou sont hors sélection. Grand Lomé : Golfe et Agoè-Nyivé sont colorés ensemble (unité de comparaison unique). Contours indicatifs.")
        elif mode == "Graphique":
            with panel("graph", "Rythme de croissance et part de l'accroissement", "fa-chart-simple", height=H_MAIN):
                if rankable.empty:
                    insights.empty_state()
                else:
                    g = rankable.sort_values("contribution_croissance_pct", ascending=False).head(top_n).copy()
                    g["Libellé"] = g.nom + " · " + g.comparability_flag
                    charts.show(charts.create_rank_bar(g, "Libellé", "contribution_croissance_pct", "id", fmt=lambda v: fmt_pct(v, 1), colors=g.comparability_flag.map({"HIGH": "#016b4b", "MEDIUM": "#fec902"}).tolist(),
                                                       height=H_MAIN - 110, xtitle="Part de l'accroissement national 2010–2022 (%)", selected=sel_ids), "ev_contrib")
                    insights.nd_note(f"Contribution = variation du territoire ÷ accroissement national ({fmt_int(d_nat)} habitants). Elle dépend de la taille autant que de la vitesse de croissance.")
        else:
            with panel("tab", f"Détail par {level.lower()}", "fa-table", height=H_MAIN):
                show = d[d.id.isin(sel_ids)] if sel_ids else d
                if show.empty:
                    insights.empty_state()
                else:
                    t = show.sort_values("Valeur", ascending=False)[["nom", "comparability_flag", "pop_2010", "pop_2022", "variation_abs", "variation_rel_pct", "tcam_pct", "contribution_croissance_pct"]].rename(columns={
                        "nom": "Territoire", "comparability_flag": "Comparabilité", "pop_2010": "Pop. 2010", "pop_2022": "Pop. 2022", "variation_abs": "Variation", "variation_rel_pct": "Variation (%)",
                        "tcam_pct": "TCAM (%/an)", "contribution_croissance_pct": "Contribution (%)"})
                    st.markdown(f'<div class="list-scroll" style="max-height:{H_MAIN - 80}px">' + tables.create_table(t, formats={"Pop. 2010": fmt_int, "Pop. 2022": fmt_int, "Variation": SIGNE0,
                                "Variation (%)": lambda v: fmt_signe(v, 1), "TCAM (%/an)": lambda v: fmt_pct(v, 2), "Contribution (%)": lambda v: fmt_pct(v, 1)}) + "</div>", unsafe_allow_html=True)
                    insights.nd_note("N/D = valeur non calculable (territoire non comparable). Aucune valeur n'est remplacée par zéro.")
# ---- Les deux recensements, territoire par territoire (région / préfecture)
st.subheader("Les deux recensements (2010 et 2022), territoire par territoire")
insights.story("analyse", "Population de chaque territoire aux deux recensements, avec la variation entre les deux dates. "
               "Le niveau <b>Région</b> est à périmètre constant ; le niveau <b>Préfecture</b> utilise les unités de comparaison (Grand Lomé en bloc, voir plus bas). "
               "Les territoires non comparables restent affichés pour 2022 et en <b>N/D</b> pour 2010 : aucune valeur n'est inventée.")
k1, k2, k3 = st.columns([0.9, 1.5, 1.0], gap="small")
with k1:
    with st.container(key="ctl_cens_niv"):
        st.markdown('<span class="ctl-label">Niveau</span>', unsafe_allow_html=True)
        niv_c = st.segmented_control("Niveau (recensements)", ["Région", "Préfecture"], default="Région", key="ev_cens_niv", label_visibility="collapsed",
                                     help="Région : 6 régions 2022 (ou 5 historiques selon le découpage choisi). Préfecture : unités de comparaison 2010 ↔ 2022.") or "Région"
with k2:
    with st.container(key="ctl_cens_tri"):
        st.markdown('<span class="ctl-label">Trier par</span>', unsafe_allow_html=True)
        tri_c = st.segmented_control("Trier par", ["Population 2022", "Variation (%)", "TCAM"], default="Population 2022", key="ev_cens_tri", label_visibility="collapsed",
                                     help="Ordre d'affichage : plus peuplés d'abord, plus forte variation relative, ou plus fort taux de croissance annuel moyen (TCAM).") or "Population 2022"
with k3:
    with st.container(key="ctl_cens_nb"):
        st.markdown('<span class="ctl-label">Préfectures affichées</span>', unsafe_allow_html=True)
        nb_c = st.segmented_control("Nombre de préfectures", [10, 20, "Toutes"], default=10, key="ev_cens_nb", label_visibility="collapsed", disabled=niv_c == "Région",
                                    help="Nombre de préfectures dessinées (niveau Préfecture). Le tableau et l'export CSV contiennent toujours tous les territoires du périmètre.") or 10
if niv_c == "Région":
    dc = CP[CP.niveau == ("région 2022 (6)" if f["decoupage"] == D.DEC6 else "région historique (5)")].copy()
    dc["Territoire"] = dc[rc].map(labs).fillna(dc.nom)
    code_c = f["region"] or (Q.region_of_pref(f, f["prefecture"]) if f["prefecture"] else None)
    dc = dc[dc[rc] == code_c] if code_c else dc
else:
    dc = U.copy()
    dc["Territoire"] = dc.nom
    code_c = f["region"] or (Q.region_of_pref(f, f["prefecture"]) if f["prefecture"] else None)
    dc = dc[dc[rc] == code_c] if code_c else dc
    if f["prefecture"]:
        dc = dc[dc.prefectures_raw.astype(str).str.split(";").apply(lambda l: f["prefecture"] in l)]
_tri = {"Population 2022": "pop_2022", "Variation (%)": "variation_rel_pct", "TCAM": "tcam_pct"}[tri_c]
dc = dc.sort_values(_tri, ascending=False, na_position="last")          # N/D toujours en fin de liste
if dc.empty:
    insights.empty_state("Aucun territoire pour cette sélection.")
else:
    dg = dc if (niv_c == "Région" or nb_c == "Toutes") else dc.head(int(nb_c))
    H_C = 150 + 46 * len(dg)
    cc1, cc2 = st.columns([1.5, 1.0], gap="small")
    with cc1:
        with panel("cens_graph", f"Population 2010 et 2022 · {len(dg)} {niv_c.lower()}{'s' if len(dg) > 1 else ''} · tri : {tri_c.lower()}", "fa-chart-simple", height=None):
            import plotly.graph_objects as go
            g = dg
            nd = lambda v: "N/D" if v != v else charts.compact(v)
            lab22 = [f"<b>{charts.compact(p)}</b>  ({fmt_signe(v, 0)})" if v == v else f"<b>{charts.compact(p)}</b>  (variation N/D)" for p, v in zip(g.pop_2022, g.variation_rel_pct)]
            fig = go.Figure()
            fig.add_trace(go.Bar(y=g.Territoire, x=g.pop_2010, name="Recensement 2010", orientation="h", marker_color="#8fb8e8", text=[nd(v) for v in g.pop_2010],
                                 textposition="outside", cliponaxis=False, textfont=dict(size=12, color="#4f6270"),
                                 hovertemplate="<b>%{y}</b><br>2010 : %{x:,.0f} hab.<extra></extra>"))
            fig.add_trace(go.Bar(y=g.Territoire, x=g.pop_2022, name="Recensement 2022", orientation="h", marker_color="#016b4b", text=lab22,
                                 textposition="outside", cliponaxis=False, textfont=dict(size=12, color="#0b4a35"),
                                 customdata=g[["variation_rel_pct", "tcam_pct"]].to_numpy(),
                                 hovertemplate="<b>%{y}</b><br>2022 : %{x:,.0f} hab.<br>Variation : %{customdata[0]:+.1f} %<br>TCAM : %{customdata[1]:.2f} %/an<extra></extra>"))
            fig.update_layout(barmode="group", height=H_C, margin=dict(l=8, r=8, t=40, b=36), bargap=0.22, bargroupgap=0.06,
                              legend=dict(orientation="h", y=1.0, yanchor="bottom", x=0, font=dict(size=13)),
                              xaxis=dict(range=[0, float(g.pop_2022.max()) * 1.38], showgrid=True, gridcolor="#e3edf0", tickformat=".2s", title=dict(text="Habitants", font=dict(size=12)), zeroline=False),
                              yaxis=dict(tickfont=dict(size=13, color="#1e3a4c"), automargin=True, autorange="reversed"), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            charts.show(fig, "ev_cens_fig")
            insights.nd_note("<b>OBSERVATION</b> · RGPH 2010 et RGPH-5 2022. Étiquette verte : population 2022 et variation depuis 2010. N/D : territoire non comparable (aucune valeur 2010).")
    with cc2:
        with panel("cens_tab", "Variation entre les deux recensements", "fa-table", height=None):
            t = pd.DataFrame({"Territoire": dc.Territoire, "2010": dc.pop_2010, "2022": dc.pop_2022, "Variation (%)": dc.variation_rel_pct, "TCAM (%/an)": dc.tcam_pct})
            fm = {"2010": lambda v: fmt_int(v) if v == v else "N/D", "2022": fmt_int, "Variation (%)": lambda v: fmt_signe(v, 1) if v == v else "N/D",
                  "TCAM (%/an)": lambda v: fmt_dec(v, 2) if v == v else "N/D"}
            st.markdown(f'<div class="list-scroll" style="max-height:{max(H_C - 60, 300)}px">' + tables.create_table(t, formats=fm, num_cols=("2010", "2022", "Variation (%)", "TCAM (%/an)")) + "</div>", unsafe_allow_html=True)
            st.download_button("Exporter (CSV)", Q.csv_bytes(t), f"recensements_2010_2022_{niv_c.lower()}.csv", "text/csv", key="dl_cens",
                               help="Population 2010 et 2022, variation et TCAM de tous les territoires du niveau et du périmètre filtrés.")

# ---- Comparabilité 2010–2022 --------------------------------------------------------------------------------------
pref_rows = CW[CW.niveau_comparaison == "préfecture"]
cnt = pref_rows.groupby("comparability_flag").agg(n=("id_comparaison", "size"), pop=("pop_2022", "sum"))
tot_pop = pref_rows.pop_2022.sum()
def _card(fl, titre, texte):
    n, p = int(cnt.loc[fl, "n"]) if fl in cnt.index else 0, float(cnt.loc[fl, "pop"]) if fl in cnt.index else 0
    return f'<div class="cmp-card {fl.lower()}"><div class="t">{titre}</div><div class="n">{n} préfectures</div><div class="d"><b>{fmt_pct(p / tot_pop * 100, 0)}</b> de la population 2022. {texte}</div></div>'
with panel("compar", "Comparabilité 2010–2022 : ce qui peut, et ne peut pas, être comparé", "fa-scale-balanced", height=None):
    st.markdown('<div class="cmp-grid">' +
                _card("HIGH", "Comparable (HIGH)", "Le périmètre est identique aux deux dates (ou reconstitué exactement par cantons) : la comparaison est fiable.") +
                _card("MEDIUM", "À lire avec prudence (MEDIUM)", "Libellés de cantons hétérogènes entre 2010 et 2022, ou petit transfert de canton (Zio) : l'ordre de grandeur est bon, le détail moins.") +
                _card("LOW", "Non comparable (LOW)", "Le territoire a changé de périmètre sans équivalent exact (Golfe, Agoè-Nyivé) : aucune croissance n'est calculée séparément ; seule leur union, le Grand Lomé, est comparable.") + "</div>", unsafe_allow_html=True)
    st.markdown("<div class='note' style='font-size:13.5px;color:#1e3a4c'><b>Pourquoi ?</b> Entre 2010 et 2022, <b>Kpendjal</b> et <b>Oti</b> ont chacune été scindées en deux préfectures, et le <b>Grand Lomé</b> a été recomposé "
                "(Lomé commune + Golfe 2010 devenus Golfe + Agoè-Nyivé). Les <b>communes</b> n'existent pas dans les données 2010. On compare donc des <b>unités de comparaison</b> (33 préfectures inchangées, 4 moitiés "
                "reconstituées par cantons, le Grand Lomé en bloc), et on ne compare jamais deux territoires sur leur seul nom.</div>", unsafe_allow_html=True)
    nh = pref_rows[pref_rows.comparability_flag != "HIGH"][["territoire_2022", "comparability_flag", "type_correspondance", "motif"]].rename(columns={
        "territoire_2022": "Territoire", "comparability_flag": "Fiabilité", "type_correspondance": "Correspondance", "motif": "Motif"})
    st.markdown(f'<div class="list-scroll" style="max-height:300px">' + tables.create_table(nh.sort_values("Fiabilité"), formats={}) + "</div>", unsafe_allow_html=True)
    insights.nd_note("Seuil HIGH : au moins 90 % de la population 2010 de la préfecture couverte par des cantons retrouvés à l'identique. Sensibilité Zio / Grand Lomé : ESTIMATION indicative (voir « Méthode & données »).")

insights.story_grid([
    ("implication", f"La croissance est concentrée : <b>{top_unit.nom}</b> croît à <b>{fmt_pct(top_unit.tcam_pct, 1)}</b>/an contre <b>{fmt_pct(tn, 2)}</b> pour le pays ; "
                    f"<b>{int((U[U.classement_autorise].tcam_pct > tn).sum())}</b> unités sur <b>{int(U.classement_autorise.sum())}</b> croissent plus vite que le pays : la demande potentielle de services y augmente le plus vite."),
    ("recommandation", "Croiser ces rythmes avec l'accès à l'électricité et aux agences (page « Services de base ») avant d'arbitrer : une croissance rapide ne justifie un renforcement que si le territoire est aussi sous-équipé."),
])
if level != "Commune":
    exp = d.drop(columns=[x for x in ("id", "Valeur", "classement_autorise", "prefectures_raw") if x in d.columns]) if len(d) else pd.DataFrame({"info": ["aucune donnée"]})
    st.download_button(
        "Exporter",
        Q.csv_bytes(exp),
        "evolution_2010_2022.csv",
        "text/csv",
        key="dl_btn",
        help="Exporter les données affichées (CSV, filtres actifs inclus)",
    )
flush_panel_css()
