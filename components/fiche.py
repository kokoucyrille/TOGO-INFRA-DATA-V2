"""Fiche territoire : synthèse d'un territoire choisi par clic sur la carte, recherche ou filtre (région ou préfecture)."""
from __future__ import annotations

import streamlit as st

from components import insights
from components.ui import panel
from data import loader as D
from utils.formats import fmt_dec, fmt_int, fmt_pct, fmt_pp


def _rows(items: list[tuple[str, str, str]]) -> str:
    return "".join(f'<div class="fiche-row"><span class="fiche-k">{k}</span><span class="fiche-v">{v}</span><span class="fiche-n">{n}</span></div>' for k, v, n in items)


def fiche_territoire(f: dict, key: str = "fiche") -> None:
    """Affiche la fiche de la préfecture (sinon de la région) sélectionnée dans les filtres globaux ; invite à cliquer sinon."""
    T = D.load_tables()
    FP = T["prefecture"]
    with panel(key, "Fiche territoire", "fa-location-dot", height=None):
        if f.get("prefecture"):
            r = FP[FP.prefecture_raw == f["prefecture"]].iloc[0]
            rang_pop = int((FP.population_2022 > r.population_2022).sum()) + 1
            st.markdown(f'<div class="fiche-h">{r.prefecture_nom} <small>· {D.labels(f["decoupage"]).get(r[f["region_col"]], r[f["region_col"]])}</small></div>' + _rows([
                ("Population 2022", fmt_int(r.population_2022), f"{fmt_pct(r.poids_national_pct, 2)} du pays · rang {rang_pop} sur 39"),
                ("Accès à l'électricité 2021", fmt_pct(r.taux_plaf_2021, 1), f"{fmt_pp(r.ecart_national_pp_2021)} vs national publié" + (" · taux hérité de l'unité" if r.taux_herite_du_groupe else "")),
                ("Population sans accès (PROXY)", fmt_int(r.pop_sans_acces_2021), "population 2022 × (1 − taux)"),
                ("Agences CEET · TdE ouvertes", f"{int(r.ceet_ouvertes)} · {int(r.tde_ouvertes)}", f"{fmt_dec(r.agences_par_100k_total, 2)} pour 100 000 hab." if r.agences_ouvertes_total else "aucune agence ouverte"),
                ("Croissance 2010–2022", (fmt_pct(r.tcam_pct, 2) + "/an") if r.tcam_pct == r.tcam_pct else "N/D", {"HIGH": "comparable", "MEDIUM": "à lire avec prudence", "LOW": "non comparable"}.get(r.flag_croissance, "")),
                ("Priorité IPT (unité)", f"{r.unite_classe_priorite} · {int(r.unite_rang_ipt)}ᵉ/33", f"{r.unite_stabilite} ({fmt_pct(r.unite_stabilite_pct, 0)} des configurations)"),
            ]), unsafe_allow_html=True)
        elif f.get("region"):
            labs = D.labels(f["decoupage"])
            g = FP[FP[f["region_col"]] == f["region"]]
            pop = g.population_2022.sum()
            taux = (g.taux_plaf_2021 * g.population_2022).sum() / pop
            st.markdown(f'<div class="fiche-h">{labs.get(f["region"], f["region"])} <small>· région</small></div>' + _rows([
                ("Population 2022", fmt_int(pop), f"{fmt_pct(pop / FP.population_2022.sum() * 100, 1)} du pays · {len(g)} préfectures"),
                ("Accès à l'électricité 2021", fmt_pct(taux, 1), "moyenne des unités pondérée par la population (CALCUL)"),
                ("Population sans accès (PROXY)", fmt_int(g.pop_sans_acces_2021.sum()), "somme des préfectures"),
                ("Agences CEET · TdE ouvertes", f"{int(g.ceet_ouvertes.sum())} · {int(g.tde_ouvertes.sum())}", f"{fmt_dec(g.agences_ouvertes_total.sum() / pop * 1e5, 2)} pour 100 000 hab."),
                ("Préfectures en priorité IPT « très haute »", f"{int((g.unite_classe_priorite == 'Très haute').sum())} sur {len(g)}", ", ".join(g[g.unite_classe_priorite == 'Très haute'].prefecture_nom.head(4)) or "aucune"),
            ]), unsafe_allow_html=True)
        else:
            insights.nd_note("<b>Aucun territoire sélectionné.</b> Cliquez une région ou une préfecture sur la carte, ou utilisez la recherche en haut de la barre latérale : la fiche et tous les filtres suivent.")
