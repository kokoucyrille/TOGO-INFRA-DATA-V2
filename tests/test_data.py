"""Invariants des tables, de l'indice de priorité, du récit calculé et de la sécurité d'affichage (indépendants de l'interface)."""
import numpy as np
import pandas as pd
import pytest

from components.tables import create_table
from data import loader as D
from utils import story
from utils.contrast import ratio
from utils.formats import ND, fmt_dec, fmt_int, fmt_pct
from utils.io import OUT
from utils.priority import CODES, SCENARIOS, SCENARIO_DEFAUT, compute_ipt, correlation_composantes, robustesse

NAT = 8_095_498


@pytest.fixture(scope="module")
def T():
    return D.load_tables()


# ───────── cohérence des tables ─────────
def test_populations_somment_au_total_national(T):
    assert T["commune"].population_2022.sum() == NAT
    assert T["prefecture"].population_2022.sum() == NAT
    assert T["unite"].population_2022.sum() == NAT


def test_33_unites_couvrent_39_prefectures(T):
    assert len(T["unite"]) == 33 and int(T["unite"].n_prefectures.sum()) == 39 and len(T["prefecture"]) == 39


def test_agences_ouvertes_coherentes_entre_fichier_et_tables(T):
    ouvertes = int(T["agences"].ouverte_public.sum())
    assert ouvertes == int(T["prefecture"].agences_ouvertes_total.sum()) == int(T["unite"].agences_ouvertes_total.sum()) == 71


def test_population_sans_acces_est_un_proxy_borne(T):
    u = T["unite"]
    assert ((u.pop_sans_acces_2021 >= 0) & (u.pop_sans_acces_2021 <= u.population_2022)).all()


def test_aucune_valeur_inventee_ni_remplacee_par_zero(T):
    p = T["prefecture"]
    assert p[p.ceet_ouvertes == 0].ceet_hab_par_agence.isna().all(), "habitants par agence = N/D (pas 0) quand aucune agence"
    low = T["crosswalk"][T["crosswalk"].comparability_flag == "LOW"]
    assert low.pop_2010.isna().all() and low.tcam_pct.isna().all()


def test_les_low_ne_sont_jamais_classes(T):
    cp = T["comparaison"]
    assert not cp[cp.comparability_flag == "LOW"].classement_autorise.any()
    assert not T["crosswalk"][T["crosswalk"].comparability_flag == "LOW"].dans_classement.any()


def test_partition_comparable_somme_aux_deux_recensements(T):
    u = T["comparaison"].query("niveau == 'unité de comparaison'")
    assert u.pop_2010.sum() == 6_191_155 and u.pop_2022.sum() == NAT and abs(u.contribution_croissance_pct.sum() - 100) < 1e-9


def test_tous_les_polygones_se_rattachent_aux_39_prefectures():
    mp = D.polygons_of_prefecture()
    assert len(mp) == 39 and len(mp["GOLFE"]) == 2


def test_pas_de_donnees_de_demonstration():
    from pathlib import Path
    assert not (Path(D.ROOT) / "data" / "data.py").exists(), "le module de données fictives du gabarit doit avoir disparu"


# ───────── indice de priorité ─────────
def test_poids_des_scenarios_somment_a_100():
    assert all(abs(sum(w.values()) - 100) < 1e-9 for w in SCENARIOS.values())


def test_ipt_borne_rang_et_classes(T):
    r = compute_ipt(T["unite"], SCENARIOS[SCENARIO_DEFAUT])
    assert r.ipt.between(0, 100).all() and sorted(r.rang_ipt) == sorted(r.ipt.rank(ascending=False, method="min").astype(int))
    assert set(r.classe_priorite) <= {"Très haute", "Haute", "Moyenne", "Faible"} and len(r) == 33
    assert abs((r.classe_priorite == "Très haute").sum() - 33 / 4) <= 2


def test_ipt_invariant_a_l_echelle_des_poids(T):
    a = compute_ipt(T["unite"], SCENARIOS[SCENARIO_DEFAUT]).ipt
    b = compute_ipt(T["unite"], {k: v * 7 for k, v in SCENARIOS[SCENARIO_DEFAUT].items()}).ipt
    assert np.allclose(a, b)


def test_poids_nuls_refuses(T):
    with pytest.raises(ValueError):
        compute_ipt(T["unite"], {c: 0 for c in CODES})


def test_valeur_neutre_pour_croissance_non_comparable(T):
    r = compute_ipt(T["unite"], SCENARIOS[SCENARIO_DEFAUT])
    low = r[r.flag_croissance == "LOW"]
    assert len(low) >= 2 and low.neutre_c3.all()
    ref = r[~r.neutre_c3].c3_croissance_norm.median()
    assert np.allclose(low.c3_croissance_norm, r.c3_croissance_norm[r.neutre_c3].iloc[0])      # même valeur neutre pour tous


def test_robustesse_reproductible_graine_42(T):
    a, b = robustesse(T["unite"], n_tirages=60), robustesse(T["unite"], n_tirages=60)
    assert a.equals(b) and a.priority_stability_score.between(0, 100).all()


def test_stabilite_stockee_correspond_au_calcul(T):
    assert (T["rob"].stabilite == "robuste").sum() == (T["rob"].priority_stability_score >= 80).sum()


def test_correlation_verdict_present(T):
    assert correlation_composantes(T["unite"])["verdict"]


# ───────── récit calculé ─────────
def test_phrases_dynamiques_correspondent_aux_donnees(T):
    n = int((T["prefecture"].taux_plaf_2021 < 57.82).sum())
    assert story.phrase_sous_moyenne(T["prefecture"]).startswith(f"{n} préfectures sur 39")
    top10 = T["commune"].nlargest(10, "population_2022").population_2022.sum() / NAT * 100
    assert fmt_pct(top10) in story.phrase_top_communes(T["commune"], 10)


def test_messages_cles_et_recommandations_sont_tracables(T):
    msgs = story.messages_cles(T["unite"], T["prefecture"], T["commune"], T["kpi"], T["rob"], T["comparaison"], T["idn"])
    assert len(msgs) == 10 and all(m["constat"] and m["preuve"] and m["implication"] for m in msgs)
    reco = T["reco"]
    for c in ("Territoire", "Problème", "Indicateur", "Valeur", "Priorité", "Recommandation", "Horizon", "KPI de suivi", "Preuve"):
        assert c in reco.columns and reco[c].notna().all()
    assert not reco.Recommandation.str.contains("améliorer les infrastructures", case=False).any(), "pas de recommandation générique"


def test_formats_francais_et_nd():
    assert fmt_int(19788) == "19\u00a0788" and fmt_dec(72.34, 1) == "72,3"
    assert fmt_int(np.nan) == ND and fmt_pct(None) == ND


# ───────── sécurité d'affichage ─────────
def test_les_tableaux_echappent_le_html():
    h = create_table(pd.DataFrame({"A": ["<script>alert(1)</script>"], "B": ["<b>sûr</b>"]}), raw_cols=("B",))
    assert "<script>" not in h and "&lt;script&gt;" in h and "<b>sûr</b>" in h


# ───────── charte : le texte courant atteint 4,5 : 1 ; les couleurs faibles du gabarit ne servent pas de texte ─────────
@pytest.mark.parametrize("txt,fond", [("#1e3a4c", "#f7fcfe"), ("#1e3a4c", "#ffffff"), ("#003f8c", "#ffffff"), ("#0a5ec0", "#ffffff"), ("#ffffff", "#016b4b"), ("#004f31", "#fdcf00"),
                                       ("#004f31", "#e1f3ea"), ("#5f4300", "#fff3c4"), ("#34424c", "#eceff1"), ("#8f0b24", "#fdebef"), ("#6e3600", "#ffeed8"), ("#554200", "#fff8d6"),
                                       ("#c4102f", "#ffffff"), ("#4f6270", "#ffffff"), ("#a30d27", "#ffffff"), ("#6b4a00", "#ffffff")])
def test_contraste_texte_conforme(txt, fond):
    assert ratio(txt, fond) >= 4.5


def test_couleurs_faibles_du_gabarit_documentees():
    assert ratio("#fdcf00", "#ffffff") < 4.5 and ratio("#a2b8cc", "#ffffff") < 4.5 and ratio("#f20e36", "#ffffff") < 4.5    # jamais utilisées comme couleur de texte sur blanc
