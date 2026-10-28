"""Graphique « Contribution des composantes » : légende séparée du graphique, totaux cohérents avec le score."""
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from components import charts

ROOT = Path(__file__).resolve().parents[1]
COMPS = {f"c{i}": (f"Composante {i}",) for i in range(1, 7)}
W = {f"c{i}": 10 * i for i in range(1, 7)}
DF = pd.DataFrame({"lab": ["A", "B"], **{f"c{i}_norm": [20.0 * i % 100, 50.0] for i in range(1, 7)}})


def test_graphique_sans_legende_integree_et_totaux_corrects():
    fig = charts.create_stacked_components(DF, "lab", COMPS, W, 120)
    assert fig.layout.showlegend is False
    bars = [t for t in fig.data if t.type == "bar"]
    assert len(bars) == 6
    wsum = sum(W.values())
    attendu = [sum(DF.loc[i, f"c{k}_norm"] * W[f"c{k}"] / wsum for k in range(1, 7)) for i in range(2)]
    texte = [t for t in fig.data if t.type == "scatter"][0]
    assert [float(x) for x in texte.x] == pytest.approx(attendu), "le total affiché = somme des segments"


def test_legende_html_liste_toutes_les_composantes():
    h = charts.stacked_legend(COMPS, W)
    assert h.count("cmp-leg-item") == 6 and all(f"Composante {i}" in h for i in range(1, 7))
    assert "10 %" in h or "5 %" in h
    hv = charts.stacked_legend(COMPS, W, values={f"c{i}": 1.5 for i in range(1, 7)})
    assert "1.5 pts" in hv


def test_page_priorites_affiche_graphiques_et_legendes():
    at = AppTest.from_file(str(ROOT / "views" / "recommandations.py"), default_timeout=120).run()
    assert not at.exception
    html = " ".join(m.value for m in at.markdown)
    assert html.count('class="cmp-legend"') == 2, "une légende pour le classement, une pour la fiche territoire"
    assert "contribution des composantes au score de" in html
