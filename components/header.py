"""En-tête institutionnel : drapeau + intitulés à gauche ; titre du challenge à droite."""
from __future__ import annotations

import streamlit as st

from components.ui import flag_data_uri


def create_header() -> None:
    with st.container(key="header"):
        c_logo, c_title = st.columns([4.0, 6.4], gap="small")
        c_logo.markdown(
            f'<div class="hdr"><img src="{flag_data_uri()}" alt="Togo">'
            '<div><div class="t1">RÉPUBLIQUE TOGOLAISE</div>'
            '<div class="t2">TRAVAIL - LIBERTÉ - PATRIE</div></div></div>', unsafe_allow_html=True)
        c_title.markdown('<div class="hdr-challenge">DATA CHALLENGE - ADMINISTRATION TERRITORIALE | DÉFI 2</div>', unsafe_allow_html=True)
