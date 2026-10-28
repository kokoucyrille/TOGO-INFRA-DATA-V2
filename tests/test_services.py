"""Tests des indicateurs « Services de base » : formules vérifiées par une méthode indépendante (numpy / recalcul manuel / totaux sources)."""
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from utils import services as SV

ROOT = Path(__file__).resolve().parents[1]
FP = pd.read_parquet(ROOT / "outputs" / "data" / "fact_prefecture.parquet")


def test_taux_pondere_recalcul_manuel():
    df = pd.DataFrame({"population_2022": [100.0, 300.0, 600.0], "taux_2021": [50.0, 100.0, 20.0]})
    r = SV.taux_pondere(df, 2021)
    assert r["valeur"] == pytest.approx((100 * 50 + 300 * 100 + 600 * 20) / 1000)      # 47,0 : 100 × 0,5 + 300 × 1 + 600 × 0,2
    assert r["pop_couverte"] == 1000 and r["n_sans_taux"] == 0


def test_taux_pondere_plafonne_et_exclut_les_manquants():
    df = pd.DataFrame({"population_2022": [100.0, 100.0, 800.0], "taux_2021": [110.0, 50.0, np.nan]})
    r = SV.taux_pondere(df, 2021)
    assert r["valeur"] == pytest.approx(75.0), "110 plafonné à 100 ; le manquant n'entre ni au numérateur ni au dénominateur"
    assert r["n_plafonnes"] == 1 and r["n_sans_taux"] == 1 and r["pop_couverte"] == 200


@pytest.mark.parametrize("df", [pd.DataFrame({"population_2022": [], "taux_2021": []}), pd.DataFrame({"population_2022": [10.0], "taux_2021": [np.nan]})])
def test_taux_pondere_cas_limites_sans_division_par_zero(df):
    assert SV.taux_pondere(df, 2021)["valeur"] is None


def test_taux_pondere_different_de_la_moyenne_simple_sur_les_donnees_reelles():
    """Régression P0 : la moyenne simple des préfectures (34,5 % en 2021) sous-estimait fortement le taux (≈ 54,5 % pondéré)."""
    r = SV.taux_pondere(FP, 2021)["valeur"]
    simple = FP.taux_2021.mean()
    assert r - simple > 15
    w = FP.population_2022.to_numpy(); t = np.minimum(FP.taux_2021.to_numpy(), 100)
    assert r == pytest.approx(float((w * t).sum() / w.sum()))                          # méthode distincte (numpy)
    assert abs(r - SV.TAUX_NATIONAL[2021]) < 5, "cohérent avec le taux national publié (écart documenté : dénominateur de la source inconnu)"


def test_population_sans_acces_reconstitue_la_population_totale():
    sans = SV.population_sans_acces(FP, 2021)
    avec = FP.population_2022 * FP.taux_2021.clip(upper=100) / 100
    assert (sans + avec).sum() == pytest.approx(FP.population_2022.sum())               # sans + avec = population (aucun taux manquant en 2021)
    assert (sans >= 0).all()


def test_population_sans_acces_manquant_reste_nan():
    s = SV.population_sans_acces(FP, 2018)
    assert s.isna().sum() == FP.taux_2018.isna().sum() == 1


def test_population_sans_acces_somme_regions_egale_somme_prefectures():
    par_region = SV.population_sans_acces(FP, 2021).groupby(FP.region_6).sum()
    assert par_region.sum() == pytest.approx(SV.population_sans_acces(FP, 2021).sum())


def test_score_deficit_croise_borne_et_monotone():
    sc = SV.score_deficit_croise(FP, 2021)
    assert len(sc) == 39 and sc.between(0, 100).all()
    i_best = FP.taux_2021.clip(upper=100).idxmax(); i_worst = FP.taux_2021.clip(upper=100).idxmin()
    assert sc.iloc[i_worst] > sc.iloc[i_best], "meilleur accès → déficit plus faible"


def test_agences_total_egale_somme_ceet_tde():
    assert (FP.agences_ouvertes_total == FP.ceet_ouvertes + FP.tde_ouvertes).all()
    assert int(FP.agences_ouvertes_total.sum()) == 71, "71 agences ouvertes (rapprochement avec les fichiers sources, cf. test_data)"


def test_toutes_les_icones_utilisees_existent_dans_les_polices_embarquees():
    css = (ROOT / "assets" / "embedded_fonts.css").read_text(encoding="utf-8")
    used = set()
    for d in ("views", "components", "utils"):
        for f in (ROOT / d).glob("*.py"):
            used |= set(re.findall(r"fa-[a-z0-9]+(?:-[a-z0-9]+)*", f.read_text(encoding="utf-8")))
    used.discard("fa-solid")
    manquantes = sorted(i for i in used if i not in css)
    assert not manquantes, f"icônes absentes du sous-ensemble embarqué (affichage vide) : {manquantes}"


def test_agences_ouvertes_rapprochees_des_fichiers_bruts():
    """Contrôle indépendant : recompte direct dans les CSV bruts (statut {Utilise} et catégorie « Agence » hors Admin/Technique)."""
    raw = ROOT / "data" / "raw"
    ceet = pd.read_csv(raw / "file-agences-ceet-23-12-2024-11-06-42.csv")
    tde = pd.read_csv(raw / "file-agences-togolaise-des-eaux-tde-19-12-2024-17-48-23.csv")
    n_ceet = int(((ceet.activite_statut == "{Utilise}") & (ceet.activite_categorie == "Agence CEET")).sum())
    n_tde = int(((tde.activite_statut == "{Utilise}") & (tde.activite_categorie == "Agence TdE")).sum())
    assert (n_ceet, n_tde) == (int(FP.ceet_ouvertes.sum()), int(FP.tde_ouvertes.sum())) == (25, 46)
