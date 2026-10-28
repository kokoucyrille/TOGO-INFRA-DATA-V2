"""Tableaux HTML aux couleurs des maquettes (en-tête vert pâle, lignes séparées, évolution en vert)."""
from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from utils.formats import fmt_dec, fmt_int


def create_table(df: pd.DataFrame, formats: dict | None = None, up_cols: tuple = (), raw_cols: tuple = (), num_cols: tuple = ()) -> str:
    """
    Convertit un DataFrame en table HTML.
    `formats` : colonne -> fonction de mise en forme ; `up_cols` : colonnes de variation (flèche verte) ;
    `raw_cols` : colonnes dont le contenu est du HTML déjà sûr (badges) — toutes les autres cellules sont ÉCHAPPÉES ; `num_cols` : alignées à droite.
    """
    formats = formats or {}
    head = "".join(f'<th class="num">{html.escape(str(c))}</th>' if c in num_cols else f"<th>{html.escape(str(c))}</th>" for c in df.columns)
    body = []
    for _, row in df.iterrows():
        cells = []
        for c in df.columns:
            v = row[c]
            txt = formats[c](v) if c in formats else (fmt_dec(v) if isinstance(v, float) else str(v))
            txt = txt if c in raw_cols else html.escape(str(txt))
            if c in up_cols:
                cells.append(f'<td class="up"><i class="fa-solid fa-arrow-up" style="font-size:11px"></i> {txt}</td>')
            else:
                cells.append(f'<td class="num">{txt}</td>' if c in num_cols else f"<td>{txt}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return f'<table class="tbl"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table>'


def render_table(df: pd.DataFrame, **kw) -> None:
    if df.empty:
        st.markdown('<div style="color:#7b8794;padding:20px 0">Aucune donnée pour cette sélection.</div>', unsafe_allow_html=True)
        return
    st.markdown(create_table(df, **kw), unsafe_allow_html=True)


# mises en forme usuelles
FMT_PERF = {"CA (Md)": lambda v: fmt_dec(v, 1), "Ventes": fmt_int, "Marge (%)": lambda v: fmt_dec(v, 1),
            "Évolution": lambda v: f"+{fmt_dec(v, 1)}%"}
