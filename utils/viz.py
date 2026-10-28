"""Fonctions de visualisation `plot_*` : chacune retourne une figure Plotly (titre-message, unité, période, source, statut)."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from .theme import (PRIMAIRE, SECONDAIRE, ACCENT, TEXTE, TEXTE_2, FLAG_COULEUR, GRILLE, mise_en_forme, fmt_int, fmt_dec, fmt_pct)
from .demography import gini, courbe_lorenz

FEMININ = {"communes", "préfectures", "régions"}
SRC_RGPH = "RGPH-5 2022 (observationdata-kwwolwb.csv)"
SRC_RGPH_2 = "RGPH-4 2010 et RGPH-5 2022 (observationdata-sapxctg.csv, -kwwolwb.csv)"


def _hauteur(n: int, base: int = 380, pas: int = 24) -> int:
    return max(base, 170 + n * pas)


def plot_classement(df: pd.DataFrame, niveau: str, top_n: int = 15, surbrillance=None, id_col: str = "territoire_id", nom_col: str = "nom",
                    val_col: str = "population_2022") -> go.Figure:
    """Barres horizontales triées : les `top_n` territoires les plus peuplés (valeurs affichées ; surbrillance en accent)."""
    d = df.sort_values(val_col, ascending=False)
    total = d[val_col].sum()
    top = d.head(top_n)
    part = top[val_col].sum() / total * 100 if total else np.nan
    ids = set(surbrillance or [])
    couleurs = [ACCENT if i in ids else PRIMAIRE for i in top[id_col]]
    fig = go.Figure(go.Bar(
        x=top[val_col], y=top[nom_col], orientation="h", marker=dict(color=couleurs, line=dict(color=[TEXTE if i in ids else "rgba(0,0,0,0)" for i in top[id_col]], width=1.5)),
        text=[fmt_int(v) for v in top[val_col]], textposition="outside", cliponaxis=False, customdata=top[[id_col]].values,
        hovertemplate="<b>%{y}</b><br>Population : %{x:,.0f} hab.<extra></extra>"))
    fig.update_yaxes(autorange="reversed", title=None)
    fig.update_xaxes(title="Habitants (RGPH 2022)", range=[0, top[val_col].max() * 1.18])
    n = len(top)
    f = niveau.split()[0] in FEMININ
    adj, aff = ("peuplées", "affichées") if f else ("peuplés", "affichés")
    titre = f"Les {n} {niveau} les plus {adj} regroupent {fmt_pct(part)} de la population affichée" if len(d) > n else f"Population des {len(d)} {niveau} {aff}"
    return mise_en_forme(fig, titre, f"Population 2022, en habitants — {len(d)} {niveau} dans la sélection", SRC_RGPH, "OBSERVATION", hauteur=_hauteur(n))


def plot_lorenz(valeurs, niveau: str) -> go.Figure:
    """Courbe de Lorenz et Gini de la répartition de la population entre territoires d'un même niveau."""
    v = pd.Series(valeurs).dropna()
    L = courbe_lorenz(v)
    g = gini(v)
    # part de la population détenue par les 10 % de territoires les plus peuplés
    x90 = np.interp(0.9, L.part_territoires, L.part_population)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines", name="Égalité parfaite", line=dict(color=TEXTE_2, dash="dash", width=1.5)))
    fig.add_trace(go.Scatter(x=L.part_territoires, y=L.part_population, mode="lines", name=f"Répartition observée (Gini = {fmt_dec(g, 2)})",
                             line=dict(color=PRIMAIRE, width=3), fill="tonexty", fillcolor="rgba(11,60,93,0.10)",
                             hovertemplate="%{x:.0%} des territoires les moins peuplés → %{y:.0%} de la population<extra></extra>"))
    fig.update_xaxes(title=f"Part cumulée des {niveau} (du moins au plus peuplé)", tickformat=".0%", range=[0, 1])
    fig.update_yaxes(title="Part cumulée de la population", tickformat=".0%", range=[0, 1])
    fig.add_annotation(x=0.5, y=0.12, text=f"Les 10 % les plus peuplés détiennent {fmt_pct((1 - x90) * 100, 0)}", showarrow=False, font=dict(size=12, color=PRIMAIRE), bgcolor="#FFFFFF")
    return mise_en_forme(fig, f"Gini de {fmt_dec(g, 2)} : la population est inégalement répartie entre {niveau}", f"Courbe de Lorenz, population 2022 — {len(v)} {niveau}",
                         SRC_RGPH, "CALCUL")


def plot_boxplot_tailles(groupes: dict, surbrillance=None) -> go.Figure:
    """Boîtes à moustaches (échelle logarithmique) des tailles de communes, cantons et quartiers ; points sélectionnés en accent."""
    ids = set(surbrillance or [])
    fig = go.Figure()
    couleurs = {"Communes": SECONDAIRE, "Cantons": PRIMAIRE, "Quartiers du Grand Lomé": TEXTE_2}
    meds = {}
    for nom, d in groupes.items():
        if d is None or len(d) == 0:
            continue
        meds[nom] = (d.population_2022.median(), d.population_2022.min(), d.population_2022.max(), len(d))
        fig.add_trace(go.Box(y=d.population_2022, name=f"{nom} (n = {len(d)})", boxpoints="outliers", marker=dict(color=couleurs.get(nom, PRIMAIRE), size=4),
                             line=dict(color=couleurs.get(nom, PRIMAIRE)), text=d.nom, hovertemplate="%{text}<br>%{y:,.0f} hab.<extra></extra>"))
        sel = d[d.territoire_id.isin(ids)]
        if len(sel):
            fig.add_trace(go.Scatter(x=[f"{nom} (n = {len(d)})"] * len(sel), y=sel.population_2022, mode="markers+text", text=sel.nom, textposition="middle right",
                                     marker=dict(color=ACCENT, size=11, symbol="diamond", line=dict(color=TEXTE, width=1.5)), name="Sélection", showlegend=False,
                                     hovertemplate="%{text}<br>%{y:,.0f} hab.<extra></extra>"))
    fig.update_yaxes(type="log", title="Habitants (échelle logarithmique)")
    fig.update_layout(showlegend=False)
    if meds:
        k = "Cantons" if "Cantons" in meds else next(iter(meds))
        m, lo, hi, n = meds[k]
        titre = f"Un {k.lower().rstrip('s')} médian compte {fmt_int(m)} habitants, mais les tailles vont de {fmt_int(lo)} à {fmt_int(hi)}"
    else:
        titre = "Tailles des territoires"
    return mise_en_forme(fig, titre, "Distribution des populations 2022 par niveau (médiane, quartiles, valeurs extrêmes)", SRC_RGPH, "OBSERVATION",
                         note="Échelle logarithmique : chaque graduation multiplie la taille par 10.")


def plot_tcam(df: pd.DataFrame, tcam_national: float, top_n: int = 40, plus_lentes: bool = False) -> go.Figure:
    """TCAM 2010–2022 par unité de comparaison ; le niveau de fiabilité (flag) figure dans l'étiquette ET dans la couleur."""
    d = df.sort_values("tcam_pct", ascending=plus_lentes).head(top_n)
    etiq = [f"{n} · {f}" for n, f in zip(d.nom, d.comparability_flag)]
    fig = go.Figure(go.Bar(
        x=d.tcam_pct, y=etiq, orientation="h", marker=dict(color=[FLAG_COULEUR[f] for f in d.comparability_flag], line=dict(color=[TEXTE if f == "MEDIUM" else "rgba(0,0,0,0)" for f in d.comparability_flag], width=1)),
        text=[fmt_pct(v, 1) for v in d.tcam_pct], textposition="outside", cliponaxis=False,
        customdata=np.stack([d.pop_2010, d.pop_2022, d.comparability_flag], axis=-1),
        hovertemplate="<b>%{y}</b><br>TCAM : %{x:.2f} %/an<br>2010 : %{customdata[0]:,.0f} hab.<br>2022 : %{customdata[1]:,.0f} hab.<extra></extra>"))
    fig.add_vline(x=tcam_national, line=dict(color=TEXTE, dash="dash", width=1.5), annotation_text=f"Togo : {fmt_pct(tcam_national, 1)}/an", annotation_position="top",
                  annotation_font=dict(size=11, color=TEXTE))
    fig.update_yaxes(autorange="reversed", title=None)
    fig.update_xaxes(title="Taux de croissance annuel moyen, en % par an", range=[min(0, d.tcam_pct.min() * 1.2), d.tcam_pct.max() * 1.18])
    n_sup = int((d.tcam_pct > tcam_national).sum())
    top = d.iloc[0]
    titre = (f"{top.nom} croît le moins vite ({fmt_pct(top.tcam_pct, 1)}/an) ; {len(d) - n_sup} des {len(d)} unités affichées restent sous le rythme national" if plus_lentes
             else f"{top.nom} croît le plus vite ({fmt_pct(top.tcam_pct, 1)}/an) ; {n_sup} unités sur {len(d)} dépassent le rythme national")
    return mise_en_forme(fig, titre, "TCAM 2010–2022 sur 12 ans, par unité de comparaison (HIGH = fiable, MEDIUM = prudence)", SRC_RGPH_2, "CALCUL",
                         note="Seuls les territoires HIGH/MEDIUM sont classés ; les LOW sont présentés à part.", hauteur=_hauteur(len(d), pas=22))


def plot_contributions(df: pd.DataFrame, surbrillance=None, top_n: int = 15) -> go.Figure:
    """Contribution de chaque unité à la croissance de la population nationale (en % de l'accroissement total 2010–2022)."""
    d = df.sort_values("contribution_croissance_pct", ascending=False)
    top = d.head(top_n)
    ids = set(surbrillance or [])
    fig = go.Figure(go.Bar(x=top.contribution_croissance_pct, y=top.nom, orientation="h",
                           marker=dict(color=[ACCENT if n in ids else SECONDAIRE for n in top.nom], line=dict(color=[TEXTE if n in ids else "rgba(0,0,0,0)" for n in top.nom], width=1.5)),
                           text=[fmt_pct(v, 1) for v in top.contribution_croissance_pct], textposition="outside", cliponaxis=False,
                           hovertemplate="<b>%{y}</b><br>%{x:.1f} % de l'accroissement national<extra></extra>"))
    fig.update_yaxes(autorange="reversed", title=None)
    fig.update_xaxes(title="Part de l'accroissement national 2010–2022 (%)", range=[0, top.contribution_croissance_pct.max() * 1.2])
    lead = top.iloc[0]
    part_pop = lead.pop_2022 / d.pop_2022.sum() * 100
    titre = f"{lead.nom} explique {fmt_pct(lead.contribution_croissance_pct, 0)} de la croissance nationale, pour {fmt_pct(part_pop, 0)} de la population"
    return mise_en_forme(fig, titre, "Contribution à l'accroissement de 1,90 million d'habitants (2010–2022)" if len(d) > 30 else "Contribution à l'accroissement 2010–2022",
                         SRC_RGPH_2, "CALCUL", hauteur=_hauteur(len(top)))


def plot_regions_evolution(df: pd.DataFrame, decoupage: str) -> go.Figure:
    """Dot plot 2010 → 2022 par région (à périmètre constant) avec le TCAM en étiquette."""
    d = df.sort_values("pop_2022", ascending=True)
    fig = go.Figure()
    for _, r in d.iterrows():
        fig.add_trace(go.Scatter(x=[r.pop_2010, r.pop_2022], y=[r.nom, r.nom], mode="lines", line=dict(color=GRILLE, width=4), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=d.pop_2010, y=d.nom, mode="markers", name="2010", marker=dict(color="#FFFFFF", size=12, line=dict(color=PRIMAIRE, width=2.5)),
                             hovertemplate="%{y}<br>2010 : %{x:,.0f} hab.<extra></extra>"))
    fig.add_trace(go.Scatter(x=d.pop_2022, y=d.nom, mode="markers+text", name="2022", marker=dict(color=PRIMAIRE, size=12),
                             text=[f"{fmt_pct(t, 1)}/an" for t in d.tcam_pct], textposition="middle right", textfont=dict(size=12, color=TEXTE),
                             hovertemplate="%{y}<br>2022 : %{x:,.0f} hab.<extra></extra>"))
    fig.update_xaxes(title="Habitants", range=[0, d.pop_2022.max() * 1.25])
    fig.update_yaxes(title=None)
    top = d.sort_values("tcam_pct", ascending=False).iloc[0]
    titre = f"Toutes les régions gagnent des habitants ; {top.nom} croît le plus vite ({fmt_pct(top.tcam_pct, 1)}/an)"
    return mise_en_forme(fig, titre, f"Population 2010 (cercle vide) et 2022 (cercle plein), {decoupage}, à périmètre constant", SRC_RGPH_2, "CALCUL",
                         hauteur=max(380, 150 + len(d) * 55))
