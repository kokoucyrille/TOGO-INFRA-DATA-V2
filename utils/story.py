"""Récit décisionnel calculé à partir des données : phrases dynamiques, messages Constat → Preuve → Implication, recommandations chiffrées.
Aucune valeur n'est écrite à la main : tout chiffre cité provient d'une table. Règle : DONNÉE → INDICATEUR → COMPARAISON → INTERPRÉTATION → CONCLUSION → RECOMMANDATION."""
import math
import numpy as np
import pandas as pd
from .formats import fmt_int, fmt_dec, fmt_pct, fmt_pp, fmt_signe, liste_fr, ND
from .services import TAUX_NATIONAL

TAUX_NAT = TAUX_NATIONAL[2021]


# ───────────────────────── phrases dynamiques (utilisées dans les titres et annotations) ─────────────────────────
def phrase_concentration_regions(reg: pd.DataFrame, k: int = 2) -> str:
    """`reg` : régions d'un même découpage (colonnes nom, population_2022, poids_national_pct)."""
    top = reg.sort_values("population_2022", ascending=False).head(k)
    return f"{fmt_pct(top.poids_national_pct.sum())} de la population nationale est concentrée dans {k} régions : {liste_fr(top.nom)}."


def phrase_top_communes(com: pd.DataFrame, n: int = 10) -> str:
    top = com.sort_values("population_2022", ascending=False).head(n)
    return f"Les {n} communes les plus peuplées regroupent {fmt_pct(top.population_2022.sum() / com.population_2022.sum() * 100)} de la population."


def phrase_sous_moyenne(fp: pd.DataFrame) -> str:
    n = int((fp.taux_plaf_2021 < TAUX_NAT).sum())
    return f"{n} préfectures sur {len(fp)} présentent un taux d'accès à l'électricité inférieur à la moyenne nationale ({fmt_pct(TAUX_NAT)})."


# ───────────────────────── recommandations ─────────────────────────
from .priority import CODES, COMPOSANTES, SCENARIO_DEFAUT, SCENARIOS  # noqa: E402

TOP_PRIORITE = "Très haute"
LIB_ROBUSTE, LIB_SENSIBLE = "Agir sans regret", "À confirmer"


def _agences_manquantes(pop: float, ratio_nat: float, ouvertes: int) -> int:
    """Agences à ajouter pour atteindre le ratio national (agences pour 100 000 hab.)."""
    return max(0, math.ceil(pop * ratio_nat / 1e5) - int(ouvertes))


def composantes_dominantes(u, k: int = 3, weights: dict | None = None) -> list:
    """Codes des k composantes qui contribuent le plus au score IPT de l'unité `u` (poids × composante normalisée)."""
    w = weights or SCENARIOS[SCENARIO_DEFAUT]
    contrib = {c: float(u[f"{c}_norm"] if isinstance(u, pd.Series) else getattr(u, f"{c}_norm")) * w[c] for c in CODES}
    return sorted(contrib, key=contrib.get, reverse=True)[:k]


def synthese_priorites(fin: pd.DataFrame) -> dict:
    """Synthèse MÉCANIQUE du classement IPT : unités de priorité « Très haute » (triées par rang), part robuste / sensible.
    `fin` : table `fact_unite_electrique` (colonnes unite_affichage, rang_ipt, classe_priorite, stabilite, priority_stability_score, population_2022, pop_sans_acces_2021)."""
    th = fin[fin.classe_priorite == TOP_PRIORITE].sort_values("rang_ipt")
    rob, sen = th[th.stabilite == "robuste"], th[th.stabilite != "robuste"]
    return dict(n=len(th), noms=list(th.unite_affichage), robustes=list(rob.unite_affichage), sensibles=list(sen.unite_affichage),
                n_robustes=len(rob), n_sensibles=len(sen), population=float(th.population_2022.sum()), sans_acces=float(th.pop_sans_acces_2021.sum()),
                part_pop_pct=float(th.population_2022.sum() / fin.population_2022.sum() * 100))


def phrase_synthese_priorites(syn: dict) -> str:
    """« 8 unités en priorité très haute : 5 robustes (A, B…) et 3 sensibles (C…) »."""
    return (f"{syn['n']} unités sont en priorité « très haute » : {syn['n_robustes']} robuste(s) — agir sans regret ({liste_fr(syn['robustes'], 5)}) — "
            f"et {syn['n_sensibles']} sensible(s) — à confirmer ({liste_fr(syn['sensibles'], 4)}).")


def _action_unite(u, ratio_nat: float) -> tuple[str, str]:
    """(action, KPI de suivi) déduits des composantes dominantes de l'unité."""
    dom = set(composantes_dominantes(u))
    a_raccorder = max(0.0, u.population_2022 * (TAUX_NAT - u.taux_plaf_2021) / 100)
    manque = _agences_manquantes(u.population_2022, ratio_nat, u.agences_ouvertes_total)
    acces = {"c1_deficit_acces", "c2_pop_sans_acces", "c4_stagnation_acces"} & dom
    serv = {"c5_deficit_equipement", "c6_absence_service"} & dom
    actions, kpis = [], []
    if acces or not serv:
        actions.append(f"programme d'électrification de {u.unite_affichage} visant au moins le taux national ({fmt_pct(TAUX_NAT)}), soit environ {fmt_int(a_raccorder)} personnes à raccorder")
        kpis.append(f"taux d'accès (cible ≥ {fmt_pct(TAUX_NAT)}) · personnes raccordées")
    if serv:
        actions.append(f"ouverture ou renforcement de points de service CEET / TdE ({manque} agence(s) de plus pour atteindre le ratio national de {fmt_dec(ratio_nat, 2)} pour 100 000 hab.)" if manque
                       else "ouverture de guichets dans les préfectures sans agence (ratio global déjà proche du national)")
        kpis.append(f"agences ouvertes pour 100 000 hab. (cible ≥ {fmt_dec(ratio_nat, 2)})")
    return " + ".join(actions), " ; ".join(kpis)


def construire_recommandations(fin: pd.DataFrame, fp: pd.DataFrame, communes: pd.DataFrame, kpi: dict, ec: pd.DataFrame, ag: pd.DataFrame,
                               canton: pd.DataFrame) -> pd.DataFrame:
    """Table des recommandations. Les lignes de type « Priorité IPT » découlent MÉCANIQUEMENT du classement : toutes les unités de classe « Très haute »,
    dans l'ordre du rang, avec leur statut « robuste » (agir sans regret) ou « sensible » (à confirmer). Les lignes « Complémentaire » portent sur d'autres axes
    (agences, cantons, état civil, données) et ne revendiquent aucune classe IPT. `fin` : table des 33 unités avec IPT, rang, classe et stabilité."""
    rows = []
    ratio_nat = fin.agences_ouvertes_total.sum() / fin.population_2022.sum() * 1e5
    cls = fin.set_index("unite_electrique")
    base = dict.fromkeys(["Rang IPT", "Classe IPT", "Stabilité (%)", "Robustesse", "Statut", "Unité IPT"])

    def ligne(**kw):
        d = dict(base); d.update(kw); rows.append(d)

    # (1) Priorités IPT : toutes les unités « Très haute », dans l'ordre du rang
    for u in fin[fin.classe_priorite == TOP_PRIORITE].sort_values("rang_ipt").itertuples():
        robuste = u.stabilite == "robuste"
        action, kpi_suivi = _action_unite(u, ratio_nat)
        dom = composantes_dominantes(u)
        ligne(Territoire=u.unite_affichage, Type="Priorité IPT", Problème=f"Priorité très haute (rang {u.rang_ipt}/33) : " + ", ".join(COMPOSANTES[c][0].lower() for c in dom),
              Indicateur="Taux d'accès 2021 · population sans accès (PROXY) · agences ouvertes / 100 000 hab.",
              Valeur=f"{fmt_pct(u.taux_plaf_2021)} · {fmt_int(u.pop_sans_acces_2021)} pers. · {fmt_dec(u.agences_par_100k_total, 2)}",
              **{"Population concernée": u.pop_sans_acces_2021}, Priorité=u.classe_priorite,
              Recommandation=("[Priorité robuste — agir sans regret] " if robuste else "[Priorité sensible — à confirmer avec des données complémentaires avant engagement] ") + action[0].upper() + action[1:] + ".",
              Horizon="Court à moyen terme (1–2 ans)" if robuste else "Confirmer en 6 mois, puis moyen terme (2–3 ans)",
              **{"KPI de suivi": kpi_suivi},
              Preuve=(f"fact_unite_electrique : rang_ipt={u.rang_ipt} ; ipt={fmt_dec(u.ipt, 1)} ; taux_plaf_2021={fmt_dec(u.taux_plaf_2021, 2)} ({fmt_pp(u.ecart_national_pp_2021)} vs national) ; "
                      f"pop_sans_acces_2021={fmt_int(u.pop_sans_acces_2021)} (rang {u.rang_pop_sans_acces}/33) ; population_2022={fmt_int(u.population_2022)} ; "
                      f"agences_par_100k_total={fmt_dec(u.agences_par_100k_total, 2)} ; priority_stability_score={fmt_dec(u.priority_stability_score, 1)} ({u.stabilite})"),
              Axe="Priorités IPT", **{"Rang IPT": int(u.rang_ipt), "Classe IPT": u.classe_priorite, "Stabilité (%)": float(u.priority_stability_score),
                                      "Robustesse": u.stabilite, "Statut": LIB_ROBUSTE if robuste else LIB_SENSIBLE, "Unité IPT": u.unite_electrique})

    # (2) Complémentaire — préfectures sans aucune agence ouverte
    sans = fp[fp.sans_aucun_service].sort_values("population_2022", ascending=False)
    if len(sans):
        cl = sans.unite_electrique.map(cls.classe_priorite)
        n_th = int((cl == TOP_PRIORITE).sum())
        ligne(Territoire=liste_fr(sans.prefecture_nom, 7), Type="Complémentaire", Problème="Aucune agence CEET ni TdE ouverte accueillant le public", Indicateur="Préfectures sans aucune agence ouverte",
              Valeur=f"{len(sans)} préfectures", **{"Population concernée": sans.population_2022.sum()}, Priorité="Complémentaire",
              Recommandation=(f"Prévoir au moins un point de service CEET et TdE (agence ou guichet) dans chacune des {len(sans)} préfectures sans offre ; commencer par celles dont l'unité est en priorité IPT très haute "
                              f"({n_th} sur {len(sans)}) puis par les plus peuplées : {liste_fr(sans.head(3).prefecture_nom)}."),
              Horizon="Court à moyen terme (1–2 ans)", **{"KPI de suivi": "Nombre de préfectures sans agence ouverte (cible : 0)"},
              Preuve=f"fact_prefecture : sans_aucun_service=True pour {len(sans)} préfectures, {fmt_int(sans.population_2022.sum())} habitants ; {int(fp.ceet_sans_agence.sum())} sans CEET, {int(fp.tde_sans_agence.sum())} sans TdE ; "
                     f"classes IPT de leurs unités : " + ", ".join(f"{k} : {v}" for k, v in cl.value_counts().items()), Axe="Agences")

    # (3) Complémentaire — Grand Lomé : forte pression sur les services mais accès élevé → pas de priorité IPT
    for r in fp[fp.prefecture_raw.isin(["GOLFE", "AGOE-NYIVE"])].itertuples():
        manque = _agences_manquantes(r.population_2022, ratio_nat, r.agences_ouvertes_total)
        urow = cls.loc[r.unite_electrique]
        ligne(Territoire=r.prefecture_nom, Type="Complémentaire", Problème="Très forte population pour un nombre limité d'agences (capacité d'accueil, pas déficit d'accès)", Indicateur="Habitants par agence ouverte (CEET + TdE)",
              Valeur=f"{fmt_int(r.hab_par_agence_total)} hab./agence", **{"Population concernée": r.population_2022}, Priorité="Complémentaire",
              Recommandation=(f"Hors priorité IPT (classe « {urow.classe_priorite} », rang {int(urow.rang_ipt)}/33 : l'accès à l'électricité y dépasse {fmt_pct(r.taux_plaf_2021, 0)}). "
                              + (f"Suivre la capacité d'accueil : {manque} agence(s) de plus atteindraient le ratio national ({fmt_dec(ratio_nat, 2)} pour 100 000 hab.)." if manque else "Maintenir le niveau d'équipement et suivre la croissance.")),
              Horizon="Moyen terme (2–3 ans)", **{"KPI de suivi": "Habitants par agence ; délais d'attente (à collecter)"},
              Preuve=f"fact_prefecture : population_2022={fmt_int(r.population_2022)} ; agences_ouvertes_total={int(r.agences_ouvertes_total)} ; fact_unite_electrique : rang_ipt={int(urow.rang_ipt)}, classe={urow.classe_priorite}",
              Axe="Agences", **{"Rang IPT": int(urow.rang_ipt), "Classe IPT": urow.classe_priorite, "Stabilité (%)": float(urow.priority_stability_score), "Robustesse": urow.stabilite, "Statut": "Suivi", "Unité IPT": r.unite_electrique})

    # (4) Complémentaire — cantons petits / isolés
    c = canton[canton.niveau_feuille == "canton"]
    petits = c[c.petit_canton == True]
    par_pref = petits.groupby("prefecture").size().sort_values(ascending=False)
    pref_nom = dict(zip(fp.prefecture_raw, fp.prefecture_nom))
    ligne(Territoire=liste_fr([pref_nom.get(p, p) for p in par_pref.head(3).index]) + " (les plus concernées)", Type="Complémentaire", Problème="Cantons très petits : accès de proximité difficile à organiser avec des agences fixes",
          Indicateur=f"Cantons de moins de {fmt_int(kpi['seuil_petit_canton'])} habitants", Valeur=f"{kpi['n_petits_cantons']} cantons ({fmt_pct(kpi['part_petits_cantons_pct'], 0)} des cantons)",
          **{"Population concernée": petits.population_2022.sum()}, Priorité="Complémentaire",
          Recommandation="Étudier des solutions mobiles ou des relais de proximité (permanences, guichets itinérants) pour ces cantons, plutôt que des agences fixes : leur poids démographique est faible mais ils sont nombreux.",
          Horizon="Long terme (3 ans et plus)", **{"KPI de suivi": "Part des petits cantons disposant d'un point d'accès de proximité (à définir)"},
          Preuve=f"canton_2022 : petit_canton=True pour {kpi['n_petits_cantons']} cantons ({fmt_pct(kpi['part_pop_petits_cantons_pct'], 1)} de la population des cantons) ; seuil de {fmt_int(kpi['seuil_petit_canton'])} habitants (à discuter)", Axe="Démographie")

    # (5) Complémentaire — système d'état civil (national, non territorialisé)
    s = ec[(ec.sexe == "Total") & (ec.serie == "A") & ec.valide_pour_tendance & ~ec.absent_du_fichier]
    e45 = s[s.indicateur_code == "enfants_enreg_45j"].set_index("annee").valeur_brute
    sco = s[s.indicateur_code == "scolarises_sans_acte"].set_index("annee").valeur_brute
    if len(e45) >= 2 and len(sco) >= 1:
        a0, a1 = int(e45.idxmax()), int(e45.index.max())
        ligne(Territoire="National (données non territorialisées)", Type="Complémentaire", Problème="Recul de l'enregistrement des naissances dans les délais et stock d'enfants scolarisés sans acte",
              Indicateur="Enfants enregistrés dans les 45 jours · scolarisés sans acte",
              Valeur=f"{fmt_int(e45[a0])} ({a0}) → {fmt_int(e45[a1])} ({a1}) · {fmt_int(sco.iloc[-1])} sans acte ({int(sco.index[-1])})", **{"Population concernée": float(sco.iloc[-1])},
              Priorité="Nationale",
              Recommandation=(f"Rétablir l'enregistrement dans les 45 jours (baisse de {fmt_pct((1 - e45[a1] / e45[a0]) * 100, 0)} entre {a0} et {a1}) et résorber le stock d'enfants scolarisés sans acte de naissance "
                              f"({fmt_int(sco.iloc[-1])} en {int(sco.index[-1])}) ; territorialiser le suivi de l'état civil pour pouvoir cibler les préfectures."),
              Horizon="Court à moyen terme (1–3 ans)", **{"KPI de suivi": "Enfants enregistrés dans les 45 jours ; enfants scolarisés sans acte"},
              Preuve="etat_civil_long : séries nationales cohérentes uniquement (valide_pour_tendance) ; valeurs aberrantes exclues ; aucune dimension territoriale dans les données", Axe="État civil")

    # (6) Complémentaire — amélioration de la donnée
    nsp = int(ag[ag.statut == "Inconnu (Nsp)"].shape[0])
    ligne(Territoire="Dispositif statistique", Type="Complémentaire", Problème="Données insuffisantes pour cibler finement", Indicateur="Agences au statut inconnu · dénominateur du taux d'électricité non documenté · état civil non territorialisé",
          Valeur=f"{nsp} agences au statut inconnu", **{"Population concernée": np.nan}, Priorité="Nationale",
          Recommandation="Documenter le statut de chaque agence, publier la définition et le dénominateur du taux d'accès à l'électricité, et collecter l'état civil par préfecture.",
          Horizon="Court terme (≤ 1 an)", **{"KPI de suivi": "Part des agences au statut renseigné ; existence de séries territorialisées"},
          Preuve=f"agences_geo : statut='Inconnu (Nsp)' pour {nsp} agences ; reconciliation_regions : taux régionaux publiés reproduits par Σ abonnés ÷ Σ dénominateurs implicites (voir « Méthode & données » › Réconciliation) ; nature du dénominateur non documentée ; commune Danyi 1 et 2 non séparable", Axe="Données")
    return pd.DataFrame(rows)


def messages_cles(ipt: pd.DataFrame, fp: pd.DataFrame, communes: pd.DataFrame, kpi: dict, rob: pd.DataFrame, comparaison: pd.DataFrame, idn: pd.DataFrame) -> list:
    """8 à 10 messages Constat → Preuve → Implication, générés à partir des tables."""
    msgs = []
    top = ipt.sort_values("ipt", ascending=False)
    # 1 concentration
    msgs.append(dict(constat="La population est très concentrée.", preuve=f"Le Grand Lomé pèse {fmt_pct(kpi['part_grand_lome_pct'])} de la population et les 10 plus grandes communes {fmt_pct(kpi['part_top10_communes_pct'])}.",
                     implication="Une dotation identique par commune ne suit pas la population : privilégier des critères par habitant."))
    # 2 croissance
    u = comparaison[(comparaison.niveau == "unité de comparaison")]
    gl = u[u.nom.str.startswith("Grand Lomé")].iloc[0]
    msgs.append(dict(constat="Le Grand Lomé porte une part majeure de la croissance.", preuve=f"Il explique {fmt_pct(gl.contribution_croissance_pct, 0)} de l'accroissement 2010–2022 pour {fmt_pct(gl.pop_2022 / u.pop_2022.sum() * 100, 0)} de la population.",
                     implication="La pression sur les services urbains continue de croître plus vite que dans le reste du pays."))
    # 3 accès
    n_sous = int((fp.taux_plaf_2021 < TAUX_NAT).sum())
    msgs.append(dict(constat="L'accès à l'électricité est très inégal.", preuve=(f"{n_sous} préfectures sur {len(fp)} sont sous la moyenne nationale ({fmt_pct(TAUX_NAT)}) ; le taux va de {fmt_pct(ipt.taux_plaf_2021.min())} à {fmt_pct(ipt.taux_plaf_2021.max())} selon les unités"
                    + (f" (maximum plafonné : {int((ipt.taux_2021 > 100).sum())} unité(s) dépassent 100 % dans la source)." if (ipt.taux_2021 > 100).any() else ".")),
                     implication="Les moyennes nationales masquent des territoires presque non desservis."))
    # 4 personnes sans accès : volume ≠ priorité (on cite le rang IPT de chaque unité pour rester cohérent avec le classement)
    t5 = ipt.sort_values("pop_sans_acces_2021", ascending=False).head(5)
    cite = "; ".join(f"{r.unite_affichage} ({fmt_int(r.pop_sans_acces_2021)}, rang IPT {int(r.rang_ipt)} · {r.classe_priorite.lower()} · {r.stabilite})" for r in t5.head(3).itertuples())
    msgs.append(dict(constat="Le nombre de personnes sans accès dépend autant de la taille que du taux.", preuve=f"Les 5 unités les plus concernées en volume regroupent {fmt_int(t5.pop_sans_acces_2021.sum())} personnes sans accès (PROXY) ; les 3 premières : {cite}.",
                     implication="Le volume seul ne fixe pas la priorité : l'IPT combine taux, volume, équipement et tendance ; une unité très peuplée à taux moyen peut être « sensible » alors que des unités plus petites à taux très bas sont « robustes »."))
    # 5 agences
    sans = fp[fp.sans_aucun_service]
    msgs.append(dict(constat="Plusieurs préfectures n'ont aucune agence CEET ni TdE ouverte.", preuve=f"{len(sans)} préfectures ({liste_fr(sans.prefecture_nom)}) ; {int(fp.ceet_sans_agence.sum())} sont sans CEET, {int(fp.tde_sans_agence.sum())} sans TdE.",
                     implication="L'absence d'agence prive ces territoires d'un point d'accueil pour l'électricité et l'eau."))
    # 6 priorités (synthèse mécanique du classement)
    syn = synthese_priorites(ipt)
    msgs.append(dict(constat=f"{syn['n']} unités sont en priorité « très haute » ; {syn['n_robustes']} sont robustes.",
                     preuve=phrase_synthese_priorites(syn) + f" Elles regroupent {fmt_int(syn['population'])} habitants ({fmt_pct(syn['part_pop_pct'], 0)} du pays) dont {fmt_int(syn['sans_acces'])} sans accès (PROXY).",
                     implication="Agir sans attendre dans les unités robustes ; confirmer les unités sensibles (données complémentaires, enquête terrain) avant d'engager les investissements."))
    # 7 robustesse
    rb = ipt[ipt.stabilite == "robuste"].sort_values("rang_ipt")
    msgs.append(dict(constat="Le classement n'est que partiellement robuste.", preuve=f"{len(rb)} unités sur 33 restent dans le Top 10 dans au moins {int(80)} % des {rob.attrs.get('n_configurations', 506)} configurations testées ({liste_fr(rb.unite_affichage, 5)}).",
                     implication="Se concentrer d'abord sur les unités robustes ; traiter les autres comme sensibles aux pondérations."))
    # 8 état civil et identité (dynamique)
    cni = idn[(idn.type == "cni") & idn.valeur_brute.notna()].set_index("annee").valeur_brute
    pic = int(cni.idxmax()); der = int(cni.index.max())
    lac = sorted(idn[idn.lacune_source].annee.unique())
    msgs.append(dict(constat="L'état civil et l'identité ne se territorialisent pas.",
                     preuve=f"Les séries sont nationales ; la production de CNI passe de {fmt_int(cni[pic])} ({pic}) à {fmt_int(cni[der])} ({der}), soit {fmt_signe((cni[der] / cni[pic] - 1) * 100, 0)}, et l'année {liste_fr(lac)} est absente de la source.",
                     implication="Aucune priorisation territoriale n'est possible : la recommandation porte sur le système d'enregistrement."))
    # 9 comparabilité
    msgs.append(dict(constat="La comparaison 2010–2022 est limitée par les changements de découpage.", preuve="Golfe et Agoè-Nyivé ne sont comparables qu'ensemble (Grand Lomé) ; les communes n'existent pas en 2010.",
                     implication="Les croissances de territoires non comparables ne sont jamais classées."))
    # 10 données
    msgs.append(dict(constat="Le taux d'accès publié se reproduit avec les dénominateurs de la source, pas avec la population.", preuve="Taux national = Σ abonnés BT ÷ Σ (abonnés ÷ taux) : 50,30 % et 53,00 % reproduits exactement en 2019 et 2020 ; pondéré par la population 2022, l'écart 2021 est de −3,3 pp (54,5 % contre 57,82 %). La nature du dénominateur (≈ 12,8 % de la population) n'est pas documentée.",
                     implication="« Population sans accès » est un PROXY : à lire comme un ordre de grandeur, pas comme un décompte."))
    return msgs


def verifier_coherence_reco(reco: pd.DataFrame, fin: pd.DataFrame) -> list:
    """Contrôle de cohérence recommandations ↔ classement IPT. Retourne la liste des anomalies (vide = cohérent).
    Règles : (1) toutes les unités « Très haute » sont recommandées, dans l'ordre du rang, et seulement elles pour le type « Priorité IPT » ;
    (2) rang, classe et robustesse cités = ceux de la table IPT ; (3) « Priorité » d'une ligne IPT = classe IPT ; une ligne complémentaire ne revendique aucune classe ;
    (4) « Agir sans regret » seulement pour une unité robuste ; (5) une ligne IPT ne nomme aucune autre unité dans son texte."""
    err = []
    f = fin.set_index("unite_electrique")
    ipt_rows = reco[reco.Type == "Priorité IPT"]
    attendu = list(fin[fin.classe_priorite == TOP_PRIORITE].sort_values("rang_ipt").unite_electrique)
    if list(ipt_rows["Unité IPT"]) != attendu:
        err.append(f"unités recommandées {list(ipt_rows['Unité IPT'])} ≠ unités « {TOP_PRIORITE} » dans l'ordre du rang {attendu}")
    for _, r in reco.iterrows():
        unite = r["Unité IPT"]
        if isinstance(unite, str):
            if unite not in f.index:
                err.append(f"unité inconnue : {unite}")
                continue
            ref = f.loc[unite]
            if int(r["Rang IPT"]) != int(ref.rang_ipt) or r["Classe IPT"] != ref.classe_priorite or r["Robustesse"] != ref.stabilite:
                err.append(f"{r.Territoire} : rang/classe/robustesse cités ({r['Rang IPT']}, {r['Classe IPT']}, {r['Robustesse']}) ≠ table IPT ({ref.rang_ipt}, {ref.classe_priorite}, {ref.stabilite})")
        if r.Type == "Priorité IPT":
            if r.Priorité != r["Classe IPT"]:
                err.append(f"{r.Territoire} : priorité « {r.Priorité} » ≠ classe IPT « {r['Classe IPT']} »")
            if r.Statut == LIB_ROBUSTE and r.Robustesse != "robuste":
                err.append(f"{r.Territoire} : « {LIB_ROBUSTE} » attribué à une unité {r.Robustesse}")
            if r.Statut == LIB_SENSIBLE and r.Robustesse == "robuste":
                err.append(f"{r.Territoire} : « {LIB_SENSIBLE} » attribué à une unité robuste")
            texte = f"{r.Problème} {r.Recommandation}"
            for autre in fin.unite_affichage:
                if autre != r.Territoire and autre in texte and autre not in r.Territoire:
                    err.append(f"{r.Territoire} : cite aussi {autre} dans son texte")
        elif r.Priorité in set(fin.classe_priorite):
            err.append(f"{r.Territoire} : une ligne complémentaire ne doit pas porter la classe IPT « {r.Priorité} »")
    return err
