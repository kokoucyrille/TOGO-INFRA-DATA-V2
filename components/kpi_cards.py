"""Cartes KPI : icône ronde + titre + valeur — AUCUN texte descriptif sous la valeur."""
from __future__ import annotations

import streamlit as st

from components.styles import THEME

# variante -> (fond de carte, couleur de l'icône ronde, couleur de la valeur)
VARIANTS = {
    "green": (THEME["kpi_green"], THEME["green"], THEME["green_dark"]),
    "yellow": (THEME["kpi_yellow"], THEME["gold"], "#a36f00"),
    "gray": (THEME["kpi_gray"], "#3d3d3d", "#3d3d3d"),
    "red": (THEME["kpi_pink"], THEME["red"], THEME["red"]),
    "blue": (THEME["kpi_blue"], "#1488ee", "#0b5cc7"),
    "purple": (THEME["kpi_purple"], "#8b3fe0", "#5b21b6"),
    "teal": (THEME["kpi_green"], "#0d8a7a", "#0b7a6a"),
    "ghost": (THEME["kpi_gray"], "transparent", "#10335c"),
}


def create_kpi_card(title: str, value: str, icon: str, variant: str = "green", value_style: str = "") -> str:
    """Retourne le HTML d'une carte KPI (titre + valeur uniquement)."""
    bg, icon_bg, val_color = VARIANTS[variant]
    icon_color = "#fff" if icon_bg != "transparent" else "#7b8794"
    style = f' style="{value_style}"' if value_style else ""
    return (
        f'<div class="kpi" style="background:{bg}">'
        f'<div class="kpi__icon" style="background:{icon_bg};color:{icon_color}"><i class="fa-solid {icon}"></i></div>'
        f'<div class="kpi__body"><div class="kpi__title">{title}</div>'
        f'<div class="kpi__value" style="color:{val_color}{("; " + value_style) if value_style else ""}">{value}</div></div></div>')


def create_kpi_row(cards: list[dict], key: str = "kpi_row") -> None:
    """Affiche une rangée de KPI. Chaque carte : {title, value, icon, variant, value_style (optionnel)}."""
    with st.container(key=key):
        cols = st.columns(len(cards), gap="small")
        for col, c in zip(cols, cards):
            col.markdown(create_kpi_card(c["title"], c["value"], c["icon"], c.get("variant", "green"), c.get("value_style", "")),
                         unsafe_allow_html=True)
