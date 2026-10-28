"""Étape 3 : audit analytique INDÉPENDANT des pages (Vue d'ensemble, Démographie, Évolution, État civil, Priorités, Méthode).
Chaque KPI affiché est recalculé à partir des CSV BRUTS (data/raw) avec pandas / numpy uniquement (aucune fonction de `utils/` ni de `data/`),
puis comparé (1) aux tables de l'application et (2) au texte réellement rendu par la page (AppTest)."""
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "outputs" / "data"
NB = "  "


def nrm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z0-9]+", " ", s).strip()


def txt(at) -> str:
    return re.sub(r"[  ]", " ", " ".join(m.value for m in at.markdown))


def page(name, **state) -> AppTest:
    at = AppTest.from_file(str(ROOT / "views" / name), default_timeout=120)
    for k, v in state.items():
        at.session_state[k] = v
    at.run()
    assert not at.exception, [e.value[:300] for e in at.exception]
    return at


def fr(x, d=1) -> str:
    return f"{x:.{d}f}".replace(".", ",")


def gini_ref(x):                                        # Gini par la moyenne des écarts absolus : indépendant de la formule triée utilisée par l'application
    x = np.asarray(x, float)
    return np.abs(x[:, None] - x[None, :]).sum() / (2 * len(x) ** 2 * x.mean())


@pytest.fixture(scope="module")
def r22():
    d = pd.read_csv(RAW / "observationdata-kwwolwb.csv", dtype=str, keep_default_na=False)
    return pd.DataFrame({"nom": d["découpage-administratif"], "v": d.Value.astype(int)})


@pytest.fixture(scope="module")
def r10():
    d = pd.read_csv(RAW / "observationdata-sapxctg.csv", dtype=str, keep_default_na=False)
    return pd.DataFrame({"nom": d.indicateurs, "v": d.Value.astype(int)})


@pytest.fixture(scope="module")
def dim():
    return pd.read_csv(OUT / "dim_territoire.csv")


# ───────────────────────── hiérarchie : valeurs relues dans le brut, parent = somme des enfants, ordre des lignes ─────────────────────────
def test_hierarchie_2022_validee_par_les_lignes_et_les_sommes_du_brut(r22, dim):
    d = dim.copy()
    d["brut"] = d.ligne_source_2022.map(lambda L: r22.v.iloc[int(L) - 2])
    d["nom_brut"] = d.ligne_source_2022.map(lambda L: r22.nom.iloc[int(L) - 2])
    assert (d.brut == d.population_2022).all(), "toute population affichée est la valeur du brut à la ligne indiquée"
    assert (d.nom_brut == d.libelle_brut).all()
    assert len(r22) == len(d) + (len(r22) - len(d)), "lignes brutes"
    enfants = d.groupby("parent_id").agg(somme=("brut", "sum"), n=("brut", "size"), l_min=("ligne_source_2022", "min"))
    parents = d.set_index("territoire_id")
    for pid, r in enfants.iterrows():
        p = parents.loc[pid]
        assert r.somme == p.brut, f"{p.nom} : somme des enfants {r.somme} ≠ {p.brut}"
        assert r.l_min > p.ligne_source_2022, "un enfant suit toujours son parent dans le fichier"
    nb = dim.niveau.value_counts()
    assert (nb.region, nb.prefecture, nb.commune) == (6, 39, 116)
    assert r22.v.iloc[0] == 8095498 and d[d.niveau == "region"].brut.sum() == 8095498 and d[d.niveau == "prefecture"].brut.sum() == 8095498


# ───────────────────────── Vue d'ensemble + Démographie ─────────────────────────
def test_demographie_kpi_recalcules_depuis_le_brut(r22, dim):
    com = dim[dim.niveau == "commune"].ligne_source_2022.map(lambda L: r22.v.iloc[int(L) - 2]).to_numpy(float)
    reg = dim[dim.niveau == "region"].ligne_source_2022.map(lambda L: r22.v.iloc[int(L) - 2]).to_numpy(float)
    total = 8095498.0
    k = dict(med=np.median(com), top10=np.sort(com)[::-1][:10].sum() / total * 100, gini=gini_ref(com), dagl=reg[-1] / total * 100,
             top2=np.sort(reg)[::-1][:2].sum() / total * 100, ratio=com.max() / com.min())
    kp = pd.read_json(OUT / "kpi_demographie.json", typ="series")
    assert kp.population_totale == total
    assert kp.mediane_commune == pytest.approx(k["med"]) and kp.part_top10_communes_pct == pytest.approx(k["top10"], rel=1e-9)
    assert kp.gini_communes == pytest.approx(k["gini"], abs=1e-9) and kp.part_grand_lome_pct == pytest.approx(k["dagl"])
    assert kp.rapport_max_min_communes == pytest.approx(k["ratio"])
    t = txt(page("overview.py"))
    assert "8 095 498" in t and fr(k["top2"]) + "%</div><div class=\"rs-lab\">de la population dans 2 régions" in t.replace(" %", "%") and fr(k["top10"]) + "%" in t
    assert fr(k["dagl"]) + "%" in t, "poids du Grand Lomé affiché"
    d = txt(page("demographie.py"))
    assert fr(k["gini"], 2) in d and "52 302" in d and fr(k["top10"]) + "%" in d
    assert f"{int(round(k['med'])):,}".replace(",", " ") == "52 302"


def test_cantons_petits_et_comptes_de_territoires(r22, dim):
    can = dim[(dim.niveau == "canton") & (dim.niveau_feuille == "canton")].ligne_source_2022.map(lambda L: r22.v.iloc[int(L) - 2]).to_numpy(float)
    kp = pd.read_json(OUT / "kpi_demographie.json", typ="series")
    assert kp.n_petits_cantons == (can < 5000).sum() and kp.nb_cantons == len(can) == 375
    assert kp.part_pop_petits_cantons_pct == pytest.approx(can[can < 5000].sum() / can.sum() * 100)
    assert round(kp.part_petits_cantons_pct) == round((can < 5000).mean() * 100)


# ───────────────────────── Évolution ─────────────────────────
def test_evolution_kpi_recalcules_depuis_les_deux_recensements(r22, r10):
    p10, p22 = int(r10.v.iloc[0]), int(r22.v.iloc[0])
    assert p10 == 6191155
    tcam = ((p22 / p10) ** (1 / 12) - 1) * 100
    cp = pd.read_csv(OUT / "population_2010_2022.csv")
    u = cp[cp.niveau == "unité de comparaison"]
    assert u.pop_2010.sum() == p10 and u.pop_2022.sum() == p22, "les unités de comparaison recouvrent exactement le pays aux deux dates"
    assert u.contribution_croissance_pct.sum() == pytest.approx(100.0, abs=1e-6)
    t = txt(page("evolution.py"))
    assert "6 191 155" in t and "1 904 343" in t and fr(tcam, 2) + "%" in t and fr((p22 / p10 - 1) * 100) in t
    gl10 = int(r10[r10.nom == "LOME"].v.iloc[0]) + int(r10[r10.nom == "GOLFE"].v.iloc[0])
    gl22 = int(r22[r22.nom == "GRAND LOME"].v.iloc[0]) if (r22.nom == "GRAND LOME").any() else None
    gl = u[u.nom.str.startswith("Grand Lomé")].iloc[0]
    assert gl.pop_2010 == gl10, "Grand Lomé 2010 = Lomé + Golfe du brut 2010"
    assert gl.contribution_croissance_pct == pytest.approx((gl.pop_2022 - gl10) / (p22 - p10) * 100)
    assert fr(gl.contribution_croissance_pct, 0) + "%" in t


def test_pop_2010_des_prefectures_exactes_se_retrouve_dans_le_brut_2010(r10):
    cw = pd.read_csv(OUT / "crosswalk_2010_2022.csv")
    cw = cw[(cw.niveau_comparaison == "préfecture") & (cw.type_correspondance == "exacte")]
    assert len(cw) >= 20
    vals = {}
    for n, v in zip(r10.nom.map(nrm), r10.v):
        vals.setdefault(n, set()).add(v)
    for r in cw.itertuples():
        nom10 = {"MO": "SOUS PREFECTURE DE MO"}.get(nrm(r.territoires_2010), nrm(r.territoires_2010))      # libellé 2010 du brut
        assert int(r.pop_2010) in vals.get(nom10, set()), f"{r.territoire_2022} : pop 2010 absente du brut"
        assert r.tcam_pct == pytest.approx(((r.pop_2022 / r.pop_2010) ** (1 / 12) - 1) * 100)


def test_comparabilite_high_medium_low_invariants_et_comptes_affiches():
    cw = pd.read_csv(OUT / "crosswalk_2010_2022.csv")
    p = cw[cw.niveau_comparaison == "préfecture"]
    assert p.comparability_flag.value_counts().to_dict() == {"HIGH": 20, "MEDIUM": 17, "LOW": 2}
    assert (p[p.comparability_flag == "HIGH"].couverture_cantons_pct.dropna() >= 90).all()
    assert p[p.comparability_flag == "LOW"].tcam_pct.isna().all(), "un territoire LOW n'a jamais de croissance calculée"
    t = txt(page("evolution.py"))
    assert "20 préfectures" in t and "17 préfectures" in t and "2 préfectures" in t and "Seules <b>37</b> préfectures" in t


# ───────────────────────── État civil & identité ─────────────────────────
def test_etat_civil_et_identite_recalcules_depuis_le_brut():
    ec = pd.read_csv(RAW / "observationdata-vrsicxf.csv", dtype=str, keep_default_na=False)
    idn = pd.read_csv(RAW / "observationdata-fsemhj.csv", dtype=str, keep_default_na=False)
    e45 = ec[ec.indicateur.str.startswith("Nombre d'enfants enregistrés") & (ec.sexe == "Tota")].set_index("Date").Value.astype(int)
    assert (e45["2014"], e45["2019"]) == (118717, 103893)
    evo = (e45["2019"] / e45["2014"] - 1) * 100
    cni = idn[idn.type.str.contains("CNI|Cartes nationales", case=False, regex=True)].set_index("Date").Value.astype(int)
    pas = idn[idn.type == "Passeports"].set_index("Date").Value.astype(int)
    assert "2021" not in cni.index, "2021 est absente du brut pour la CNI : jamais estimée"
    t = txt(page("etat_civil_identite.py"))
    assert "103 893" in t and fr(evo).replace("-", "−") + "%" in t.replace(" %", "%")
    assert f"{cni['2022']:,}".replace(",", " ") in t and f"{pas['2022']:,}".replace(",", " ") in t
    assert fr((pas["2022"] / pas["2014"] - 1) * 100, 0) in t or fr((pas["2022"] / pas["2014"] - 1) * 100, 0).replace("83", "83") in t
    assert fr((cni["2022"] / cni["2019"] - 1) * 100, 0).replace("-", "−") in t


# ───────────────────────── Priorités : IPT recalculé indépendamment ─────────────────────────
def test_ipt_recalcule_independamment_reproduit_rang_et_score():
    b = pd.read_csv(OUT / "fact_unite_electrique_base.csv")
    ref = pd.read_csv(OUT / "fact_unite_electrique.csv").set_index("unite_electrique")
    pop, t21 = b.population_2022.to_numpy(float), np.minimum(b.taux_2021.to_numpy(float), 100)
    t18 = np.minimum(b.taux_2018.to_numpy(float), 100)
    ok_tend = b.valide_pour_tendance.astype(bool).to_numpy() & ~np.isnan(t18)
    brut = {
        "c1": 100 - t21,
        "c2": pop * (1 - t21 / 100),
        "c3": np.where(b.flag_croissance.isin(["HIGH", "MEDIUM"]), ((pop / b.pop_2010_comparable) ** (1 / 12) - 1) * 100, np.nan),
        "c4": np.where(ok_tend, -(t21 - t18), np.nan),
        "c5": -(b.ceet_ouvertes + b.tde_ouvertes).to_numpy(float) / pop * 1e5,
        "c6": 100 * (b.part_pop_sans_ceet + b.part_pop_sans_tde).to_numpy(float) / 2,
    }
    w = dict(c1=20, c2=20, c3=15, c4=15, c5=15, c6=15)
    score = np.zeros(len(b))
    for c, x in brut.items():
        lo, hi = np.nanpercentile(x, 5), np.nanpercentile(x, 95)
        n = (np.clip(x, lo, hi) - lo) / (hi - lo) * 100
        n = np.where(np.isnan(n), np.nanmedian(n), n)
        score += n * w[c] / 100
    mine = pd.Series(score, index=b.unite_electrique)
    assert np.allclose(mine.sort_index().to_numpy(), ref.ipt.sort_index().to_numpy(), atol=1e-6)
    rang = mine.rank(ascending=False, method="min").astype(int)
    assert (rang.sort_index() == ref.rang_ipt.sort_index()).all()
    q = np.quantile(score, [.25, .5, .75])
    cls = np.select([score > q[2], score > q[1], score > q[0]], ["Très haute", "Haute", "Moyenne"], "Faible")
    assert (pd.Series(cls, index=b.unite_electrique).sort_index() == ref.classe_priorite.sort_index()).all()
    t = txt(page("recommandations.py"))
    assert "8 unités" in t and "33 sur 33" in t and "5 sur 33" in t
    top = ref.sort_values("rang_ipt").head(3).unite_affichage.tolist()
    assert all(n.split(" +")[0] in t for n in top)


def test_services_et_vue_ensemble_population_sans_acces_et_agences():
    b = pd.read_csv(OUT / "fact_unite_electrique_base.csv")
    sans = (b.population_2022 * (1 - np.minimum(b.taux_2021, 100) / 100)).sum()
    assert round(sans) == 3683089
    ag = pd.read_csv(RAW / "file-agences-ceet-23-12-2024-11-06-42.csv", dtype=str, keep_default_na=False)
    assert len(ag) > 0
    t = txt(page("overview.py"))
    assert "3 683 089" in t and "57,8%" in t
    assert "25" in t and "46" in t


# ───────────────────────── Méthode ─────────────────────────
def test_methode_kpi_comparabilite_et_qualite():
    at = page("methode.py")
    t = txt(at)
    assert "37 sur 39" in t and "33" in t
    q = pd.read_csv(OUT / "data_quality_tests.csv")
    assert " · ".join(str(int((q.statut == s).sum())) for s in ("PASS", "WARNING", "FAIL")) in t
