"""Étape 2 : réconciliation 54,5 % (pondéré population 2022) vs 57,82 % (publié). Recalcul INDÉPENDANT à partir du CSV brut (pandas/numpy, sans utils.reconciliation)."""
import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from utils import reconciliation as RC
from utils import services as SV
from utils.io import OUT, RAW
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def brut():
    e = pd.read_csv(RAW / "observationdata-puncgpd.csv", dtype=str, keep_default_na=False).rename(columns={"préfecture": "lieu", "libellés": "lib", "Date": "an", "Value": "v"})
    e = e[e.lieu != "LOME COMMUNE + GOLFE"]                    # doublon documenté de LOME
    e["an"] = e.an.astype(int); e["v"] = pd.to_numeric(e.v, errors="coerce")
    return e


def _pivot(e, lib):
    return e[e.lib.str.startswith(lib)].pivot(index="lieu", columns="an", values="v")


def test_taux_national_publie_reproduit_par_les_denominateurs_de_la_source(brut):
    ab, tx = _pivot(brut, "Nombre"), _pivot(brut, "Taux")
    unites = [u for u in ab.index if not u.startswith("REGION") and u != "ENSEMBLE DU PAYS"]
    for an, pub in ((2019, 50.3), (2020, 53.0)):
        a, t = ab.loc[unites, an], tx.loc[unites, an]
        assert a.sum() == ab.loc["ENSEMBLE DU PAYS", an], "les abonnés des unités somment au national"
        assert (a.sum() / (a / (t / 100)).sum() * 100) == pytest.approx(pub, abs=0.01)


def test_taux_regionaux_publies_reproduits_et_maritime_exclut_lome(brut):
    ab, tx = _pivot(brut, "Nombre"), _pivot(brut, "Taux")
    fb = pd.read_csv(OUT / "fact_unite_electrique_base.csv").set_index("unite_electrique")
    for nom, code in RC.REGIONS_PUBLIEES.items():
        us = [u for u in fb.index[fb.region_5 == code] if u != "LOME"]
        for an in (2019, 2020):
            r = ab.loc[us, an].sum() / (ab.loc[us, an] / (tx.loc[us, an] / 100)).sum() * 100
            assert r == pytest.approx(tx.loc[nom, an], abs=0.02), (nom, an)
    us = list(fb.index[fb.region_5 == "MARITIME"])                              # avec Lomé : ne correspond plus
    r = ab.loc[us, 2020].sum() / (ab.loc[us, 2020] / (tx.loc[us, 2020] / 100)).sum() * 100
    assert abs(r - tx.loc["REGION MARITIME", 2020]) > 10


def test_ecart_2021_et_taux_pondere_population_coherents_avec_la_page_services():
    fp = pd.read_csv(OUT / "fact_prefecture.csv")
    pond = SV.taux_pondere(fp, 2021)["valeur"]
    rn = pd.read_csv(OUT / "reconciliation_national.csv").set_index("scenario")
    assert rn.loc["S2", "taux_2021"] == pytest.approx(pond, abs=1e-6)
    assert rn.loc["S2", "ecart_2021"] == pytest.approx(pond - 57.82, abs=1e-6)
    assert round(pond, 1) == 54.5
    # recalcul indépendant : numpy sur les 33 unités
    fu = pd.read_csv(OUT / "fact_unite_electrique_base.csv")
    num = (np.minimum(fu.taux_2021, 100) * fu.population_2022).sum() / fu.population_2022.sum()
    assert num == pytest.approx(pond, abs=1e-6)


def test_scenarios_s6_a_s8_reproduisent_le_publie_et_s9_reste_nd():
    rn = pd.read_csv(OUT / "reconciliation_national.csv").set_index("scenario")
    assert abs(rn.loc["S6", "ecart_2019"]) < 0.01 and abs(rn.loc["S6", "ecart_2020"]) < 0.01
    assert abs(rn.loc["S7", "ecart_2018"]) < 0.1
    assert abs(rn.loc["S8", "ecart_2021"]) < 0.05
    assert rn.loc["S9", [f"taux_{a}" for a in RC.ANNEES]].isna().all(), "scénario non testable : N/D, jamais 0"
    for s in ("S1", "S2", "S3", "S4", "S5"):
        assert abs(rn.loc[s, "ecart_2021"]) > 2, f"{s} ne reproduit pas le taux publié"
    assert (rn.loc["P", [f"taux_{a}" for a in RC.ANNEES]] == pd.Series(RC.NATIONAL_PUBLIE).rename(lambda a: f"taux_{a}")).all()


def test_denominateur_implicite_part_de_la_population():
    rs = RC.resume_denominateur(pd.read_csv(OUT / "electricite_long.csv"), pd.read_csv(OUT / "fact_unite_electrique_base.csv"))
    assert 12.7 < rs[2020]["part_pop_2022_pct"] < 12.9


def test_moyenne_ponderee_exclut_les_absents_sans_les_compter_zero():
    t = pd.Series([50.0, np.nan, 150.0]); p = pd.Series([1.0, 5.0, 1.0])
    assert RC.moyenne_ponderee(t, p, 100) == pytest.approx(75.0)
    assert np.isnan(RC.moyenne_ponderee(pd.Series([np.nan]), pd.Series([1.0])))


def test_page_methode_affiche_le_bloc_reconciliation():
    at = AppTest.from_file(str(ROOT / "views" / "methode.py"), default_timeout=120).run()
    at.session_state["me_sec"] = "Réconciliation du taux"
    at.run()
    assert not at.exception, [e.value[:300] for e in at.exception]
    t = " ".join(m.value for m in at.markdown)
    assert "Scénarios testés" in t and "57,82" in t and "54,50" in t and "Ce qui reste inexpliqué" in t
