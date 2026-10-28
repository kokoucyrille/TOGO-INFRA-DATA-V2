"""Tests fonctionnels de la page « Services de base » après correction (KPI, export, filtres, périmètre cohérent)."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def lancer():
    return AppTest.from_file(str(ROOT / "views" / "services_base.py"), default_timeout=120).run()


def md(at):
    return " ".join(m.value for m in at.markdown)


def test_export_et_kpis_presents():
    at = lancer()
    assert not at.exception
    assert any("Exporter" in b.proto.label for b in at.get("download_button"))
    t = md(at)
    for libelle in ("Taux d'accès pondéré", "Agences ouvertes (CEET + TdE)", "Préfectures sans aucune agence"):
        assert libelle in t


@pytest.mark.parametrize("annee", [2018, 2019, 2020, 2021])
def test_toutes_les_annees_sans_erreur(annee):
    at = AppTest.from_file(str(ROOT / "views" / "services_base.py"), default_timeout=120).run()
    at.sidebar.selectbox(key="w_services_annee").select(annee).run()
    assert not at.exception
    assert f"Taux d'accès pondéré {annee}" in md(at)


def test_filtre_region_change_les_kpis_et_l_export():
    base = lancer()
    at = AppTest.from_file(str(ROOT / "views" / "services_base.py"), default_timeout=120).run()
    at.sidebar.selectbox(key="w_services_region").select("Kara").run()
    assert not at.exception
    import re
    n_base = int(re.search(r"(\d+)\s*sur\s*(\d+)</div>", md(base).split("Préfectures sans aucune agence")[1]).group(2))
    n_kara = int(re.search(r"(\d+)\s*sur\s*(\d+)</div>", md(at).split("Préfectures sans aucune agence")[1]).group(2))
    assert n_base == 39 and 0 < n_kara < n_base, "le périmètre des KPI doit se restreindre à la région choisie"
    assert any("Exporter" in b.proto.label for b in at.get("download_button"))


def test_2018_signale_la_prefecture_sans_taux():
    at = AppTest.from_file(str(ROOT / "views" / "services_base.py"), default_timeout=120).run()
    at.sidebar.selectbox(key="w_services_annee").select(2018).run()
    assert "sans taux publié" in md(at), "la limite (taux 2018 manquant pour une préfecture) doit être affichée"


def test_sidebar_etat_civil_ordre_et_reinitialisation():
    """Sidebar État civil & identité : période → état civil → identité → affichage → Réinitialiser ; le bouton remet tous les widgets par défaut."""
    at = AppTest.from_file(str(ROOT / "views" / "etat_civil_identite.py"), default_timeout=120).run()
    assert not at.exception
    side = " ".join(m.value for m in at.sidebar.markdown)
    positions = [side.index(x) for x in ("Période", "ÉTAT CIVIL · NAISSANCES", "IDENTITÉ · DOCUMENTS", "AFFICHAGE")]
    assert positions == sorted(positions), "ordre des sections de la sidebar"
    at.sidebar.multiselect(key="ec_types").set_value(["total"]).run()
    at.sidebar.button(key="reset_etat_civil").click().run()
    assert not at.exception
    assert at.sidebar.multiselect(key="ec_types").value == ["cni", "passeports"]
    assert at.sidebar.selectbox(key="ec_ind").index == 0, "l'indicateur d'état civil revient au premier choix"
