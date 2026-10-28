"""Page « Services de base » — objectif 3 : inégalités d'accès à l'électricité et répartition des agences CEET / TdE rapportées à la population."""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from components import gstate, charts, insights, maps, tables
from components.kpi_cards import create_kpi_row
from components.styles import THEME
from components.sidebar import create_sidebar
from components.ui import flush_panel_css, legend_rows, page_title, panel
from data import loader as D, query as Q
from utils import services as SV
from utils.formats import fmt_dec, fmt_int, fmt_pct, fmt_pp

f = create_sidebar("services")
T = D.load_tables()
FP = T["prefecture"]
yr = int(f["annee"])
NAT = SV.TAUX_NATIONAL.get(yr)                                               # taux national PUBLIÉ (seulement 2018 et 2021)
page_title("fa-bolt", "Services de base", "Électricité et agences CEET / TdE.")

fp = Q.appliquer(FP, f, "prefecture", pref_col="prefecture_raw", use_commune=False).copy()
SCORE = SV.score_deficit_croise(FP, yr)                          # rangs nationaux (référence stable), filtrés ensuite par l'affichage

# ---- indicateurs de synthèse du périmètre filtré ----------------------------------------------------------------------
if fp.empty:
    insights.empty_state("Aucune préfecture ne correspond à cette sélection.")
    st.stop()
tp = SV.taux_pondere(fp, yr)
sans = SV.population_sans_acces(fp, yr)
ag_total = int(fp.agences_ouvertes_total.sum())
pop_perimetre = float(fp.population_2022.sum())
st.markdown(f'<div class="kpi-group"><i class="fa-solid fa-bolt"></i> Électricité · année {yr}</div>', unsafe_allow_html=True)
create_kpi_row([
    {"title": "Population 2022 du périmètre", "value": fmt_int(pop_perimetre), "icon": "fa-users", "variant": "green"},
    {"title": f"Taux d'accès pondéré {yr}", "value": fmt_pct(tp["valeur"], 1) if tp["valeur"] is not None else "N/D", "icon": "fa-bolt", "variant": "blue"},
    {"title": f"Personnes sans accès {yr} (PROXY)", "value": fmt_int(sans.sum(min_count=1)), "icon": "fa-ban", "variant": "red"},
], key="sv_kpis")
st.markdown('<div class="kpi-group"><i class="fa-solid fa-building"></i> Agences CEET et TdE ouvertes</div>', unsafe_allow_html=True)
create_kpi_row([
    {"title": "Agences ouvertes (CEET + TdE)", "value": fmt_int(ag_total), "icon": "fa-building", "variant": "yellow"},
    {"title": "Agences pour 100 000 habitants", "value": fmt_dec(100000 * ag_total / pop_perimetre, 2) if pop_perimetre else "N/D", "icon": "fa-chart-simple", "variant": "teal"},
    {"title": "Préfectures sans aucune agence", "value": f"{int(fp.sans_aucun_service.sum())} sur {len(fp)}", "icon": "fa-triangle-exclamation", "variant": "gray"},
], key="sv_kpis_ag")

_reg = fp.assign(sans=sans).groupby("region_nom")["sans"].sum(min_count=1).dropna().sort_values(ascending=False)
_msgs = []
if tp["valeur"] is not None:
    ref = f" (taux national publié : <b>{fmt_pct(NAT, 1)}</b>, écart {fmt_pp(tp['valeur'] - NAT, 1)} : la source pondère par ses propres dénominateurs, voir « Méthode & données » › Réconciliation)" if NAT is not None and len(fp) == len(FP) else ""
    _msgs.append(("retenir", f"Sur ce périmètre, le taux d'accès {yr} pondéré par la population est de <b>{fmt_pct(tp['valeur'], 1)}</b>{ref}. "
                  f"Environ <b>{fmt_int(sans.sum(min_count=1))}</b> personnes seraient sans accès (PROXY)"
                  + (f", dont <b>{fmt_pct(100 * _reg.iloc[0] / _reg.sum(), 0)}</b> en région {_reg.index[0]}." if len(_reg) > 1 and _reg.sum() > 0 else ".")))
_dens_med = float(FP.agences_par_100k_total.median())
_cible = fp[(fp[f"taux_{yr}"].clip(upper=100) < FP[f"taux_{yr}"].clip(upper=100).median()) & (fp.agences_par_100k_total < _dens_med)]
if len(_cible):
    _top = _cible.assign(sans=SV.population_sans_acces(_cible, yr)).sort_values("sans", ascending=False).head(3)
    _msgs.append(("implication", f"<b>{len(_cible)}</b> préfecture(s) cumulent un taux d'accès et une densité d'agences inférieurs aux médianes nationales ; "
                  f"les plus peuplées parmi elles : <b>{', '.join(_top.prefecture_nom)}</b>. Ce croisement désigne où examiner d'abord la situation ; "
                  "il ne prouve aucun lien de cause à effet entre agences et accès."))
_lim = []
if tp["n_sans_taux"]:
    _lim.append(f"{tp['n_sans_taux']} préfecture(s) sans taux publié en {yr} (exclues du calcul, jamais comptées à 0)")
if tp["n_plafonnes"]:
    _lim.append(f"{tp['n_plafonnes']} taux supérieur(s) à 100 % dans la source, plafonné(s) à 100 %")
_lim.append("la population sans accès est un PROXY (population 2022 × (1 − taux)), pas un décompte")
_msgs.append(("attention", "Limites : " + " ; ".join(_lim) + "."))
insights.story_grid(_msgs)
# ---- explorateur de cartes : 1 · thème → 2 · indicateur → carte + graphique associé --------------------------------------
IND_E = {
    "Taux d'accès (%)": "Part de la population ayant accès à l'électricité (taux de la source, plafonné à 100 %).",
    "Population sans accès (PROXY)": "Personnes sans accès estimées : population 2022 × (1 − taux). Ce n'est pas un décompte observé.",
    "Écart à la moyenne nationale (pp)": "Taux de la préfecture moins le taux national publié (points de pourcentage). Disponible en 2018 et 2021 seulement.",
    "Évolution 2018→2021 (pp)": "Gain de taux d'accès entre 2018 et 2021, en points de pourcentage (N/D si une des deux années manque).",
}
IND_A = {
    "Agences pour 100 000 hab.": ("par100", lambda v: fmt_dec(v, 2), "Agences ouvertes rapportées à la population 2022 de la préfecture."),
    "Habitants par agence": ("hab", fmt_int, "Population 2022 divisée par le nombre d'agences ouvertes ; N/D si aucune agence (jamais 0)."),
    "Agences ouvertes (nombre)": ("ouv", fmt_int, "Nombre d'agences au statut « utilisé », hors sites administratifs et techniques."),
}
IND_CROSS = {
    "Déficit croisé · accès + densité des agences": "Score relatif 0–100 : moyenne des rangs inversés du taux d'accès et des agences pour 100 000 hab. Plus il est élevé, plus le déficit est marqué.",
    "Taux d'accès (%)": "Taux d'accès à l'électricité par préfecture (rappel, pour croiser avec la densité d'agences).",
    "Agences combinées pour 100 000 hab.": "Agences CEET + TdE ouvertes pour 100 000 habitants.",
}
THEMES = {  # thème -> (icône, clé du sélecteur d'indicateur, liste d'indicateurs)
    "Électricité": ("fa-bolt", "sv_ind_electricite", list(IND_E)),
    "Agences CEET": ("fa-building", "sv_ind_CEET", list(IND_A)),
    "Agences TdE": ("fa-building", "sv_ind_TdE", list(IND_A)),
    "Analyse croisée": ("fa-bullseye", "sv_ind_croisee", list(IND_CROSS)),
}
H_MAP = 390

st.subheader("Explorer les cartes")
with st.container(key="sv_bar"):
    c_theme, c_ind = st.columns([1.0, 1.25], gap="medium")
    with c_theme:
        st.markdown('<div class="sv-pick"><span class="sv-step">1</span><span>Choisir un thème</span></div>', unsafe_allow_html=True)
        theme = st.segmented_control("Thème", list(THEMES), default="Électricité", key="sv_theme", label_visibility="collapsed") or "Électricité"
    icon_t, ind_key, ind_opts = THEMES[theme]
    with c_ind:
        st.markdown('<div class="sv-pick"><span class="sv-step">2</span><span>Choisir l\'indicateur affiché sur la carte</span></div>', unsafe_allow_html=True)
        ind = st.selectbox("Indicateur affiché sur la carte", ind_opts, key=ind_key, label_visibility="collapsed")
    definition = IND_E.get(ind) if theme == "Électricité" else (IND_A[ind][2] if theme.startswith("Agences") else IND_CROSS[ind])
    st.markdown(f'<div class="sv-desc"><i class="fa-solid fa-circle-info"></i><span><b>{ind}</b> — {definition} '
                f'Périmètre : <b>{len(fp)}</b> préfecture(s)' + (f", année <b>{yr}</b>." if theme in ("Électricité", "Analyse croisée") else ".") + "</span></div>", unsafe_allow_html=True)


def _render_prefecture_map(df: pd.DataFrame, value_col: str, title: str, formatter, key: str,
                           palette: list[str] | None = None, higher_is_first: bool = True) -> None:
    if df.empty or df[value_col].notna().sum() == 0:
        insights.empty_state("Aucune valeur disponible pour cet indicateur et cette sélection.")
        return
    polygons = []
    _pid = dict(zip(D.load_tables()["prefecture"].prefecture_raw, D.load_tables()["prefecture"].prefecture_id))
    base_values = df[["prefecture_raw", "prefecture_nom", value_col]].copy()
    classes, legend = maps.legend_from_values(
        base_values[value_col], palette or maps.ACCESS_LEGEND_COLORS, formatter,
        higher_is_first=higher_is_first,
    )
    base_values["cls"] = classes
    for row in base_values.itertuples(index=False):
        for name in D.polygons_of_prefecture().get(row.prefecture_raw, []):
            polygons.append({
                "code": name, "Territoire": row.prefecture_nom, "Valeur": getattr(row, value_col),
                "cls": row.cls, "tip": row.prefecture_nom, "id": _pid.get(row.prefecture_raw),
            })
    if not polygons:
        insights.empty_state("Aucun polygone préfectoral ne correspond à cette sélection.")
        return
    clicked = maps.create_map("Préfecture", pd.DataFrame(polygons), legend, key=key, height=H_MAP,
                              value_label=title, fmt=formatter)
    _pn = dict(zip(_pid.values(), D.load_tables()["prefecture"].prefecture_nom))
    gstate.handle_click(key, clicked, lambda i: gstate.hierarchy_for("prefecture", _pn[i]) if i in _pn else None)
    st.caption("Survolez une préfecture pour lire sa valeur. Les territoires hors sélection restent grisés.")


def _map_spec():
    """(frame avec colonne map_value, libellé, formateur, palette, note, carte disponible ?) pour le thème et l'indicateur choisis."""
    frame = fp.copy()
    rate = frame[f"taux_{yr}"].clip(upper=100)
    ok, note = True, ""
    if theme == "Électricité":
        if ind == "Taux d'accès (%)":
            frame["map_value"] = rate; fmt_, pal = (lambda v: fmt_pct(v, 1)), maps.ACCESS_LEGEND_COLORS
        elif ind == "Population sans accès (PROXY)":
            frame["map_value"] = SV.population_sans_acces(frame, yr); fmt_, pal = fmt_int, maps.DEFICIT_LEGEND_COLORS
            note = "PROXY : population 2022 × (1 − taux d'accès). Ce n'est pas un décompte observé."
        elif ind == "Écart à la moyenne nationale (pp)":
            frame["map_value"] = rate - NAT if NAT is not None else np.nan; fmt_, pal = (lambda v: fmt_pp(v, 1)), maps.ACCESS_LEGEND_COLORS
            ok = NAT is not None
        else:
            frame["map_value"] = frame.delta_pp_2018_2021; fmt_, pal = (lambda v: fmt_pp(v, 1)), maps.ACCESS_LEGEND_COLORS
        return frame, ind, fmt_, pal, note, ok
    if theme.startswith("Agences"):
        service = "ceet" if theme.endswith("CEET") else "tde"
        col, fmt_, _ = IND_A[ind]
        frame["map_value"] = frame[{"par100": f"{service}_par_100k", "hab": f"{service}_hab_par_agence", "ouv": f"{service}_ouvertes"}[col]]
        if col == "hab":
            note = "Les territoires sans agence ouverte sont N/D pour « habitants par agence », jamais assimilés à zéro."
        return frame, f"{ind} · {theme}", fmt_, (maps.ACCESS_LEGEND_COLORS if col == "par100" else maps.DEFICIT_LEGEND_COLORS), note, True
    if ind == list(IND_CROSS)[0]:
        frame["map_value"] = frame.prefecture_raw.map(SCORE)
        return frame, "Déficit croisé (score relatif / 100)", (lambda v: fmt_dec(v, 0)), maps.DEFICIT_LEGEND_COLORS, \
            "Score relatif, pas un indicateur officiel : il compare les préfectures entre elles et ne prouve aucun lien de cause à effet.", True
    if ind == list(IND_CROSS)[1]:
        frame["map_value"] = rate
        return frame, ind, (lambda v: fmt_pct(v, 1)), maps.ACCESS_LEGEND_COLORS, "", True
    frame["map_value"] = frame.agences_par_100k_total
    return frame, ind, (lambda v: fmt_dec(v, 2)), maps.ACCESS_LEGEND_COLORS, "", True


def _side_chart() -> None:
    """Graphique associé au thème : il suit les mêmes filtres que la carte."""
    if theme == "Électricité":
        with panel("sv_side", "Taux d'accès pondéré par année", "fa-chart-simple", height=300):
            years_ = [2018, 2019, 2020, 2021]
            hdf = pd.DataFrame({"Année": [str(y) for y in years_], "Taux": [SV.taux_pondere(fp, y)["valeur"] for y in years_]}).dropna()
            if hdf.empty:
                insights.empty_state()
            else:
                charts.show(charts.create_bar_chart(hdf, "Année", "Taux", ["#016b4b", "#1488ee", "#fec902", "#8b3fe0"][:len(hdf)], height=210, fmt=lambda v: fmt_pct(v, 1)), "sv_side_chart")
            insights.nd_note("Pondéré par la population 2022, plafonné à 100 %. Référence nationale publiée : "
                             f"{fmt_pct(SV.TAUX_NATIONAL[2018], 1)} (2018) et {fmt_pct(SV.TAUX_NATIONAL[2021], 1)} (2021) ; rien en 2019 ni 2020.")
    elif theme.startswith("Agences"):
        service = "ceet" if theme.endswith("CEET") else "tde"
        with panel("sv_side", f"Agences {service.upper()} ouvertes par région", "fa-chart-simple", height=300):
            agg = fp.groupby("region_6")[f"{service}_ouvertes"].sum().reset_index().rename(columns={"region_6": "Région", f"{service}_ouvertes": "Agences"}).sort_values("Agences", ascending=False)
            charts.show(charts.create_bar_chart(agg, "Région", "Agences", ["#016b4b", "#1488ee", "#fec902", "#8b3fe0", "#f20e36", "#0d8a7a"][:len(agg)], height=210, fmt=fmt_int), "sv_side_chart")
            insights.nd_note("Nombre d'agences ouvertes par région, sur le périmètre filtré.")
    else:
        with panel("sv_side", "Déficit croisé par région", "fa-chart-simple", height=300):
            agg = fp.assign(Score=fp.prefecture_raw.map(SCORE)).groupby("region_6")["Score"].mean().dropna().reset_index().rename(columns={"region_6": "Région"}).sort_values("Score", ascending=False)
            if agg.empty:
                insights.empty_state()
            else:
                charts.show(charts.create_bar_chart(agg, "Région", "Score", ["#f20e36", "#fec902", "#016b4b", "#1488ee", "#8b3fe0", "#0d8a7a"][:len(agg)], height=210, fmt=lambda v: fmt_dec(v, 0)), "sv_side_chart")
            insights.nd_note("Score moyen (non pondéré) des préfectures de la région ; rangs calculés sur les 39 préfectures.")


frame_m, label_m, fmt_m, pal_m, note_m, ok_m = _map_spec()
col_map, col_side = st.columns([1.55, 1.0], gap="medium")
with col_map:
    with panel("sv_map", f"{label_m} · carte du Togo", icon_t, height=H_MAP + 105):
        if not ok_m:
            insights.empty_state(f"Le taux national {yr} n'est pas publié ; cet indicateur n'est pas disponible.")
        else:
            _render_prefecture_map(frame_m, "map_value", label_m, fmt_m, "sv_map_" + THEMES[theme][1], palette=pal_m, higher_is_first=True)
            if note_m:
                insights.nd_note(note_m)
with col_side:
    _side_chart()
    if NAT is None and theme == "Électricité":
        insights.nd_note(f"Taux national {yr} non publié par la source : écart au national indisponible.")

# ---- Évolution par an et par région (histogrammes circulaires) -------------------------------------------------------
st.subheader("Évolution de l'accès par région (2018–2021)")
insights.story("analyse", "Représentation circulaire de la population sans accès à l'électricité par région, pour chaque année publiée. "
              "La taille de chaque part indique le poids régional du déficit ; le centre donne le total national de personnes sans accès.")
years = [y for y in (2018, 2019, 2020, 2021) if f"taux_{y}" in fp.columns]
region_colors = {"SAVANES": "#f20e36", "KARA": "#fec902", "CENTRALE": "#1488ee", "PLATEAUX": "#016b4b",
                 "MARITIME": "#8b3fe0", "DAGL": "#0d8a7a", "Grand Lomé (DAGL)": "#0d8a7a"}
# normaliser les noms de régions
reg_col = "region_6" if "region_6" in fp.columns else "region_nom"
donut_cols = st.columns(len(years), gap="small")
for col, y in zip(donut_cols, years):
    sans = SV.population_sans_acces(fp, y).groupby(fp[reg_col]).sum()
    sans = sans[sans > 0].sort_values(ascending=False)
    labels = list(sans.index)
    values = [float(v) for v in sans.values]
    colors = [region_colors.get(str(l).upper(), "#7b8794") for l in labels]
    total = sum(values)
    with col:
        with panel(f"sv_donut_{y}", f"Population sans accès · {y}", "fa-chart-line", height=300):
            if not values:
                insights.empty_state()
            else:
                fig = charts.create_donut_chart(labels, values, colors, fmt_int(total), str(y), height=200)
                charts.show(fig, f"sv_donut_chart_{y}")
                st.markdown(legend_rows([(c, str(l), fmt_int(v)) for c, l, v in zip(colors, labels, values)]),
                            unsafe_allow_html=True)
                insights.nd_note(f"Total sans accès : {fmt_int(total)} (PROXY)" + (f" ; {SV.taux_pondere(fp, y)['n_sans_taux']} préfecture(s) sans taux exclue(s), total sous-estimé." if SV.taux_pondere(fp, y)["n_sans_taux"] else "."))

# tableau récapitulatif par région : taux PONDÉRÉ par la population (et non moyenne simple des préfectures)
st.markdown("**Taux d'accès pondéré par région (%)**")
rows = []
for reg, g in fp.groupby(reg_col):
    rows.append({"Région": reg, **{str(y): SV.taux_pondere(g, y)["valeur"] for y in years}})
recap = pd.DataFrame(rows)
st.markdown('<div class="list-scroll" style="max-height:260px">' + tables.create_table(recap, formats={str(y): (lambda v: fmt_pct(v, 1)) for y in years}) + "</div>", unsafe_allow_html=True)
insights.nd_note("Moyenne pondérée par la population 2022, taux plafonnés à 100 % ; N/D si aucun taux publié pour la région cette année-là.")

# ---- export du périmètre filtré (même tableau que les cartes) --------------------------------------------------------
export = fp[["region_nom", "prefecture_nom", "population_2022", f"taux_{yr}", "ceet_ouvertes", "tde_ouvertes", "agences_ouvertes_total", "agences_par_100k_total"]].copy()
export["taux_plafonne_%"] = export[f"taux_{yr}"].clip(upper=100)
export["sans_acces_PROXY"] = sans.round(0)
export["score_deficit_croise"] = fp.prefecture_raw.map(SCORE).round(1)
st.download_button("Exporter", Q.csv_bytes(export.rename(columns={f"taux_{yr}": f"taux_{yr}_source_%"})), f"services_de_base_{yr}.csv", "text/csv",
                   key="dl_btn", help="Exporter les données affichées (CSV, filtres et année actifs)")

flush_panel_css()
