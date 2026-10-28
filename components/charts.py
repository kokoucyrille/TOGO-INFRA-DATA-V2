"""Graphiques Plotly aux couleurs des maquettes + blocs HTML (barres Top 5, anneaux de qualité)."""
from __future__ import annotations

import math

import numpy as np

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components.styles import FONT, THEME
from utils.formats import fmt_dec, fmt_int

GRID = "#e3edf0"
AXIS_TXT = "#0a4a9a"
LINE_COLORS = [THEME["green"], "#ffc903", "#f20e36", "#a24df0"]


def show(fig: go.Figure, key: str) -> None:
    """Affiche une figure sans barre d'outils, à la largeur du conteneur."""
    st.plotly_chart(fig, width="stretch", key=key,
                    config={"displayModeBar": False, "responsive": True})


def _layout(fig: go.Figure, height: int, **kw) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=4, r=8, t=kw.pop("t", 8), b=kw.pop("b", 4)), paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", font=dict(family=FONT, size=13, color=AXIS_TXT), showlegend=False, **kw)
    return fig


def nice_ticks(vmax: float, n: int = 4) -> list[float]:
    """Graduations « rondes » (0, 2,5k, 5k, …) jusqu'à couvrir `vmax`."""
    if vmax <= 0:
        return [0, 1]
    raw = vmax / n
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    top = math.ceil(vmax / step) * step
    return [round(i * step, 6) for i in range(int(round(top / step)) + 1)]


def compact(v: float) -> str:
    """2500 -> '2,5k' ; 800000 -> '800K' ; 1000000 -> '1M' (graduations d'axes)."""
    if abs(v) >= 1_000_000:
        return f"{fmt_dec(v / 1_000_000, 1).rstrip('0').rstrip(',')}M"
    if abs(v) >= 1000:
        return f"{fmt_dec(v / 1000, 1).rstrip('0').rstrip(',')}k"
    return fmt_dec(v, 1).rstrip("0").rstrip(",") if v % 1 else str(int(v))


# --------------------------------------------------------------------------------------
def create_bar_chart(df: pd.DataFrame, x: str, y: str, colors: list[str], height: int = 215,
                     fmt=compact, hover_unit: str = "") -> go.Figure:
    """Barres verticales (une couleur par barre, comme sur la maquette)."""
    ticks = nice_ticks(float(df[y].max()))
    fig = go.Figure(go.Bar(x=df[x], y=df[y], marker_color=colors[: len(df)], width=0.42,
                           hovertemplate="%{x}<br><b>%{customdata}</b>" + hover_unit + "<br><i>Valeur observée</i><extra></extra>",
                           customdata=[fmt_int(v) for v in df[y]]))
    _layout(fig, height, b=2)
    fig.update_yaxes(tickvals=ticks, ticktext=[fmt(t) for t in ticks], gridcolor=GRID, zeroline=False,
                     tickfont=dict(size=12), range=[0, ticks[-1]])
    fig.update_xaxes(showgrid=False, tickfont=dict(size=13.5))
    return fig


def create_donut_chart(labels: list[str], values: list[float], colors: list[str], center_top: str,
                       center_bottom: str, height: int = 190) -> go.Figure:
    """Donut avec valeur + libellé au centre (la légende est rendue en HTML à côté)."""
    fig = go.Figure(go.Pie(labels=labels, values=values, hole=0.62, sort=False, direction="clockwise",
                           marker=dict(colors=colors, line=dict(color="#fff", width=2)), textinfo="none", rotation=0,
                           hovertemplate="%{label}<br><b>%{value:,.0f}</b> (%{percent})<extra></extra>"))
    _layout(fig, height, t=2, b=2)
    fig.update_layout(margin=dict(l=2, r=2, t=2, b=2), annotations=[
        dict(text=f"<b>{center_top}</b>", x=0.5, y=0.56, showarrow=False, font=dict(size=24 if len(center_top) <= 6 else 19, color="#0a4a9a")),
        dict(text=f"<b>{center_bottom}</b>", x=0.5, y=0.40, showarrow=False, font=dict(size=13.5, color="#0a4a9a"))])
    return fig


def create_line_chart(df: pd.DataFrame, x: str, y: str, group: str, colors: dict | list, height: int = 190,
                      yfmt=compact, yrange: tuple | None = None, ypct: bool = False) -> go.Figure:
    """Courbes multi-séries avec marqueurs ronds et légende horizontale en haut."""
    fig = go.Figure()
    groups = list(dict.fromkeys(df[group]))
    palette = colors if isinstance(colors, dict) else dict(zip(groups, colors))
    for g in groups:
        d = df[df[group] == g]
        fig.add_trace(go.Scatter(
            x=d[x], y=d[y], name=g, mode="lines+markers", line=dict(color=palette[g], width=2.4),
            marker=dict(size=7, color=palette[g], line=dict(color="#fff", width=1)),
            hovertemplate="%{x}<br>" + g + " : <b>%{y:,.0f}</b><br><i>Série temporelle</i><extra>" + g + "</extra>"))
    if ypct:
        ticks = [0, 25, 50, 75, 100]
        tt = [f"{t}%" for t in ticks]
    else:
        ticks = nice_ticks(float(df[y].max()), 4)
        tt = [yfmt(t) for t in ticks]
    _layout(fig, height, t=34, b=2)
    fig.update_layout(showlegend=True, legend=dict(orientation="h", x=-0.02, y=1.22, xanchor="left", yanchor="top", itemwidth=30,
                                                   font=dict(size=11), itemsizing="constant", tracegroupgap=0))
    fig.update_yaxes(tickvals=ticks, ticktext=tt, gridcolor=GRID, zeroline=False, tickfont=dict(size=12),
                     range=yrange or [0, ticks[-1] * 1.0])
    fig.update_xaxes(showgrid=False, tickfont=dict(size=9.5 if len(df[x].unique()) > 7 else 12), type="category", tickangle=0)
    return fig


# --------------------------------------------------------------------------------------
# Blocs HTML
# --------------------------------------------------------------------------------------
def create_top5(df: pd.DataFrame, colors: list[str] | None = None, unit: str = "") -> str:
    """Barres horizontales « Top 5 » (piste grise + remplissage + valeur à droite)."""
    if df.empty:
        return '<div style="color:#7b8794;padding:20px 0">Aucune localité pour cette sélection.</div>'
    vmax = float(df["Valeur"].max()) or 1.0
    colors = colors or [THEME["green"], "#45b08c", "#4fbf9f", "#58c9aa", "#62d1b3"]
    rows = []
    for i, r in df.reset_index(drop=True).iterrows():
        pct = max(r["Valeur"] / vmax * 100, 3)
        rows.append(f'<div class="row"><span>{r["Localité"]}</span><div class="track"><div class="fill" '
                    f'style="width:{pct:.1f}%;background:{colors[i % len(colors)]}"></div></div>'
                    f'<span class="val">{fmt_int(r["Valeur"])}{unit}</span></div>')
    return f'<div class="top5">{"".join(rows)}</div>'


def create_ring(value_text: str, pct: float, color: str) -> str:
    """Anneau de progression (conic-gradient) avec la valeur au centre."""
    pct = max(0, min(pct, 100))
    return (f'<div class="ring" style="background:conic-gradient({color} {pct * 3.6:.0f}deg,#e8eff1 0)">'
            f'<span style="color:{color}">{value_text}</span></div>')


def fmt_pct_int(p: float, nd: int = 1) -> str:
    return f"{fmt_dec(p, nd)}%"


# --------------------------------------------------------------------------------------
# Graphiques du dashboard Défi 2 (même style que le template : fond transparent, axes bleus, séries vertes)
# --------------------------------------------------------------------------------------
SEL_COLOR = THEME["gold"]
RED_TXT = "#c4102f"        # rouge foncé pour le TEXTE (le rouge du gabarit n'atteint que 4,29 : 1 sur blanc)
SUB_TXT = "#4f6270"        # gris-bleu foncé pour les petits libellés (le gris du gabarit n'atteint que 2,05 : 1)
MUTED = "#c9d6dd"


def show_select(fig: go.Figure, key: str) -> list:
    """Affiche une figure cliquable (filtrage croisé) ; retourne les identifiants (`customdata[0]`) sélectionnés."""
    ev = st.plotly_chart(fig, width="stretch", key=key, config={"displayModeBar": False, "responsive": True},
                         on_select="rerun", selection_mode=("points", "box"))
    pts = (ev.selection.points if ev is not None and getattr(ev, "selection", None) else []) or []
    ids = []
    for p in pts:
        cd = p.get("customdata")
        if isinstance(cd, dict):                                    # Streamlit renvoie customdata sous forme {'0': valeur}
            cd = cd.get("0", next(iter(cd.values()), None))
        if cd not in (None, [], ()):
            ids.append(cd[0] if isinstance(cd, (list, tuple)) else cd)
    return ids


def create_rank_bar(df: pd.DataFrame, label: str, value: str, ids: str, fmt=fmt_int, colors=None, selected=None, height: int = 300,
                    ref: float | None = None, ref_label: str = "", xtitle: str = "") -> go.Figure:
    """Classement : barres horizontales triées (la plus grande en haut), valeur au bout de la barre, surbrillance de la sélection.
    `ids` : colonne d'identifiants renvoyée par la sélection ; `ref` : ligne de référence (ex. moyenne nationale)."""
    d = df.reset_index(drop=True)
    sel = set(selected or [])
    cols = list(colors) if colors is not None else [THEME["green"]] * len(d)
    cols = [SEL_COLOR if d[ids][i] in sel else cols[i] for i in range(len(d))] if sel else cols
    fig = go.Figure(go.Bar(
        x=d[value], y=d[label], orientation="h", marker=dict(color=cols, line=dict(color=[THEME["blue"] if d[ids][i] in sel else ("#8a6a00" if str(cols[i]).lower() in ("#fec902", "#fdcf00") else "rgba(0,0,0,0)") for i in range(len(d))], width=1.6)),
        text=[fmt(v) for v in d[value]], textposition="outside", cliponaxis=False, textfont=dict(size=12, color=AXIS_TXT),
        customdata=d[[ids]].values, hovertemplate="<b>%{y}</b><br>" + (xtitle or "Valeur") + " : <b>%{text}</b><br><i>Rang : %{x}</i><extra></extra>"))
    _layout(fig, height, t=6, b=22)
    fig.update_yaxes(autorange="reversed", showgrid=False, tickfont=dict(size=12.5), automargin=True)
    vmax = float(d[value].max()) if len(d) else 1.0
    fig.update_xaxes(showgrid=True, gridcolor=GRID, zeroline=False, tickfont=dict(size=11.5), range=[min(0, float(d[value].min()) * 1.1) if len(d) else 0, max(vmax, ref or 0) * 1.22],
                     tickformat="~s" if vmax > 5000 else None, title=dict(text=xtitle, font=dict(size=12)))
    if ref is not None:
        fig.add_vline(x=ref, line=dict(color=THEME["red"], dash="dash", width=1.5), annotation_text=ref_label, annotation_position="top",
                      annotation_font=dict(size=11.5, color=RED_TXT))
    return fig


def create_scatter_quadrant(df: pd.DataFrame, x: str, y: str, size: str, color: str, name: str, hover: list[str], x_ref: float, y_ref: float,
                            xtitle: str, ytitle: str, height: int = 380, log_x: bool = True, selected=None) -> go.Figure:
    """Nuage de bulles avec quadrants (médianes) : x = population, y = taux d'accès, taille = population, couleur = densité de services."""
    d = df.reset_index(drop=True)
    sel = set(selected or [])
    smax = float(d[size].max()) or 1.0
    fig = go.Figure(go.Scatter(
        x=d[x], y=d[y], mode="markers", name="", customdata=d[[name] + hover].values,
        marker=dict(size=[10 + 34 * (v / smax) ** 0.5 for v in d[size]], color=d[color], colorscale=[[0, "#f20e36"], [0.5, "#fec902"], [1, "#016b4b"]],
                    cmin=float(d[color].min()), cmax=float(d[color].max()), colorbar=dict(title=dict(text="Agences / 100 000 hab.", font=dict(size=11)), thickness=11, len=0.78, tickfont=dict(size=11)),
                    line=dict(color=[THEME["blue"] if n in sel else "#ffffff" for n in d[name]], width=[3 if n in sel else 1 for n in d[name]]), opacity=0.9),
        hovertemplate="<b>%{customdata[0]}</b><br>" + "<br>".join(f"{h} : %{{customdata[{i + 1}]}}" for i, h in enumerate(hover)) + "<br><i>Cliquez pour sélectionner</i><extra></extra>"))
    _layout(fig, height, t=14, b=44)
    fig.update_xaxes(type="log" if log_x else "linear", title=dict(text=xtitle, font=dict(size=12)), gridcolor=GRID, zeroline=False, tickfont=dict(size=11.5))
    fig.update_yaxes(title=dict(text=ytitle, font=dict(size=12)), gridcolor=GRID, zeroline=False, tickfont=dict(size=11.5), range=[-2, 104])
    fig.add_vline(x=x_ref, line=dict(color=THEME["gray"], dash="dot", width=1.3))
    fig.add_hline(y=y_ref, line=dict(color=THEME["gray"], dash="dot", width=1.3))
    for t, (ax, ay, xa, ya) in {"Forte population · accès faible": (0.99, 0.02, "right", "bottom"), "Faible population · accès faible": (0.01, 0.02, "left", "bottom"),
                                "Forte population · accès élevé": (0.99, 0.98, "right", "top"), "Faible population · accès élevé": (0.01, 0.98, "left", "top")}.items():
        fig.add_annotation(text=t, xref="paper", yref="paper", x=ax, y=ay, xanchor=xa, yanchor=ya, showarrow=False, font=dict(size=11, color=SUB_TXT))
    return fig


def create_lorenz(values, height: int = 250) -> go.Figure:
    """Courbe de Lorenz (population cumulée selon le rang de taille) avec la diagonale d'égalité."""
    v = np.sort(np.asarray(pd.Series(values).dropna(), dtype=float))
    cum = np.concatenate([[0.0], np.cumsum(v) / v.sum()])
    x = np.linspace(0, 1, len(cum))
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines", line=dict(color=THEME["gray"], dash="dash", width=1.5), hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=x, y=cum, mode="lines", line=dict(color=THEME["green"], width=3), fill="tonexty", fillcolor="rgba(1,107,75,0.12)", showlegend=False,
                             hovertemplate="%{x:.0%} des territoires les moins peuplés<br>= %{y:.0%} de la population<extra></extra>"))
    _layout(fig, height, t=6, b=34)
    fig.update_xaxes(title=dict(text="Part cumulée des territoires (du moins au plus peuplé)", font=dict(size=11.5)), tickformat=".0%", gridcolor=GRID, zeroline=False, range=[0, 1], tickfont=dict(size=11.5))
    fig.update_yaxes(title=dict(text="Part cumulée de la population", font=dict(size=11.5)), tickformat=".0%", gridcolor=GRID, zeroline=False, range=[0, 1], tickfont=dict(size=11.5))
    return fig


def create_size_histogram(values, selected_values=None, height: int = 250, nbins: int = 14) -> go.Figure:
    """Distribution des tailles (échelle logarithmique) : effectif par classe de population."""
    v = pd.Series(values).dropna()
    v = v[v > 0]
    edges = np.logspace(np.log10(v.min()), np.log10(v.max() * 1.0001), nbins + 1)
    cnt, _ = np.histogram(v, bins=edges)
    mid = np.sqrt(edges[:-1] * edges[1:])
    fig = go.Figure(go.Bar(x=mid, y=cnt, width=np.diff(edges) * 0.9, marker_color=THEME["green"], text=[str(c) if c else "" for c in cnt], textposition="outside",
                           customdata=np.stack([edges[:-1], edges[1:]], axis=-1), cliponaxis=False,
                           hovertemplate="De %{customdata[0]:,.0f} à %{customdata[1]:,.0f} hab.<br><b>%{y}</b> territoires<br><i>Distribution des tailles</i><extra></extra>"))
    _layout(fig, height, t=14, b=34)
    fig.update_xaxes(type="log", title=dict(text="Population (échelle logarithmique)", font=dict(size=11.5)), gridcolor=GRID, zeroline=False, tickfont=dict(size=11.5))
    fig.update_yaxes(title=dict(text="Nombre de territoires", font=dict(size=11.5)), gridcolor=GRID, zeroline=False, tickfont=dict(size=11.5), rangemode="tozero")
    if v.size:
        fig.add_vline(x=float(v.median()), line=dict(color=THEME["red"], dash="dash", width=1.5), annotation_text=f"Médiane : {fmt_int(v.median())}",
                      annotation_position="top", annotation_font=dict(size=11.5, color=RED_TXT))
    return fig


def create_series_chart(df: pd.DataFrame, x: str, y: str, group: str, colors: dict | list, height: int = 270, flagged: pd.DataFrame | None = None,
                        labels: bool = True, yfmt=compact, log_y: bool = False) -> go.Figure:
    """Séries temporelles : lignes + marqueurs, valeurs affichées sur les points ; les points écartés (`flagged`: colonnes x, y, group, motif)
    sont montrés en croix creuse (jamais reliés, jamais inventés) ; une valeur manquante interrompt la ligne."""
    fig = go.Figure()
    groups = list(dict.fromkeys(df[group]))
    palette = colors if isinstance(colors, dict) else dict(zip(groups, colors))
    for g in groups:
        d = df[df[group] == g].sort_values(x)
        fig.add_trace(go.Scatter(x=d[x], y=d[y], name=g, mode="lines+markers" + ("+text" if labels else ""), connectgaps=False,
                                 line=dict(color=palette[g], width=2.6), marker=dict(size=8, color=palette[g], line=dict(color="#fff", width=1.2)),
                                 text=[yfmt(v) if v == v else "" for v in d[y]], textposition="top center", textfont=dict(size=11, color=palette[g]),
                                 hovertemplate="%{x}<br>" + g + " : <b>%{y:,.0f}</b><br><i>Série temporelle</i><extra>" + g + "</extra>"))
    if flagged is not None and len(flagged):
        fig.add_trace(go.Scatter(x=flagged[x], y=flagged[y], mode="markers", name="Valeur écartée (anomalie)", marker=dict(symbol="x-open", size=12, color=THEME["red"], line=dict(width=2.2)),
                                 customdata=flagged[["motif"]].values, hovertemplate="%{x}<br><b>%{y:,.0f}</b> — écartée : %{customdata[0]}<extra></extra>"))
    _layout(fig, height, t=34, b=4)
    fig.update_layout(showlegend=True, legend=dict(orientation="h", x=-0.02, y=1.2, xanchor="left", yanchor="top", font=dict(size=11.5), itemsizing="constant"))
    fig.update_xaxes(showgrid=False, type="category", tickfont=dict(size=12))
    fig.update_yaxes(gridcolor=GRID, zeroline=False, tickfont=dict(size=11.5), type="log" if log_y else "linear", rangemode="tozero" if not log_y else "normal")
    return fig


def create_population_comparison_chart(df: pd.DataFrame, height: int = 360, log_x: bool = False) -> go.Figure:
    """Compare deux recensements par territoire avec des segments et une légende limitée aux deux années."""
    data = df.sort_values("pop_2022", ascending=False).copy()
    labels = data["nom"].astype(str).tolist()
    fig = go.Figure()
    for row in data.itertuples(index=False):
        fig.add_trace(go.Scatter(
            x=[row.pop_2010, row.pop_2022],
            y=[str(row.nom), str(row.nom)],
            mode="lines",
            line=dict(color="#c5d5dc", width=2),
            hoverinfo="skip",
            showlegend=False,
        ))

    for year, column, color in (
        ("2010", "pop_2010", "#1488ee"),
        ("2022", "pop_2022", THEME["green"]),
    ):
        values = data[column].astype(float).tolist()
        fig.add_trace(go.Scatter(
            x=values,
            y=labels,
            name=year,
            mode="markers",
            marker=dict(size=10, color=color, line=dict(color="#fff", width=1.5)),
            customdata=[[name, fmt_int(value)] for name, value in zip(labels, values)],
            hovertemplate="<b>%{customdata[0]}</b><br>" + year + " : %{customdata[1]} habitants<br><i>Comparaison 2010-2022</i><extra></extra>",
        ))

    _layout(fig, height, t=38, b=34)
    fig.update_layout(
        showlegend=True,
        legend=dict(orientation="h", x=0.5, xanchor="center", y=1.16, yanchor="top", font=dict(size=12)),
    )
    population_values = data[["pop_2010", "pop_2022"]].to_numpy(dtype=float)
    min_population, max_population = population_values.min(), population_values.max()
    log_x = log_x and min_population > 0
    log_ticks = sorted(
        multiplier * 10 ** exponent
        for exponent in range(math.floor(math.log10(min_population)), math.ceil(math.log10(max_population)) + 1)
        for multiplier in (1, 2, 5)
        if min_population / 1.25 <= multiplier * 10 ** exponent <= max_population * 1.25
    ) if log_x else []
    fig.update_xaxes(
        type="log" if log_x else "linear",
        title=dict(text="Population (habitants)" + (" · échelle logarithmique" if log_x else ""), font=dict(size=11.5)),
        gridcolor=GRID,
        zeroline=False,
        tickfont=dict(size=11.5),
        tickformat="~s" if not log_ticks else None,
        tickmode="array" if log_ticks else "auto",
        tickvals=log_ticks or None,
        ticktext=[compact(value) for value in log_ticks] if log_ticks else None,
    )
    fig.update_yaxes(
        categoryorder="array",
        categoryarray=labels,
        autorange="reversed",
        showgrid=False,
        tickfont=dict(size=11),
        automargin=True,
    )
    return fig


COMP_COLORS = [THEME["green"], "#1488ee", "#fec902", "#8b3fe0", "#f20e36", "#59b78d"]


def create_stacked_components(df: pd.DataFrame, label: str, comps: dict, weights: dict, height: int = 300, show_total: bool = True) -> go.Figure:
    """Contribution de chaque composante au score (points d'IPT) : barres empilées horizontales, SANS légende intégrée.

    La légende est un bloc HTML séparé (`stacked_legend`) : elle ne chevauche donc jamais le titre ni les barres.
    Segments séparés par un liseré blanc ; le score total est écrit au bout de chaque barre.
    """
    fig = go.Figure()
    wsum = sum(weights.values()) or 1
    totals = pd.Series(0.0, index=range(len(df)))
    for (code, (lab, *_)), c in zip(comps.items(), COMP_COLORS):
        x = (df[f"{code}_norm"] * weights.get(code, 0) / wsum).to_numpy()
        totals = totals + x
        fig.add_trace(go.Bar(y=df[label], x=x, name=lab, orientation="h", marker=dict(color=c, line=dict(color="#ffffff", width=1.6)),
                             hovertemplate="<b>%{y}</b><br>" + lab + " : <b>%{x:.1f}</b> points<br><i>Contribution au score</i><extra></extra>"))
    top = float(totals.max()) if len(totals) else 0.0
    if show_total and len(df):
        fig.add_trace(go.Scatter(x=totals.to_numpy(), y=df[label], mode="text", text=[f"<b>{v:.1f}</b>" for v in totals], textposition="middle right",
                                 textfont=dict(size=12, color="#1e3a4c"), hoverinfo="skip", showlegend=False, cliponaxis=False))
    _layout(fig, height, t=6, b=34)
    fig.update_layout(barmode="stack", showlegend=False, bargap=0.32)
    fig.update_yaxes(autorange="reversed", showgrid=False, tickfont=dict(size=12), automargin=True)
    fig.update_xaxes(gridcolor=GRID, zeroline=False, tickfont=dict(size=11.5), range=[0, max(top * 1.16, 1)],
                     title=dict(text="Points d'indice (total = score IPT)", font=dict(size=11.5)))
    return fig


def stacked_legend(comps: dict, weights: dict, values: dict | None = None, title: str = "Légende") -> str:
    """Légende HTML du graphique de contributions, présentée comme une carte distincte du graphique :
    titre « Légende » + consigne de lecture, puis une pastille par composante (couleur, libellé, valeur en encart à droite)."""
    wsum = sum(weights.values()) or 1
    items = []
    for (code, (lab, *_)), c in zip(comps.items(), COMP_COLORS):
        val = f'{values[code]:.1f} pts' if values is not None and code in values else f'{100 * weights.get(code, 0) / wsum:.0f} %'
        items.append(f'<div class="cmp-leg-item" style="--c:{c}"><span class="cmp-dot"></span><span class="cmp-lab">{lab}</span><b class="cmp-val">{val}</b></div>')
    sub = "Chaque couleur = une composante ; la valeur indique les <b>points apportés au score</b>" if values is not None else "Chaque couleur = une composante ; la valeur indique son <b>poids dans l'indice</b>"
    return (f'<div class="cmp-legend"><div class="cmp-leg-title"><i class="fa-solid fa-circle-info"></i><b>{title}</b><span>{sub}</span></div>'
            f'<div class="cmp-leg-grid">{"".join(items)}</div></div>')


def create_indicator_rows(items: list[tuple[str, str, str, str]]) -> str:
    """Indicateurs clés (icône ronde + libellé + valeur) : `items` = (icône Font Awesome, libellé, valeur formatée, note courte)."""
    rows = []
    for icon, lab, val, note in items:
        rows.append(f'<div class="ind-row"><div class="ind-ico"><i class="fa-solid {icon}"></i></div><div><div class="ind-lab">{lab}</div>'
                    f'<div class="ind-val">{val}</div></div><div class="ind-delta" style="color:#4f6270;font-weight:600;max-width:46%;text-align:right">{note}</div></div>')
    return "".join(rows)


def create_cumulative(values, labels, height: int = 250, k_marks=(5,)) -> go.Figure:
    """Concentration : part cumulée de la population des territoires classés du plus au moins peuplé (barres = part de chacun, ligne = cumul)."""
    s = pd.Series(list(values), index=list(labels)).sort_values(ascending=False)
    part = s / s.sum() * 100
    cum = part.cumsum()
    fig = go.Figure()
    fig.add_trace(go.Bar(x=list(range(1, len(s) + 1)), y=part, name="Part du territoire", marker_color=THEME["green"], customdata=np.stack([s.index, part.round(1), cum.round(1)], axis=-1),
                         hovertemplate="Rang %{x} · <b>%{customdata[0]}</b><br>Part : %{customdata[1]} %<br>Cumul : %{customdata[2]} %<br><i>Concentration de la population</i><extra></extra>"))
    fig.add_trace(go.Scatter(x=list(range(1, len(s) + 1)), y=cum, name="Part cumulée", mode="lines+markers", line=dict(color=THEME["blue"], width=2.6), marker=dict(size=5),
                             hovertemplate="Les %{x} plus peuplés : <b>%{y:.1f} %</b><extra></extra>"))
    _layout(fig, height, t=34, b=34)
    fig.update_layout(showlegend=True, legend=dict(orientation="h", x=-0.02, y=1.22, xanchor="left", yanchor="top", font=dict(size=11.5)))
    for k in k_marks:
        if len(s) >= k:
            fig.add_annotation(x=k, y=float(cum.iloc[k - 1]), text=f"Top {k} : {fmt_dec(cum.iloc[k - 1], 1)} %", showarrow=True, arrowhead=2, ax=38, ay=-26, font=dict(size=11.5, color=THEME["blue"]))
    fig.update_xaxes(title=dict(text="Rang du territoire (du plus au moins peuplé)", font=dict(size=11.5)), gridcolor=GRID, zeroline=False, tickfont=dict(size=11.5), dtick=max(1, len(s) // 8))
    fig.update_yaxes(title=dict(text="% de la population", font=dict(size=11.5)), gridcolor=GRID, zeroline=False, tickfont=dict(size=11.5), range=[0, 104])
    return fig
