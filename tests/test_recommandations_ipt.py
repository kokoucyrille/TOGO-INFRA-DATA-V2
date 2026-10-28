"""Étape 1 : les recommandations et les textes de synthèse découlent MÉCANIQUEMENT du classement IPT (cohérence territoire ↔ classe / rang / robustesse)."""
import pandas as pd
import pytest

from utils import story
from utils.io import OUT


@pytest.fixture(scope="module")
def fu():
    return pd.read_csv(OUT / "fact_unite_electrique.csv")


@pytest.fixture(scope="module")
def reco():
    return pd.read_csv(OUT / "recommandations.csv")


def test_reco_coherentes_avec_le_classement_ipt(reco, fu):
    assert story.verifier_coherence_reco(reco, fu) == []


def test_toutes_les_unites_tres_haute_sont_recommandees_dans_l_ordre(reco, fu):
    th = fu[fu.classe_priorite == "Très haute"].sort_values("rang_ipt")
    ipt_rows = reco[reco.Type == "Priorité IPT"]
    assert list(ipt_rows.Territoire) == list(th.unite_affichage)
    assert list(ipt_rows["Rang IPT"].astype(int)) == list(th.rang_ipt)
    assert len(th) == 8


def test_les_5_unites_robustes_du_haut_du_classement_sont_citees(reco, fu):
    robustes = fu[(fu.classe_priorite == "Très haute") & (fu.stabilite == "robuste")]
    assert len(robustes) == 5
    cites = reco[(reco.Type == "Priorité IPT") & (reco.Statut == story.LIB_ROBUSTE)].Territoire
    assert set(cites) == set(robustes.unite_affichage)
    for nom in ("Dankpen", "Est-Mono", "Tandjoaré"):
        assert nom in set(reco.Territoire), f"{nom} (très haute priorité) doit figurer dans les recommandations"


def test_haho_moyen_mono_n_est_pas_presente_comme_priorite_robuste(reco, fu):
    h = fu[fu.unite_affichage == "Haho + Moyen-Mono"].iloc[0]
    assert h.classe_priorite != "Très haute" and h.stabilite == "sensible"
    assert "Haho + Moyen-Mono" not in set(reco[reco.Type == "Priorité IPT"].Territoire)


def test_chaque_ligne_ipt_a_les_champs_demandes(reco):
    d = reco[reco.Type == "Priorité IPT"]
    for c in ("Problème", "Valeur", "Population concernée", "Recommandation", "Horizon", "KPI de suivi", "Preuve"):
        assert d[c].notna().all() and (d[c].astype(str).str.len() > 3).all(), c
    assert d.Preuve.str.contains("taux_plaf_2021=").all() and d.Preuve.str.contains("priority_stability_score=").all()
    assert (d.loc[d.Robustesse == "robuste", "Recommandation"].str.contains("agir sans regret")).all()
    assert (d.loc[d.Robustesse == "sensible", "Recommandation"].str.contains("à confirmer")).all()


# ---- le validateur DOIT échouer sur des recommandations incohérentes ----
def test_validateur_detecte_une_unite_hors_top_citee_comme_priorite(reco, fu):
    mauvais = reco.copy()
    i = mauvais.index[mauvais.Type == "Priorité IPT"][0]
    mauvais.loc[i, ["Territoire", "Unité IPT"]] = ["Haho + Moyen-Mono", fu[fu.unite_affichage == "Haho + Moyen-Mono"].unite_electrique.iloc[0]]
    assert story.verifier_coherence_reco(mauvais, fu)


def test_validateur_detecte_un_rang_ou_une_robustesse_faux(reco, fu):
    mauvais = reco.copy()
    i = mauvais.index[mauvais.Type == "Priorité IPT"][5]            # Kpélé : sensible
    mauvais.loc[i, "Statut"] = story.LIB_ROBUSTE
    assert any("sans regret" in e.lower() or "attribué" in e for e in story.verifier_coherence_reco(mauvais, fu))
    mauvais = reco.copy()
    mauvais.loc[mauvais.index[mauvais.Type == "Priorité IPT"][0], "Rang IPT"] = 11
    assert story.verifier_coherence_reco(mauvais, fu)


def test_validateur_detecte_une_ligne_complementaire_qui_revendique_une_classe(reco, fu):
    mauvais = reco.copy()
    i = mauvais.index[mauvais.Territoire == "Golfe"][0]
    mauvais.loc[i, "Priorité"] = "Haute"
    assert story.verifier_coherence_reco(mauvais, fu)


def test_synthese_mecanique_et_messages(fu):
    syn = story.synthese_priorites(fu)
    assert syn["n"] == 8 and syn["n_robustes"] == 5 and syn["n_sensibles"] == 3
    assert syn["robustes"][0] == "Kpendjal-Ouest + Kpendjal"
    phrase = story.phrase_synthese_priorites(syn)
    for nom in syn["noms"][:5]:
        assert nom in phrase
    msgs = story.messages_cles(fu, pd.read_csv(OUT / "fact_prefecture.csv"), pd.read_csv(OUT / "fact_commune.csv"), __import__("json").loads((OUT / "kpi_demographie.json").read_text()),
                               pd.read_csv(OUT / "ipt_robustesse.csv"), pd.read_csv(OUT / "population_2010_2022.csv"), pd.read_csv(OUT / "identite_long.csv"))
    texte = " ".join(m["constat"] + m["preuve"] for m in msgs)
    assert "5 robuste" in texte and "Dankpen" in texte and "Est-Mono" in texte
    m4 = next(m for m in msgs if m["constat"].startswith("Le nombre de personnes sans accès"))
    assert "rang IPT" in m4["preuve"], "le volume sans accès est toujours cité avec le rang IPT de l'unité"
