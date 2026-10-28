"""Tests de l'application (streamlit.testing.v1.AppTest) : toutes les pages, tous les filtres, cascade, cas vides, N/D, exports, performance.
Chaque vue est exécutée seule (AppTest ne relance que le script de la page) ; le point d'entrée app.py est testé à part."""
import time
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
VIEWS = {"overview": "overview.py", "demographie": "demographie.py", "evolution": "evolution.py", "services": "services_base.py",
         "etat_civil": "etat_civil_identite.py", "priorites": "recommandations.py", "methode": "methode.py"}
REG6 = ["Savanes", "Kara", "Centrale", "Plateaux", "Maritime", "Grand Lomé (DAGL)"]
REG5 = ["Savanes", "Kara", "Centrale", "Plateaux", "Maritime (avec Grand Lomé)"]
VIDE = "Aucune donnée disponible pour cette sélection."


def lancer(page: str) -> AppTest:
    return AppTest.from_file(str(ROOT / "views" / VIEWS[page]), default_timeout=120).run()


def textes(at) -> str:
    return " ".join(m.value for m in at.markdown)


def propre(at):
    assert not at.exception, [e.value[:300] for e in at.exception]


# ───────── point d'entrée ─────────
def test_application_complete_en_tete_et_navigation():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
    propre(at)
    nav = [b.label for b in at.button if b.key and b.key.startswith("nav_")]
    assert nav == ["Accueil", "Carte", "Démographie", "Évolution", "Services", "État civil", "Priorités", "Comparer", "Méthode"]
    assert not [b for b in at.button if b.key and b.key.startswith("lang_")], "les boutons FR / EN ont été supprimés de l'en-tête"
    assert "DÉFI 2" in textes(at) and "Défi 1" not in textes(at), "l'en-tête du gabarit (Défi 1) doit être remplacé"


# ───────── toutes les pages, filtres par défaut ─────────
@pytest.mark.parametrize("page", list(VIEWS))
def test_page_par_defaut(page):
    at = lancer(page)
    propre(at)
    t = textes(at)
    assert 'class="story' in t or page == "overview", "la page contient des blocs de récit calculés"
    assert at.sidebar.markdown, "sidebar de filtres présente"
    assert len(at.get("download_button")) >= 1, "export disponible"


# ───────── chaque région ─────────
@pytest.mark.parametrize("region", REG6)
@pytest.mark.parametrize("page", ["overview", "demographie", "evolution"])
def test_chaque_region_decoupage_2022(page, region):
    at = lancer(page)
    at.sidebar.selectbox(key=f"w_{page}_region").select(region)
    at.run()
    propre(at)
    assert at.sidebar.selectbox(key=f"w_{page}_region").value == region


@pytest.mark.parametrize("region", REG5)
@pytest.mark.parametrize("page", ["services", "priorites"])
def test_chaque_region_historique(page, region):
    at = lancer(page)
    at.sidebar.selectbox(key=f"w_{page}_region").select(region)
    at.run()
    propre(at)


@pytest.mark.parametrize("region", REG5)
def test_decoupage_5_regions_sur_pages_a_decoupage_libre(region):
    for page in ("overview", "demographie", "evolution"):
        at = lancer(page)
        at.sidebar.selectbox(key=f"w_{page}_decoupage").select("5 régions historiques")
        at.run()
        at.sidebar.selectbox(key=f"w_{page}_region").select(region)
        at.run()
        propre(at)


# ───────── tous les modes / sections / indicateurs ─────────
@pytest.mark.parametrize("page,key,values", [
    ("overview", "ov_mode", ["Carte", "Tableau"]), ("overview", "ov_metric", ["Population 2022", "Taux d'accès à l'électricité 2021", "Population sans accès (PROXY)", "Indice de priorité territoriale (0–100)"]),
    ("demographie", "demo_mode", ["Carte", "Graphique", "Tableau"]), ("demographie", "demo_level", ["Région", "Préfecture", "Commune", "Canton"]),
    ("evolution", "ev_mode", ["Carte", "Graphique", "Tableau"]), ("evolution", "ev_level", ["Région", "Préfecture", "Commune"]),
    ("evolution", "ev_ind", ["TCAM (%/an)", "Variation relative (%)", "Variation absolue (hab.)", "Contribution à la croissance (%)", "Population 2022"]),
    ("etat_civil", "ec_mode", ["Graphique", "Tableau"]),
    ("priorites", "pr_scen", ["A · Accès", "B · Population", "C · Équilibre", "D · Équipement", "Personnalisé"]), ("priorites", "pr_mode", ["Carte", "Graphique", "Tableau"]),
    ("methode", "me_sec", ["Sources & niveaux", "Indicateurs & formules", "Comparabilité 2010–2022", "Qualité & limites", "Glossaire"])])
def test_controles(page, key, values):
    at = lancer(page)
    for v in values:
        at.session_state[key] = v
        at.run()
        propre(at)


def test_graphique_population_evolution_compare_les_deux_recensements():
    from components.charts import create_population_comparison_chart
    import pandas as pd

    fig = create_population_comparison_chart(pd.DataFrame({
        "nom": ["Préfecture A", "Préfecture B"],
        "pop_2010": [100_000, 20_000],
        "pop_2022": [150_000, 30_000],
    }), log_x=True)

    assert [trace.name for trace in fig.data if trace.mode == "markers"] == ["2010", "2022"]
    assert len([trace for trace in fig.data if trace.mode == "lines"]) == 2
    assert fig.layout.xaxis.type == "log"
    assert list(fig.layout.yaxis.categoryarray) == ["Préfecture A", "Préfecture B"]


@pytest.mark.parametrize("theme,key,indicators", [
    ("Électricité", "sv_ind_electricite", ["Taux d'accès (%)", "Population sans accès (PROXY)", "Écart à la moyenne nationale (pp)", "Évolution 2018→2021 (pp)"]),
    ("Agences CEET", "sv_ind_CEET", ["Agences pour 100 000 hab.", "Habitants par agence", "Agences ouvertes (nombre)"]),
    ("Agences TdE", "sv_ind_TdE", ["Agences pour 100 000 hab.", "Habitants par agence", "Agences ouvertes (nombre)"]),
    ("Analyse croisée", "sv_ind_croisee", ["Déficit croisé · accès + densité des agences", "Taux d'accès (%)", "Agences combinées pour 100 000 hab."]),
])
def test_graphique_services_selon_indicateur(theme, key, indicators):
    at = lancer("services")
    at.session_state["sv_theme"] = theme
    at.run()
    propre(at)
    for indicator in indicators:
        at.selectbox(key=key).select(indicator)
        at.run()
        propre(at)
        assert len([c for c in at.get("plotly_chart") if (c.key or "").startswith("sv_map_")]) == 1, "une seule carte : celle du thème et de l'indicateur choisis"


def test_services_explorateur_theme_puis_indicateur():
    at = lancer("services")
    propre(at)
    assert len([c for c in at.get("plotly_chart") if (c.key or "").startswith("sv_map_")]) == 1
    assert any(w.key == "sv_theme" for w in at.get("segmented_control")), "sélecteur de thème présent"
    assert [s.key for s in at.selectbox if s.key and s.key.startswith("sv_ind_")] == ["sv_ind_electricite"], "un seul sélecteur d'indicateur, celui du thème actif"
    for theme, key in (("Agences CEET", "sv_ind_CEET"), ("Agences TdE", "sv_ind_TdE"), ("Analyse croisée", "sv_ind_croisee")):
        at.session_state["sv_theme"] = theme
        at.run()
        propre(at)
        assert [s.key for s in at.selectbox if s.key and s.key.startswith("sv_ind_")] == [key]


@pytest.mark.parametrize("annee", ["2018", "2019", "2020", "2021"])
def test_services_annees(annee):
    at = lancer("services")
    at.sidebar.selectbox(key="w_services_annee").select(int(annee))
    at.run()
    propre(at)
    if annee in ("2019", "2020"):
        assert "non publié" in textes(at), "pas de taux national publié pour 2019/2020 : N/D, jamais inventé"


def test_sections_graphiques_etat_civil_identite():
    at = lancer("etat_civil")
    at.session_state["ec_mode"] = "Graphique"
    at.run()
    propre(at)
    assert at.selectbox(key="ec_ind")
    assert at.multiselect(key="ec_types")


# ───────── filtres en cascade ─────────
def test_cascade_region_prefecture_commune_canton():
    at = lancer("demographie")
    at.sidebar.selectbox(key="w_demographie_region").select("Kara")
    at.run()
    prefs = at.sidebar.selectbox(key="w_demographie_prefecture").options
    assert "Kozah" in prefs and "Golfe" not in prefs
    at.sidebar.selectbox(key="w_demographie_prefecture").select("Kozah")
    at.run()
    assert any(c.startswith("Kozah") for c in at.sidebar.selectbox(key="w_demographie_commune").options)
    at.sidebar.selectbox(key="w_demographie_commune").select("Kozah 1")
    at.run()
    cantons = at.sidebar.selectbox(key="w_demographie_canton").options
    assert len(cantons) > 1 and len(cantons) < 60
    at.sidebar.selectbox(key="w_demographie_region").select("Savanes")          # parent modifié : enfants réinitialisés
    at.run()
    propre(at)
    assert at.sidebar.selectbox(key="w_demographie_prefecture").value == "Toutes les préfectures"
    assert at.sidebar.selectbox(key="w_demographie_commune").value == "Toutes les communes"
    assert at.sidebar.selectbox(key="w_demographie_canton").value == "Tous les cantons"


def test_bascule_de_decoupage_reinitialise_la_region():
    at = lancer("demographie")
    at.sidebar.selectbox(key="w_demographie_region").select("Grand Lomé (DAGL)")
    at.run()
    at.sidebar.selectbox(key="w_demographie_decoupage").select("5 régions historiques")
    at.run()
    propre(at)
    assert at.sidebar.selectbox(key="w_demographie_region").value == "Toutes les régions"


def test_niveau_d_analyse_suit_la_profondeur_des_filtres():
    at = lancer("demographie")
    assert at.sidebar.selectbox(key="demo_level").value == "Région"
    at.sidebar.selectbox(key="w_demographie_region").select("Kara")
    at.run()
    assert at.session_state["demo_level"] == "Préfecture"
    at.sidebar.selectbox(key="w_demographie_prefecture").select("Kozah")
    at.run()
    assert at.session_state["demo_level"] == "Commune"


@pytest.mark.parametrize("page,key,values", [
    ("overview", "ov_level", ["Région", "Préfecture"]),
    ("demographie", "demo_level", ["Région", "Préfecture", "Commune", "Canton"]),
    ("evolution", "ev_level", ["Région", "Préfecture", "Commune"]),
])
def test_niveau_d_analyse_dans_la_sidebar(page, key, values):
    at = lancer(page)
    selector = at.sidebar.selectbox(key=key)
    assert selector.options == values
    selector.select(values[-1])
    at.run()
    propre(at)
    assert at.sidebar.selectbox(key=key).value == values[-1]


def test_niveau_vue_ensemble_restreint_pour_l_indice_de_priorite():
    at = lancer("overview")
    at.sidebar.selectbox(key="ov_level").select("Région")
    at.run()
    at.selectbox(key="ov_metric").select("Indice de priorité territoriale (0–100)")
    at.run()
    propre(at)
    assert at.sidebar.selectbox(key="ov_level").options == ["Préfecture"]
    assert at.sidebar.selectbox(key="ov_level").value == "Préfecture"


def test_bouton_reinitialiser():
    at = lancer("demographie")
    at.sidebar.selectbox(key="w_demographie_region").select("Kara")
    at.run()
    [b for b in at.sidebar.button if b.key == "reset_demographie"][0].click()
    at.run()
    assert at.sidebar.selectbox(key="w_demographie_region").value == "Toutes les régions"


def test_filtres_conserves_apres_interaction():
    at = lancer("services")
    at.sidebar.selectbox(key="w_services_region").select("Kara")
    at.run()
    at.session_state["sv_theme"] = "Agences CEET"
    at.run()
    at.selectbox(key="sv_ind_CEET").select("Agences ouvertes (nombre)")
    at.run()
    assert at.sidebar.selectbox(key="w_services_region").value == "Kara"
    assert at.session_state["sv_theme"] == "Agences CEET", "le thème choisi est conservé après un changement d'indicateur"


# ───────── cas sans données ─────────
def test_vide_demographie_recherche():
    at = lancer("demographie")
    at.text_input(key="demo_search").set_value("zzzzzz")
    at.run()
    propre(at)
    assert VIDE in textes(at)


def test_vide_evolution_aucune_fiabilite():
    at = lancer("evolution")
    at.sidebar.multiselect(key="w_evolution_comparabilite").set_value([])
    at.run()
    propre(at)
    assert VIDE in textes(at)


def test_vide_etat_civil_comparaison_periode_sans_annees_communes():
    at = lancer("etat_civil")
    at.session_state["ec_bloc"] = "Comparaison"
    at.sidebar.slider(key="w_etat_civil_periode").set_range(2020, 2022)
    at.run()
    propre(at)
    assert "Moins de deux années communes" in textes(at)


def test_vide_priorites_poids_nuls():
    at = lancer("priorites")
    at.session_state["pr_scen"] = "Personnalisé"
    for c in ("c1_deficit_acces", "c2_pop_sans_acces", "c3_croissance", "c4_stagnation_acces", "c5_deficit_equipement", "c6_absence_service"):
        at.session_state[f"pr_w_{c}"] = 0
    at.run()
    propre(at)
    assert "Aucune pondération" in textes(at)


def test_vide_priorites_filtre_sans_resultat():
    at = lancer("priorites")
    at.sidebar.selectbox(key="w_priorites_region").select("Savanes")
    at.run()
    at.sidebar.multiselect(key="w_priorites_classes").set_value(["Faible"])
    at.run()
    propre(at)                                                       # région Savanes sans unité « Faible » ou avec : l'important est l'absence d'erreur
    at.sidebar.multiselect(key="w_priorites_classes").set_value(["Très haute"])
    at.run()
    propre(at)


def test_vide_methode_recherche_journal():
    at = lancer("methode")
    at.session_state["me_sec"] = "Qualité & limites"
    at.run()
    at.text_input(key="me_search").set_value("zzzzzz")
    at.run()
    propre(at)
    assert VIDE in textes(at)


# ───────── valeurs manquantes affichées N/D (jamais zéro) ─────────
def test_evolution_non_comparables_affiches_nd():
    at = lancer("evolution")
    at.sidebar.multiselect(key="w_evolution_comparabilite").set_value(["HIGH", "MEDIUM", "LOW"])
    at.session_state["ev_mode"] = "Tableau"
    at.run()
    propre(at)
    t = textes(at)
    assert "Golfe" in t and "N/D" in t


def test_evolution_commune_non_comparable_message():
    at = lancer("evolution")
    at.session_state["ev_level"] = "Commune"
    at.run()
    propre(at)
    assert "Les communes n'existent pas en 2010" in textes(at)


def test_identite_2021_absent_signale():
    at = lancer("etat_civil")
    at.run()
    propre(at)
    assert "2021" in textes(at) and "absent" in textes(at)


# ───────── exports ─────────
@pytest.mark.parametrize("page", list(VIEWS))
def test_export_csv_disponible(page):
    at = lancer(page)
    assert any(b.proto.label in ("Exporter",) or "Exporter" in b.proto.label for b in at.get("download_button"))


def test_export_correspond_aux_filtres():
    from data import query as Q, loader as D
    f = dict(page="demographie", decoupage=D.DEC6, region_col="region_6", region="KARA", prefecture=None, commune=None, canton=None)
    lv = Q.demo_frame(f, "Préfecture")
    csv = Q.csv_bytes(lv[["Territoire", "Population"]]).decode("utf-8-sig")
    assert csv.count("\n") - 1 == len(lv) == 7 and "Golfe" not in csv


# ───────── performance (re-rendu à cache chaud, mesure côté serveur) ─────────
@pytest.mark.parametrize("page", list(VIEWS))
def test_re_rendu_sous_la_seconde_et_demie(page):
    at = lancer(page)
    t = time.perf_counter()
    at.run()
    assert time.perf_counter() - t < 1.5
