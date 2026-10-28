"""
Dashboard décisionnel territorial du Togo — Data Lab Défi 2 (Streamlit, construit sur le template-modele).

Point d'entrée : `streamlit run app.py`
Chaque page vit dans views/ ; l'en-tête, la barre de navigation et le CSS sont partagés ici.
Les données proviennent exclusivement de outputs/data/ (produit par tools/build_tables.py).
"""
import streamlit as st

st.set_page_config(page_title="Défi 2 – Territoires du Togo", page_icon="assets/favicon.png", layout="wide", initial_sidebar_state="expanded")

from components.header import create_header          # noqa: E402  (après set_page_config)
from components.navbar import create_navbar          # noqa: E402
from components.styles import inject_css             # noqa: E402

# ---- Déclaration des pages (la navigation native est masquée : on utilise notre propre navbar) ----
PAGES = {
    "overview": st.Page("views/overview.py", title="Accueil · vue d'ensemble", default=True),
    "carte": st.Page("views/carte.py", title="Carte interactive multi-couches", url_path="carte-interactive"),
    "demographie": st.Page("views/demographie.py", title="Démographie", url_path="demographie"),
    "evolution": st.Page("views/evolution.py", title="Évolution 2010–2022", url_path="evolution-2010-2022"),
    "services": st.Page("views/services_base.py", title="Services de base", url_path="services-de-base"),
    "etat_civil": st.Page("views/etat_civil_identite.py", title="État civil & identité", url_path="etat-civil-identite"),
    "priorites": st.Page("views/recommandations.py", title="Priorités & recommandations", url_path="priorites-recommandations"),
    "comparer": st.Page("views/comparer.py", title="Comparer 2 à 4 territoires", url_path="comparer-territoires"),
    "methode": st.Page("views/methode.py", title="Méthode & données", url_path="methode-donnees"),
}
current = st.navigation(list(PAGES.values()), position="hidden")
current_key = next(k for k, p in PAGES.items() if p.url_path == current.url_path or (k == "overview" and current.url_path == ""))

inject_css()
with st.container(key="topbar"):                    # bandeau fixe : header (68 px) + navbar (61 px)
    create_header()
    create_navbar(PAGES, current_key)
current.run()
