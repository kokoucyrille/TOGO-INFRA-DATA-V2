"""Page « État civil & identité » — objectif 4 : enregistrement des naissances et production de CNI / passeports (séries nationales)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from components import charts, insights, maps, tables
from components.kpi_cards import create_kpi_row
from components.sidebar import create_sidebar
from components.ui import flush_panel_css, page_title, panel
from data import loader as D, query as Q
from utils.formats import fmt_dec, fmt_int, fmt_pct, fmt_signe, liste_fr

T = D.load_tables()
EC, ID = T["ec"], T["idn"]

MOTIF = {"aberrante": "valeur aberrante", "zero_suspect": "total nul suspect", "doublon_inter_series": "identique à une autre série", "rupture": "rupture de série"}
EC_A = EC[(EC.serie == "A") & ~EC.absent_du_fichier]
CODES = EC_A.drop_duplicates("indicateur_code").set_index("indicateur_code").indicateur.to_dict()
PRINCIPAL = "enfants_enreg_45j"
ID_LAB = {"cni": "Cartes nationales d'identité", "passeports": "Passeports", "cartes_pro": "Cartes professionnelles", "total": "Total des documents"}
ID_COL = {"cni": "#016b4b", "passeports": "#1488ee", "cartes_pro": "#fec902", "total": "#003f8c"}

# ---- Sidebar : sections ordonnées (période → état civil → identité → affichage), puis note et « Réinitialiser » ----------
def _sidebar_sections() -> None:
    def titre(texte: str, icone: str) -> None:
        st.markdown(f'<div class="f-label"><i class="fa-solid {icone}"></i><span>{texte}</span></div>', unsafe_allow_html=True)
    titre("ÉTAT CIVIL · NAISSANCES", "fa-chart-line")
    st.selectbox("Indicateur d'état civil", list(CODES), format_func=lambda c: CODES[c], key="ec_ind", label_visibility="collapsed")
    st.segmented_control("Sexe (état civil)", ["Total", "H / F"], default="Total", key="ec_sexe", label_visibility="collapsed")
    titre("IDENTITÉ · DOCUMENTS", "fa-id-card")
    st.multiselect("Documents d'identité", list(ID_LAB), default=["cni", "passeports"], format_func=lambda t: ID_LAB[t], key="ec_types",
                   label_visibility="collapsed", placeholder="Choisir des documents")
    titre("AFFICHAGE", "fa-sliders")
    st.segmented_control("Afficher", ["Graphique", "Tableau"], default="Graphique", key="ec_mode", label_visibility="collapsed")


f = create_sidebar("etat_civil", extras=_sidebar_sections)
p0, p1 = f["periode"]
code = st.session_state.get("ec_ind", next(iter(CODES)))
types = st.session_state.get("ec_types", ["cni", "passeports"])
sexe = st.session_state.get("ec_sexe") or "Total"
mode = st.session_state.get("ec_mode") or "Graphique"
page_title("fa-id-card", "État civil & identité", "Naissances, CNI et passeports.")


def serie_ec(code: str, sexe: str = "Total") -> pd.DataFrame:
    d = EC[(EC.indicateur_code == code) & (EC.serie == "A") & (EC.sexe == sexe) & ~EC.absent_du_fichier & EC.annee.between(p0, p1)].copy()
    d["ok"] = d.valide_pour_tendance.astype(bool)
    d["motif"] = d.apply(lambda r: MOTIF.get(r.anomalie, "rapport H/F improbable" if r.hf_improbable else ""), axis=1)
    return d.sort_values("annee")


def variation(d: pd.DataFrame, val: str, an: str = "annee") -> pd.DataFrame:
    """Variation annuelle (%) entre années consécutives TOUTES DEUX valides ; sinon N/D (jamais calculée sur une valeur écartée)."""
    d = d.sort_values(an).copy()
    prev = d[val].shift(1)
    cons = d[an].diff() == 1
    d["var_pct"] = np.where(cons & prev.notna() & d[val].notna() & (prev != 0), (d[val] / prev - 1) * 100, np.nan)
    return d


# ---- KPI -----------------------------------------------------------------------------------------------------------------
s0 = serie_ec(PRINCIPAL)
s0v = s0[s0.ok].dropna(subset=["valeur_brute"])
id_p = ID[ID.annee.between(p0, p1)]
def last_val(t):
    d = id_p[(id_p.type == t) & id_p.valeur_brute.notna()].sort_values("annee")
    return (int(d.annee.iloc[-1]), float(d.valeur_brute.iloc[-1])) if len(d) else (None, np.nan)
(a_cni, v_cni), (a_pas, v_pas), (a_tot, v_tot) = last_val("cni"), last_val("passeports"), last_val("total")
if len(s0v) >= 2:
    ya, yb = int(s0v.annee.iloc[0]), int(s0v.annee.iloc[-1])
    va, vb = float(s0v.valeur_brute.iloc[0]), float(s0v.valeur_brute.iloc[-1])
    pic = s0v.loc[s0v.valeur_brute.idxmax()]
else:
    ya = yb = va = vb = pic = None
create_kpi_row([
    {"title": f"Enfants enregistrés dans les 45 jours ({yb})" if yb else "Enfants enregistrés dans les 45 jours", "value": fmt_int(vb) if yb else "N/D", "icon": "fa-users", "variant": "green"},
    {"title": f"Évolution {ya}→{yb}" if yb else "Évolution", "value": fmt_signe((vb / va - 1) * 100, 1) if yb and va else "N/D", "icon": "fa-chart-line", "variant": "red" if (yb and vb < va) else "blue"},
    {"title": f"Cartes nationales d'identité ({a_cni})" if a_cni else "Cartes nationales d'identité", "value": fmt_int(v_cni), "icon": "fa-id-card", "variant": "yellow"},
    {"title": f"Passeports ({a_pas})" if a_pas else "Passeports", "value": fmt_int(v_pas), "icon": "fa-book-open", "variant": "purple"},
    {"title": f"Documents d'identité produits ({a_tot})" if a_tot else "Documents d'identité produits", "value": fmt_int(v_tot), "icon": "fa-table", "variant": "teal"},
])
lacunes = sorted(ID[ID.lacune_source & ID.annee.between(p0, p1)].annee.unique())
insights.nd_note(f"Période : <b>{p0}–{p1}</b>. Données <b>nationales</b> : l'état civil et l'identité n'ont aucune dimension territoriale ni dénominateur de naissances attendues, donc aucun <b>taux</b> d'enregistrement n'est calculable. "
                 + (f"<b>{liste_fr(lacunes)}</b> : absent(e) de la source pour la CNI, les cartes professionnelles et le total (affiché N/D)." if lacunes else ""))

# ---- récit ---------------------------------------------------------------------------------------------------------------
bad = EC[(EC.sexe == "Total") & (EC.serie == "A") & EC.anomalie.isin(["aberrante", "zero_suspect", "doublon_inter_series"]) & EC.annee.between(p0, p1)]
rup = EC[(EC.sexe == "Total") & (EC.serie == "A") & (EC.anomalie == "rupture") & EC.annee.between(p0, p1)]
cni = ID[(ID.type == "cni") & ID.valeur_brute.notna() & ID.annee.between(p0, p1)].set_index("annee").valeur_brute
pas = ID[(ID.type == "passeports") & ID.valeur_brute.notna() & ID.annee.between(p0, p1)].set_index("annee").valeur_brute
items = []
if yb:
    items.append(("retenir", f"Le nombre d'enfants enregistrés dans les 45 jours passe de <b>{fmt_int(va)}</b> ({ya}) à <b>{fmt_int(vb)}</b> ({yb}), soit <b>{fmt_signe((vb / va - 1) * 100, 1)}</b> ; "
                             f"le maximum est atteint en <b>{int(pic.annee)}</b> ({fmt_int(pic.valeur_brute)})."))
if len(cni) >= 2 and len(pas) >= 2:
    pc = int(cni.idxmax())
    items.append(("analyse", f"La production de <b>CNI</b> est passée de <b>{fmt_int(cni[pc])}</b> ({pc}) à <b>{fmt_int(cni.iloc[-1])}</b> ({int(cni.index[-1])}), soit <b>{fmt_signe((cni.iloc[-1] / cni[pc] - 1) * 100, 0)}</b>, "
                             f"alors que les <b>passeports</b> évoluent de <b>{fmt_signe((pas.iloc[-1] / pas.iloc[0] - 1) * 100, 0)}</b> entre {int(pas.index[0])} et {int(pas.index[-1])}."))
items.append(("attention", f"<b>{len(bad)}</b> valeurs d'état civil sont <b>écartées</b> des tendances (aberrantes, nulles ou doublons) et <b>{len(rup)}</b> ruptures de série sont signalées. "
                           f"Elles restent visibles (croix rouge) mais ne sont ni corrigées, ni reliées par la courbe." + (f" Année(s) absente(s) de la source : <b>{liste_fr(lacunes)}</b>." if lacunes else "")))
insights.story_grid(items)

# ---- filtres dédiés ------------------------------------------------------------------------------------------
export_df = pd.DataFrame()
H = 470
PAL = ["#016b4b", "#1488ee", "#fec902", "#8b3fe0", "#f20e36"]

# Toujours afficher les trois sections
show_ec = True
show_id = True
show_cmp = True

# ═══════════ ÉTAT CIVIL ═══════════
if show_ec:
    st.subheader("État civil")
    c_main, c_side = st.columns([2.0, 1.0], gap="small")
    nom = CODES[code]
    if sexe == "H / F":
        d = pd.concat([serie_ec(code, "Homme"), serie_ec(code, "Femme")])
    else:
        d = serie_ec(code, "Total")
    d["Série"] = d.sexe.map({"Total": "Total", "Homme": "Hommes", "Femme": "Femmes"})
    ok, ko = d[d.ok], d[~d.ok]
    with c_main:
        with panel("series_ec", f"{nom} · {p0}–{p1}", "fa-chart-line", height=H):
            if ok.empty and ko.empty:
                insights.empty_state()
            else:
                long = ok.rename(columns={"annee": "Année", "valeur_brute": "Valeur"})[["Année", "Valeur", "Série"]]
                long["Année"] = long.Année.astype(str)
                fl = ko.rename(columns={"annee": "Année", "valeur_brute": "Valeur"})[["Année", "Valeur", "Série", "motif"]]
                fl["Année"] = fl.Année.astype(str)
                fig = charts.create_series_chart(long if len(long) else pd.DataFrame({"Année": [str(p0)], "Valeur": [np.nan], "Série": ["Total"]}), "Année", "Valeur", "Série",
                                                 {"Total": "#016b4b", "Hommes": "#1488ee", "Femmes": "#8b3fe0"}, H - 90, flagged=fl if len(fl) else None, yfmt=fmt_int)
                charts.show(fig, "ec_series")
                insights.nd_note("Valeur écartée = croix rouge (jamais reliée par la courbe, jamais corrigée) ; ligne interrompue = valeur absente (N/D), pas un zéro. La série B de « enfants scolarisés sans acte » (sens non documenté) est hors analyse.")
    tab = variation(ok[ok["Série"] == ("Total" if sexe == "Total" else "Hommes")].rename(columns={"valeur_brute": "v"}), "v") if len(ok) else pd.DataFrame()
    with c_side:
        with panel("tab_ec", "Valeurs et variations annuelles", "fa-table", height=H):
            allv = d.pivot_table(index="annee", columns="Série", values="valeur_brute", aggfunc="first") if len(d) else pd.DataFrame()
            if allv.empty:
                insights.empty_state()
            else:
                t = allv.reset_index().rename(columns={"annee": "Année"})
                if sexe == "Total" and len(tab):
                    t = t.merge(tab[["annee", "var_pct"]].rename(columns={"annee": "Année", "var_pct": "Variation (%)"}), on="Année", how="left")
                flagged_years = set(ko.annee)
                t["Statut"] = t.Année.map(lambda y: ("écartée : " + ko[ko.annee == y].motif.iloc[0]) if y in flagged_years and len(ko[ko.annee == y]) else "")
                fm = {c: fmt_int for c in t.columns if c in ("Total", "Hommes", "Femmes")}
                fm["Variation (%)"] = lambda v: fmt_signe(v, 1)
                fm["Année"] = lambda v: str(int(v))
                st.markdown('<div class="list-scroll" style="max-height:340px">' + tables.create_table(t, formats=fm) + "</div>", unsafe_allow_html=True)
                insights.nd_note("Variation calculée seulement entre deux années consécutives toutes deux valides.")
                export_df = t
    ruptures = EC[(EC.indicateur_code == code) & (EC.serie == "A") & (EC.sexe == "Total") & EC.anomalie.notna() & EC.annee.between(p0, p1)]
    if len(ruptures):
        insights.story("attention", "Pour cet indicateur : " + "; ".join(f"<b>{int(r.annee)}</b> ({fmt_int(r.valeur_brute)}) : {MOTIF[r.anomalie]}" + (f" (×{fmt_dec(r.ratio_mediane_autres_annees, 2)} la médiane des autres années)" if r.ratio_mediane_autres_annees == r.ratio_mediane_autres_annees else "") for r in ruptures.itertuples()) + ".")

# ═══════════ IDENTITÉ ═══════════
if show_id:
    st.subheader("Identité")
    c_main, c_side = st.columns([2.0, 1.0], gap="small")
    types = types or ["cni", "passeports"]
    d = ID[ID.type.isin(types) & ID.annee.between(p0, p1)].copy()
    d["Document"] = d.type.map(ID_LAB)
    with c_main:
        with panel("series_id", f"Production de documents d'identité · {p0}–{p1}", "fa-chart-line", height=H):
            if d.empty:
                insights.empty_state()
            else:
                long = d.rename(columns={"annee": "Année", "valeur_brute": "Valeur"})[["Année", "Valeur", "Document"]]
                long["Année"] = long.Année.astype(str)
                # Graphique avec axe secondaire pour les passeports (échelles très différentes)
                import plotly.graph_objects as go
                fig = go.Figure()
                palette = {ID_LAB[t]: ID_COL[t] for t in types}
                for g in list(dict.fromkeys(long["Document"])):
                    sub = long[long["Document"] == g].sort_values("Année")
                    fig.add_trace(go.Scatter(x=sub["Année"], y=sub["Valeur"], name=g, mode="lines+markers",
                                             line=dict(color=palette[g], width=2.6),
                                             marker=dict(size=8, color=palette[g], line=dict(color="#fff", width=1.2)),
                                             hovertemplate="%{x}<br>" + g + " : <b>%{y:,.0f}</b><br><i>Documents produits</i><extra>" + g + "</extra>"))
                fig.update_layout(height=H - 90, margin=dict(l=4, r=8, t=34, b=40), paper_bgcolor="rgba(0,0,0,0)",
                                  plot_bgcolor="rgba(0,0,0,0)", font=dict(family="Nunito Sans, sans-serif", size=13, color="#0a4a9a"),
                                  showlegend=True, legend=dict(orientation="h", x=-0.02, y=1.2, xanchor="left", yanchor="top", font=dict(size=11.5), itemsizing="constant"))
                fig.update_xaxes(showgrid=False, tickfont=dict(size=11), tickangle=0)
                fig.update_yaxes(gridcolor="#e3edf0", zeroline=False, tickfont=dict(size=11.5), rangemode="tozero", tickformat="~s")
                for y in sorted(d[d.lacune_source & d.annee.between(p0, p1)].annee.unique()):
                    fig.add_annotation(x=str(y), y=1.0, yref="paper", yanchor="top", text=f"{y} : absent<br>de la source (N/D)", showarrow=False,
                                       font=dict(size=10.5, color="#c4102f"), bgcolor="rgba(255,255,255,0.85)", bordercolor="#c4102f", borderwidth=1, borderpad=3)
                charts.show(fig, "id_series_v3")
                insights.nd_note("Production annuelle (flux), pas une couverture de la population. Une année absente de la source reste vide : aucune valeur n'est estimée.")
    with c_side:
        with panel("tab_id", "Valeurs et variations annuelles", "fa-table", height=H):
            if d.empty:
                insights.empty_state()
            else:
                w = d.pivot_table(index="annee", columns="Document", values="valeur_brute", aggfunc="first", dropna=False).reset_index().rename(columns={"annee": "Année"})
                first = [c for c in w.columns if c != "Année"][0]
                v = variation(d[d.type == types[0]].rename(columns={"valeur_brute": "v"}), "v")
                w = w.merge(v[["annee", "var_pct"]].rename(columns={"annee": "Année", "var_pct": f"Var. {ID_LAB[types[0]][:12]} (%)"}), on="Année", how="left")
                fm = {c: fmt_int for c in w.columns if c in ID_LAB.values()}
                fm["Année"] = lambda x: str(int(x))
                fm[f"Var. {ID_LAB[types[0]][:12]} (%)"] = lambda x: fmt_signe(x, 1)
                st.markdown('<div class="list-scroll" style="max-height:340px">' + tables.create_table(w, formats=fm) + "</div>", unsafe_allow_html=True)
                insights.nd_note("N/D : valeur absente de la source. Variation seulement entre années consécutives disponibles.")
                export_df = w

# ═══════════ COMPARAISON ═══════════
if show_cmp:
    c_main, c_side = st.columns([2.0, 1.0], gap="small")
    b_ = serie_ec(PRINCIPAL)
    b_ = b_[b_.ok].set_index("annee").valeur_brute
    cni_s = ID[(ID.type == "cni") & ID.valeur_brute.notna()].set_index("annee").valeur_brute
    pas_s = ID[(ID.type == "passeports") & ID.valeur_brute.notna()].set_index("annee").valeur_brute
    years = sorted(set(b_.index) & set(cni_s.index) & set(pas_s.index))
    years = [y for y in years if p0 <= y <= p1]
    with c_main:
        with panel("series_cmp", f"Naissances enregistrées, CNI et passeports · indice base 100 ({years[0] if years else '—'})", "fa-chart-line", height=H):
            if len(years) < 2:
                insights.empty_state("Moins de deux années communes aux trois séries sur la période choisie : comparaison impossible.")
            else:
                base = years[0]
                idx = pd.DataFrame([dict(Année=str(y), Série=nm, Indice=s[y] / s[base] * 100, Valeur=s[y]) for nm, s in (("Naissances (45 jours)", b_), ("CNI", cni_s), ("Passeports", pas_s)) for y in years])
                fig = charts.create_series_chart(idx[["Année", "Indice", "Série"]], "Année", "Indice", "Série",
                                                 {"Naissances (45 jours)": "#016b4b", "CNI": "#fec902", "Passeports": "#1488ee"}, H - 90, yfmt=lambda v: fmt_dec(v, 0))
                charts.show(fig, "cmp_series")
                insights.nd_note(f"Indice : valeur de l'année ÷ valeur de {base} × 100, sur les années où les trois séries sont disponibles et valides ({years[0]}–{years[-1]}). Ces séries ont des natures différentes (enregistrements d'une part, production de documents d'autre part) : l'indice compare des dynamiques, pas des niveaux.")
                export_df = idx
    with c_side:
        with panel("tab", "Valeurs comparées", "fa-table", height=H):
            if len(years) < 2:
                insights.empty_state()
            else:
                t = pd.DataFrame({"Année": years, "Naissances (45 j)": [b_[y] for y in years], "CNI": [cni_s[y] for y in years], "Passeports": [pas_s[y] for y in years]})
                st.markdown('<div class="list-scroll" style="max-height:340px">' + tables.create_table(t, formats={"Année": lambda x: str(int(x)), "Naissances (45 j)": fmt_int, "CNI": fmt_int, "Passeports": fmt_int}) + "</div>", unsafe_allow_html=True)
                insights.nd_note("Années retenues : celles où la série des naissances est valide (2015 des autres séries d'état civil écartées) et où la CNI et les passeports sont disponibles.")
                export_df = t

if len(export_df) and mode:
    st.download_button("Exporter", Q.csv_bytes(export_df), "etat_civil_identite.csv", "text/csv", key="dl_btn", help="Exporter les données affichées (CSV, période active incluse)", width="stretch")
insights.story_grid([
    ("implication", "Sans dimension territoriale, l'état civil ne permet pas de dire <b>où</b> agir : il ne permet que de suivre l'évolution du <b>système</b> d'enregistrement et de production de documents."),
    ("recommandation", "Territorialiser la collecte (enregistrements par préfecture et dénominateur de naissances attendues) pour pouvoir cibler les territoires les moins couverts ; combler les années absentes de la source (2021) et fiabiliser les séries écartées."),
])
flush_panel_css()
