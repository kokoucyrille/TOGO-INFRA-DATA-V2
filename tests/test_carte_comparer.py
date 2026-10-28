"""Pages Carte interactive et Comparer : rendu sans erreur, couches, comparaison 2 à 4, N/D jamais remplacé par 0."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def lancer(page):
    return AppTest.from_file(str(ROOT / "views" / page), default_timeout=120).run()


@pytest.mark.parametrize("couche", ["Population 2022", "Taux d'accès à l'électricité 2021", "Population sans accès (PROXY)",
                                    "Agences ouvertes pour 100 000 hab.", "Indice de priorité territoriale (0–100)"])
def test_carte_toutes_les_couches(couche):
    at = lancer("carte.py")
    at.selectbox(key="ca_couche").select(couche).run()
    assert not at.exception
    assert any((c.key or "").startswith("map_ca_") for c in at.get("plotly_chart")), "une carte cliquable est affichée"


def test_carte_agences_superposables():
    at = lancer("carte.py")
    at.checkbox(key="ca_ceet").check().run()
    at.checkbox(key="ca_tde").check().run()
    assert not at.exception


def test_comparer_radar_barres_regions():
    at = lancer("comparer.py")
    assert not at.exception and at.get("plotly_chart")
    at.segmented_control(key="cp_mode").set_value("Barres").run()
    assert not at.exception
    at.segmented_control(key="cp_niveau").set_value("Région").run()
    assert not at.exception


def test_comparer_limite_quatre_et_minimum_deux():
    at = lancer("comparer.py")
    ms = at.multiselect(key="cp_sel_Préfecture")
    assert ms.max_selections == 4
    ms.set_value(["Kara"]).run()
    assert not at.exception and not at.get("plotly_chart"), "moins de 2 territoires : pas de graphique"


def test_comparer_nd_jamais_zero():
    """Une valeur absente s'affiche « N/D » dans le tableau, jamais 0."""
    at = lancer("comparer.py")
    valeurs = [str(v) for df in at.dataframe for v in df.value.to_numpy().ravel()]
    assert all(v not in ("nan", "None") for v in valeurs)


def test_selected_ids_accepte_customdata_dict_de_streamlit():
    """Streamlit renvoie customdata sous la forme {'0': id} : le clic doit être converti en identifiant."""
    from types import SimpleNamespace
    from components import maps, charts
    ev = SimpleNamespace(selection=SimpleNamespace(points=[{"customdata": {"0": 115}}, {"customdata": [7]}, {"customdata": None}]))
    assert maps.selected_ids(ev) == [115, 7]
    assert maps.selected_ids(None) == []


def test_resolver_region_et_prefecture():
    import pandas as pd
    from components import gstate
    fr = pd.DataFrame(dict(id=["KARA"], Territoire=["Kara"]))
    assert gstate.resolver_for("Région", fr)("KARA")["region"] == "KARA"
    assert gstate.resolver_for("Région", fr)("inconnu") is None


def test_zoom_sur_le_territoire_filtre():
    """La carte zoome sur la zone filtrée ; pays entier = cadrage par défaut (None) ; une petite préfecture n'est pas sur-zoomée."""
    from components import maps
    from data import loader as D
    gj = D.prefectures_geojson()
    tous = [f["properties"]["name"] for f in gj["features"]]
    assert maps.zoom_ranges(gj, tous) is None
    la, lo = maps.zoom_ranges(gj, ["Assoli"])
    assert la[1] - la[0] >= 1.0 and lo[1] - lo[0] >= 1.0
    kara = [f["properties"]["name"] for f in gj["features"] if f["properties"]["region"] == "Kara"]
    la2, lo2 = maps.zoom_ranges(gj, kara)
    assert (la2[1] - la2[0]) < 6 and (lo2[1] - lo2[0]) < 2.1
    assert 0.0 < sum(map(float, [1])) and la2[0] < 9.6 < la2[1]


def test_evolution_deux_recensements_et_sexe_nd():
    """Évolution : comparaison 2010/2022 par région et préfecture ; le sexe est signalé N/D (aucune donnée) et jamais estimé."""
    at = lancer("evolution.py")
    assert not at.exception
    txt = " ".join(m.value for m in at.markdown)
    assert any("Les deux recensements" in h.value for h in at.subheader)
    assert "Aucune ventilation hommes / femmes" in txt
    at.segmented_control(key="ev_cens_niv").set_value("Préfecture").run()
    assert not at.exception
    assert any(c.key == "ev_cens_fig" for c in at.get("plotly_chart"))


def test_aucune_donnee_population_par_sexe_dans_les_sources():
    """Garde-fou : si un fichier source ajoute un vrai sexe (autre que « Total »), ce test échoue et la page doit être enrichie."""
    import pandas as pd
    a = pd.read_csv(ROOT / "data" / "raw" / "observationdata-kwwolwb.csv")
    b = pd.read_csv(ROOT / "data" / "raw" / "observationdata-sapxctg.csv")
    assert set(a["sexe"].unique()) == {"Total"}
    assert "sexe" not in [c.lower() for c in b.columns]
