"""Petits éléments d'interface partagés : titres de page, panneaux, formats."""
from __future__ import annotations

import base64
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

import streamlit as st

ASSETS = Path(__file__).resolve().parent.parent / "assets"
_PANEL_HEIGHTS: dict[str, int] = {}      # clé de panneau -> hauteur (px), vidé par flush_panel_css()


@lru_cache(maxsize=1)
def flag_data_uri() -> str:
    """Drapeau du Togo encodé en base64 (utilisable dans le HTML injecté)."""
    raw = (ASSETS / "logo_togo.png").read_bytes()
    return "data:image/png;base64," + base64.b64encode(raw).decode()


def page_title(icon: str, title: str, subtitle: str) -> None:
    """Titre + sous-titre de page (icône Font Awesome à gauche)."""
    st.markdown(
        f'<div class="page-title"><div class="pi"><i class="fa-solid {icon}"></i></div>'
        f'<div><h1>{title}</h1><p>{subtitle}</p></div></div>', unsafe_allow_html=True)
    chips_bar()


def chips_bar() -> None:
    """Rappel visible des filtres actifs (puces) ; « Tout le pays » quand aucun filtre territorial n'est posé."""
    from components import gstate
    ch = gstate.chips(st.session_state.get("_chips_extra"))
    body = "".join(f'<span class="chip"><i class="fa-solid fa-filter"></i>{c}</span>' for c in ch) or '<span class="chip chip-off"><i class="fa-solid fa-location-dot"></i>Tout le pays · aucun filtre actif</span>'
    st.markdown(f'<div class="chips" role="status" aria-label="Filtres actifs">{body}</div>', unsafe_allow_html=True)


@contextmanager
def panel(key: str, title: str, icon: str, height: int | None = None, menu: bool = False):
    """
    Carte blanche à bordure légère avec titre (icône + libellé ; `menu=True` ajoute un « ··· » décoratif, désactivé par défaut car sans action).
    `height` fixe la hauteur pour aligner les panneaux d'une même rangée.
    """
    if height:
        _PANEL_HEIGHTS[key] = height
    with st.container(key=f"panel_{key}"):
        dots = '<span class="dots">&middot;&middot;&middot;</span>' if menu else ""
        st.markdown(f'<div class="panel-title"><i class="fa-solid {icon}"></i><span>{title}</span>{dots}</div>',
                    unsafe_allow_html=True)
        yield


def legend_rows(items: list[tuple[str, str, str]]) -> str:
    """HTML de légende : (couleur, libellé, valeur) -> pastille + libellé + valeur alignée à droite."""
    rows = "".join(
        f'<div class="leg-row"><span><span class="legend-dot" style="background:{c}"></span>{lab}</span><b>{val}</b></div>'
        for c, lab, val in items)
    return rows


def glossaire() -> None:
    """Volet repliable « Glossaire » : accessible depuis chaque page (termes, sigles, natures de données)."""
    from utils.glossaire import GL
    with st.expander("Glossaire : TCAM, IPT, PROXY, N/D…", expanded=False):
        st.markdown("".join(f"<p style='margin:0 0 6px'><b>{t}</b> : {d}</p>" for t, d in GL), unsafe_allow_html=True)


def flush_panel_css() -> None:
    """Émet les hauteurs minimales des panneaux (à appeler en fin de page) ; ajoute le glossaire commun."""
    glossaire()
    if _PANEL_HEIGHTS:
        css = "".join(f".st-key-panel_{k}{{min-height:{h}px !important;height:auto !important;flex:0 0 auto !important;}}"
                      for k, h in _PANEL_HEIGHTS.items())
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
        _PANEL_HEIGHTS.clear()
