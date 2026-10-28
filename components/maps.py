"""
Cartographie du Togo.

* create_region_map()   : petite carte Plotly (sans fond), régions en dégradé de vert.
* create_map()          : carte choroplèthe Plotly cliquable (aucun fond externe, aucune dépendance réseau) : un clic renvoie les identifiants
                          sélectionnés (`on_select="rerun"`) ; utilisée par toutes les pages (population, évolution, services de base, priorités, carte interactive).
"""
from __future__ import annotations

import json

import numpy as np
import html as _html

import pandas as pd
import plotly.colors as pc
import plotly.graph_objects as go
import streamlit as st

from components.charts import show
from data import loader as D

TOGO_BOUNDS = [[6.0, -0.25], [11.2, 1.9]]
TOGO_CENTER = [8.62, 0.98]
GREEN_SCALE = [[0, "#cfe8da"], [1, "#016b4b"]]

# légendes
SERVICES_LEGEND = [("Très élevée", "#016b4b"), ("Élevée", "#1488ee"), ("Moyenne", "#fec902"),
                   ("Faible", "#f20e36"), ("Très faible", "#8b3fe0")]
INFRA_LEGEND = [("Très bonne", "#0b6b4b"), ("Bonne", "#35a37a"), ("Moyenne", "#7cc99f"),
                ("Faible", "#fbe27a"), ("Très faible", "#bfeadb")]


# --------------------------------------------------------------------------------------
# Carte Plotly des régions (sans fond de carte)
# --------------------------------------------------------------------------------------
def region_colors(parts: dict) -> dict:
    """Couleur de chaque région selon sa part (dégradé vert clair -> vert institutionnel)."""
    vals = {r: v for r, v in parts.items() if v == v}                 # ignore NaN
    lo, hi = min(vals.values()), max(vals.values())
    out = {}
    for r, v in vals.items():
        t = 0.5 if hi == lo else (v - lo) / (hi - lo)
        out[r] = pc.sample_colorscale(GREEN_SCALE, [0.12 + 0.88 * t])[0]
    return out


def _polygons(geometry: dict):
    """Anneaux extérieurs (liste de listes de (lon, lat)) d'une géométrie Polygon / MultiPolygon."""
    polys = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
    return [p[0] for p in polys]


def create_region_map(parts: dict, height: int = 190) -> go.Figure:
    """
    Carte des régions dessinée directement avec des polygones Plotly (aucun fond externe requis).
    Les préfectures sont nuancées dans la couleur de leur région (effet « mosaïque » de la maquette).
    """
    colors = region_colors(parts)
    rng = np.random.default_rng(5)
    fig = go.Figure()
    for ft in D.prefectures_geojson()["features"]:
        reg, name = ft["properties"]["region"], ft["properties"]["label"]
        if reg in colors:
            rgb = [int(x) for x in colors[reg].strip("rgb()").split(",")]
            k = rng.uniform(-12, 12)
            fill = "rgb({},{},{})".format(*[max(0, min(255, int(c + k))) for c in rgb])
        else:
            fill = "#e6eeee"                                          # hors sélection
        for ring in _polygons(ft["geometry"]):
            xs, ys = zip(*ring)
            fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", fill="toself", fillcolor=fill, line=dict(color="#ffffff", width=0.8),
                                     hoverinfo="text", text=f"{reg} — {name}", showlegend=False))
    fig.update_xaxes(visible=False, constrain="domain")
    fig.update_yaxes(visible=False, scaleanchor="x", scaleratio=1.0)
    fig.update_layout(height=height, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", showlegend=False, hoverlabel=dict(font_size=12))
    return fig


def region_map_legend(parts: dict) -> list[tuple[str, str, str]]:
    colors = region_colors(parts)
    return [(colors[r], r, f"{D.fmt_dec(v, 1)}%") for r, v in parts.items() if v == v]


# --------------------------------------------------------------------------------------
# Cartes Plotly cliquables (choroplèthes par classes + bulles + points)
# --------------------------------------------------------------------------------------
NO_DATA = "#e3eaed"
SEL_LINE = "#003f8c"


def _coords(geom) -> list:
    """Tous les couples (lon, lat) d'une géométrie GeoJSON (Polygon / MultiPolygon)."""
    out: list = []

    def rec(c):
        if c and isinstance(c[0], (int, float)):
            out.append((c[0], c[1]))
        else:
            for x in c:
                rec(x)
    rec(geom.get("coordinates", []))
    return out


def zoom_ranges(gj: dict | None, names, points=None, min_span: float = 1.0):
    """Cadre (lat, lon) englobant les territoires affichés : la carte zoome sur la partie filtrée.
    Retourne None pour le pays entier (cadrage par défaut). `min_span` évite de sur-zoomer sur une très petite préfecture."""
    pts: list = []
    if gj is not None and names is not None:
        wanted = set(names)
        for ft in gj["features"]:
            if ft["properties"].get("name") in wanted:
                pts += _coords(ft["geometry"])
    if points:
        pts += list(points)
    if not pts:
        return None
    lon, lat = [p[0] for p in pts], [p[1] for p in pts]
    la0, la1, lo0, lo1 = min(lat), max(lat), min(lon), max(lon)
    if (la1 - la0) > 4.3 and (lo1 - lo0) > 1.4:                            # presque tout le pays : cadrage par défaut
        return None
    dla, dlo = max(la1 - la0, min_span), max(lo1 - lo0, min_span)
    cla, clo = (la0 + la1) / 2, (lo0 + lo1) / 2
    pad = 1.18
    return [cla - dla * pad / 2, cla + dla * pad / 2], [clo - dlo * pad / 2, clo + dlo * pad / 2]


def _geo_layout(fig: go.Figure, height: int, legend_title: str = "", zoom=None) -> go.Figure:
    if zoom:
        fig.update_geos(fitbounds=False, visible=False, projection_type="mercator", bgcolor="rgba(0,0,0,0)", lataxis_range=zoom[0], lonaxis_range=zoom[1], lataxis_showgrid=False, lonaxis_showgrid=False)
    else:
        fig.update_geos(fitbounds="locations", visible=False, projection_type="mercator", bgcolor="rgba(0,0,0,0)", lataxis_range=[6.0, 11.2], lonaxis_range=[-0.25, 1.9])
    fig.update_layout(height=height, margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", clickmode="event+select",
                      hoverlabel=dict(font_size=13, font_family="Nunito Sans, Arial, sans-serif", align="left"), dragmode="pan",
                      legend=dict(x=0.99, y=0.99, xanchor="right", yanchor="top", bgcolor="rgba(255,255,255,.92)", bordercolor="#c9d8de", borderwidth=1,
                                  font=dict(size=12, color="#0a4a9a"), itemclick=False, itemdoubleclick=False, title=dict(text=legend_title, font=dict(size=11))))
    return fig


def _cities(fig: go.Figure) -> None:
    lat, lon, name = zip(*[(v[0], v[1], k) for k, v in D.CITIES.items()])
    fig.add_trace(go.Scattergeo(lat=lat, lon=lon, text=name, mode="markers+text", textposition="middle right", textfont=dict(size=10.5, color="#1e3a4c"),
                                marker=dict(size=5, color="#0a4a9a", line=dict(color="#fff", width=1)), hoverinfo="skip", showlegend=False, name="Villes repères"))


def build_choropleth(level: str, df: pd.DataFrame, legend: list[tuple[str, str]], value_label: str = "Valeur", fmt=D.fmt_int, cls_col: str = "cls",
                     highlight: set | None = None, height: int = 420, nat_text: str | None = None, extra_traces: list | None = None) -> go.Figure:
    """Figure cliquable. level : « Région » | « Préfecture » (polygones, une ligne par polygone avec `code`) | « Commune » (bulles, `lat`/`lon`).
    df : `Territoire`, `Valeur`, classe `cls` (0 = classe la plus haute de la légende ; NaN = hors sélection / N/D), `id` (renvoyé au clic) et `tip` (libellé).
    Chaque classe est une trace nommée (légende) ; les territoires sans valeur sont grisés et libellés « N/D »."""
    palette = [c for _, c in legend]
    labels = [l for l, _ in legend]
    highlight = set(highlight or [])
    fig = go.Figure()
    d = df.copy()
    if "tip" not in d:
        d["tip"] = d["Territoire"]
    d["tip"] = d["tip"].fillna(d["Territoire"])
    if level in ("Région", "Préfecture"):
        gj = D.regions_geojson() if level == "Région" else D.prefectures_geojson()
        tous = [f["properties"]["name"] for f in D.prefectures_geojson()["features"]] if level == "Préfecture" else [f["properties"]["name"] for f in gj["features"]]
        gj = D.prefectures_geojson() if level == "Préfecture" else gj
        fig.add_trace(Choropleth_bg(gj, tous))
        if "code" not in d:
            d["code"] = d["Territoire"]
        for i, (lab, col) in enumerate(legend):
            g = d[d[cls_col] == i]
            if g.empty:
                fig.add_trace(go.Scattergeo(lat=[None], lon=[None], mode="markers", marker=dict(size=11, color=col, symbol="square"), name=lab, hoverinfo="skip"))
                continue
            hv = [f"<b>{t}</b><br>{value_label} : <b>{fmt(v)}</b><br>Classe : {lab}" + (f"<br>{nat_text}" if nat_text else "") for t, v in zip(g.tip, g.Valeur)]
            fig.add_trace(go.Choropleth(geojson=gj, featureidkey="properties.name", locations=g.code, z=[0] * len(g), colorscale=[[0, col], [1, col]], showscale=False,
                                        marker=dict(line=dict(color="#ffffff", width=1.1)), customdata=g[["id"]].to_numpy(), text=hv, hovertemplate="%{text}<extra></extra>",
                                        name=lab, showlegend=True, selected=dict(marker=dict(opacity=1)), unselected=dict(marker=dict(opacity=1))))
        nd = d[d[cls_col].isna()]
        if len(nd):
            fig.add_trace(go.Choropleth(geojson=gj, featureidkey="properties.name", locations=nd.code, z=[0] * len(nd), colorscale=[[0, NO_DATA], [1, NO_DATA]], showscale=False,
                                        marker=dict(line=dict(color="#ffffff", width=1)), customdata=nd[["id"]].to_numpy(), text=[f"<b>{t}</b><br>{value_label} : N/D (hors sélection ou valeur absente)" for t in nd.tip],
                                        hovertemplate="%{text}<extra></extra>", name="N/D · hors sélection", showlegend=True))
        if highlight:
            fig.add_trace(go.Choropleth(geojson=gj, featureidkey="properties.name", locations=sorted(highlight), z=[0] * len(highlight), colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]],
                                        showscale=False, marker=dict(line=dict(color=SEL_LINE, width=3.5)), hoverinfo="skip", showlegend=False, name="Sélection"))
    else:                                                                    # bulles par commune / canton
        fig.add_trace(Choropleth_bg(D.regions_geojson(), [f["properties"]["name"] for f in D.regions_geojson()["features"]]))
        d = d.dropna(subset=["lat", "lon"])
        vmax = float(d["Valeur"].max()) or 1.0
        for i, (lab, col) in enumerate(legend):
            g = d[d[cls_col] == i]
            if g.empty:
                fig.add_trace(go.Scattergeo(lat=[None], lon=[None], mode="markers", marker=dict(size=10, color=col), name=lab, hoverinfo="skip"))
                continue
            hl = g.Territoire.isin(highlight)
            fig.add_trace(go.Scattergeo(lat=g.lat, lon=g.lon, mode="markers", name=lab, customdata=g[["id"]].to_numpy(),
                                        marker=dict(size=[5 + 16 * float(np.sqrt(v / vmax)) for v in g.Valeur], color=col, opacity=0.9, line=dict(color=[SEL_LINE if h else "#ffffff" for h in hl], width=[3 if h else 1 for h in hl])),
                                        text=[f"<b>{t}</b> ({p})<br>{value_label} : <b>{fmt(v)}</b>" for t, p, v in zip(g.Territoire, g.get("Préfecture", ""), g.Valeur)], hovertemplate="%{text}<extra></extra>"))
    for t in extra_traces or []:
        fig.add_trace(t)
    _cities(fig)
    if level in ("Région", "Préfecture"):
        zoom = zoom_ranges(gj, d["code"].dropna().unique())
    else:
        zoom = zoom_ranges(None, None, points=list(zip(d["lon"], d["lat"])) if len(d) else None)
    return _geo_layout(fig, height, zoom=zoom)


def Choropleth_bg(gj: dict, names: list) -> go.Choropleth:
    """Fond gris de tous les contours (les territoires non colorés restent visibles), sans interaction."""
    return go.Choropleth(geojson=gj, featureidkey="properties.name", locations=names, z=[0] * len(names), colorscale=[[0, NO_DATA], [1, NO_DATA]], showscale=False,
                         marker=dict(line=dict(color="#ffffff", width=0.8)), hoverinfo="skip", showlegend=False, name="Contours")


def selected_ids(event) -> list:
    """Identifiants (`customdata[0]`) des points sélectionnés dans l'événement `st.plotly_chart(on_select=…)`."""
    pts = (event.selection.points if event is not None and getattr(event, "selection", None) else []) or []
    ids = []
    for p in pts:
        cd = p.get("customdata")
        if isinstance(cd, dict):                                    # Streamlit renvoie customdata sous forme {'0': valeur}
            cd = cd.get("0", next(iter(cd.values()), None))
        if cd not in (None, [], ()):
            ids.append(cd[0] if isinstance(cd, (list, tuple)) else cd)
    return ids


def create_map(level: str, df: pd.DataFrame, legend: list[tuple[str, str]], key: str, height: int = 420, value_label: str = "Valeur", fmt=D.fmt_int,
               cls_col: str = "cls", highlight: set | None = None, nat_text: str | None = None, extra_traces: list | None = None) -> list:
    """Affiche la carte Plotly cliquable ; retourne les identifiants (`id`) cliqués (liste vide sans sélection)."""
    fig = build_choropleth(level, df, legend, value_label, fmt, cls_col, highlight, height, nat_text, extra_traces)
    ev = st.plotly_chart(fig, width="stretch", key=key, on_select="rerun", selection_mode="points",
                         config={"displayModeBar": "hover", "displaylogo": False, "scrollZoom": False, "responsive": True, "topojsonURL": "app/static/",
                                 "modeBarButtons": [["toImage"]], "toImageButtonOptions": {"format": "png", "filename": key, "scale": 2}})
    return selected_ids(ev)


# --------------------------------------------------------------------------------------
# Classification
# --------------------------------------------------------------------------------------
def classify_rank(values: pd.Series, n: int = 5) -> pd.Series:
    """Classes par rang (0 = valeurs les plus élevées ... 4 = les plus faibles), équilibrées en effectif."""
    s = values.astype(float)
    ranks = s.rank(method="first", ascending=False)
    cls = np.floor((ranks - 1) / max(len(s), 1) * n).clip(0, n - 1)
    return cls.where(s.notna())


def classify_thresholds(values: pd.Series, edges=(85, 70, 58, 50)) -> pd.Series:
    """Classes absolues pour un taux de couverture : >=85 très bonne, >=70 bonne, >=58 moyenne, >=50 faible."""
    s = values.astype(float)
    cls = pd.Series(4, index=s.index)
    for i, e in reversed(list(enumerate(edges))):
        cls = cls.where(~(s >= e), i)
    return cls.where(s.notna())


# --------------------------------------------------------------------------------------
# Défi 2 : légendes à tranches calculées, cartes de points (agences)
# --------------------------------------------------------------------------------------
SEQ_LEGEND = ["#08306b", "#2171b5", "#6baed6", "#bdd7e7", "#eff3ff"]                  # vert foncé = valeur la plus élevée
ACCESS_LEGEND_COLORS = ["#2c7bb6", "#abd9e9", "#ffffbf", "#fdae61", "#d7191c"]                   # bleu = accès élevé … rouge = accès faible (palette sûre pour le daltonisme)
DEFICIT_LEGEND_COLORS = ["#7f0026", "#e31a1c", "#fd8d3c", "#fecc5c", "#ffffb2"]                    # rouge foncé = déficit / volume le plus élevé
PRIORITY_LEGEND = [("Très haute", "#d7191c"), ("Haute", "#fdae61"), ("Moyenne", "#fee08b"), ("Faible", "#2c7bb6")]
COMPARABILITY_LEGEND = [("HIGH · comparable", "#016b4b"), ("MEDIUM · prudence", "#fec902"), ("LOW · non comparable", "#b8c4cc")]


def legend_from_values(values: pd.Series, palette: list[str], fmt=D.fmt_int, n: int = 5, higher_is_first: bool = True) -> tuple[pd.Series, list[tuple[str, str]]]:
    """Classes d'effectif équilibré (rang) + légende « min – max » de chaque classe. Classe 0 = valeurs les plus élevées (ou les plus faibles si
    `higher_is_first` est faux). Les valeurs absentes (N/D) restent sans classe : elles sont grisées sur la carte, jamais remplacées par 0."""
    s = values.astype(float)
    cls = classify_rank(s, n) if higher_is_first else classify_rank(-s, n)
    leg = []
    for i in range(n):
        v = s[cls == i]
        lab = f"{fmt(v.min())} – {fmt(v.max())}" if len(v) and v.min() != v.max() else (fmt(v.iloc[0]) if len(v) else "—")
        leg.append((lab, palette[i % len(palette)]))
    return cls, leg


def build_points_map(df: pd.DataFrame, color_col: str, palette: dict, label_col: str = "label", height: int = 420) -> go.Figure:
    """Carte de points (agences) : une trace par service (couleur) ; pastille pleine = agence ouverte, creuse à contour gris = non ouverte ; contours des préfectures en fond."""
    gj = D.prefectures_geojson()
    fig = go.Figure(Choropleth_bg(gj, [f["properties"]["name"] for f in gj["features"]]))
    d = df.dropna(subset=["lat", "lon"])
    for service, col in palette.items():
        for ouverte in (True, False):
            g = d[(d[color_col] == service) & (d["ouverte"].astype(bool) == ouverte)] if "ouverte" in d else (d[d[color_col] == service] if ouverte else d.iloc[0:0])
            if g.empty:
                continue
            fig.add_trace(go.Scattergeo(lat=g.lat, lon=g.lon, mode="markers", name=f"{service}" + ("" if ouverte else " · non ouverte"), customdata=g[["prefecture_id"]].to_numpy() if "prefecture_id" in g else None,
                                        marker=dict(size=9 if ouverte else 8, color=col if ouverte else "#ffffff", symbol="circle" if service != "TdE" else "diamond",
                                                    line=dict(color="#ffffff" if ouverte else "#6a7b86", width=1.2 if ouverte else 2.2)),
                                        text=[f"<b>{_html.escape(str(n))}</b><br>Statut : {'Ouverte' if ouverte else 'Non ouverte'}" for n in g[label_col]], hovertemplate="%{text}<extra></extra>"))
    _cities(fig)
    return _geo_layout(fig, height)


def create_points_map(df: pd.DataFrame, color_col: str, palette: dict, height: int = 420, label_col: str = "label", key: str = "map_points") -> None:
    st.plotly_chart(build_points_map(df, color_col, palette, label_col, height), width="stretch", key=key,
                    config={"displayModeBar": "hover", "displaylogo": False, "topojsonURL": "app/static/", "modeBarButtons": [["toImage"]], "toImageButtonOptions": {"format": "png", "filename": key, "scale": 2}})


def agency_traces(ag: pd.DataFrame, services=("CEET", "TdE")) -> list:
    """Traces de points des agences ouvertes (pastille pleine) et non ouvertes (creuse) à superposer à une carte choroplèthe. `ag` : table `agences_geo`."""
    style = {"CEET": ("#111111", "circle"), "TdE": ("#6a1b9a", "diamond")}
    out = []
    d = ag[ag.est_public.astype(bool)].dropna(subset=["lat", "lon"]) if "lat" in ag else ag[ag.est_public.astype(bool)].dropna(subset=["lon"])
    for sv in services:
        col, sym = style[sv]
        for ouverte in (True, False):
            g = d[(d.service == sv) & (d.ouverte_public.astype(bool) == ouverte)]
            if g.empty:
                continue
            out.append(go.Scattergeo(lat=g.lat, lon=g.lon, mode="markers", name=f"Agence {sv}" + ("" if ouverte else " (non ouverte)"),
                                     marker=dict(size=9 if ouverte else 8, symbol=sym, color=col if ouverte else "#ffffff", line=dict(color="#ffffff" if ouverte else col, width=1.2 if ouverte else 2)),
                                     text=[f"<b>{_html.escape(str(n))}</b><br>Statut : {'ouverte' if ouverte else 'non ouverte'}" for n in g.nom], hovertemplate="%{text}<extra></extra>"))
    return out
