"""Barre de navigation horizontale (vert foncé) ; l'entrée active est jaune/or. 9 pages, libellés courts pour rester lisibles à 1280 px et au-delà."""
from __future__ import annotations

import streamlit as st

# (libellé, icône [indicatif], clé de page, poids de colonne). L'icône réellement affichée est définie
# par index (.st-key-nav_<i>) dans components/styles.py.
NAV_ITEMS = [
    ("Accueil", "house", "overview", 1.0),
    ("Carte", "map", "carte", 0.9),
    ("Démographie", "users", "demographie", 1.35),
    ("Évolution", "chart-line", "evolution", 1.1),
    ("Services", "bolt", "services", 1.05),
    ("État civil", "id-card", "etat_civil", 1.1),
    ("Priorités", "bullseye", "priorites", 1.05),
    ("Comparer", "scale-balanced", "comparer", 1.15),
    ("Méthode", "book-open", "methode", 1.05),
]


def create_navbar(pages: dict, current: str) -> None:
    """`pages` : clé -> st.Page ; `current` : clé de la page affichée (menu actif en jaune)."""
    with st.container(key="navbar"):
        cols = st.columns([w for *_, w in NAV_ITEMS], gap="small")
        for i, (col, (label, icon, key, _)) in enumerate(zip(cols, NAV_ITEMS)):
            with col:
                if st.button(label, key=f"nav_{i}", type="primary" if key == current else "secondary", width="stretch", help=pages[key].title):
                    st.switch_page(pages[key])
