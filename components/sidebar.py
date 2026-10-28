"""
Sidebar verticale de filtres.

Chaque page possède son jeu de filtres (cf. PAGE_FILTERS). Les valeurs choisies (widgets `w_<page>_<nom>`)
s'appliquent immédiatement : elles sont recopiées dans `applied_<page>` à chaque exécution.
Cascade : découpage → région → préfecture → commune → canton (un changement de niveau supérieur remet les niveaux
inférieurs à « Toutes… »). « Réinitialiser » remet tout à zéro.
"""
from __future__ import annotations

import streamlit as st

from components import gstate
from components.ui import flag_data_uri
from data import loader as D

# nom du filtre -> (libellé, icône Font Awesome, type de widget, valeur par défaut)
FIELDS = {
    "decoupage": ("Découpage régional", "fa-layer-group", "select", D.DEC6),
    "region": ("Région", "fa-location-dot", "select", D.ALL_REGIONS),
    "prefecture": ("Préfecture", "fa-building", "select", D.ALL_PREFS),
    "commune": ("Commune", "fa-location-crosshairs", "select", D.ALL_COMMUNES),
    "canton": ("Canton / quartier", "fa-map-pin", "select", D.ALL_CANTONS),
    "annee": ("Année", "fa-calendar-days", "select", D.ANNEES_ELEC[0]),
    "periode": ("Période", "fa-calendar-days", "range", (D.ANNEES_EC[0], D.ANNEES_EC[-1])),
    "comparabilite": ("Comparabilité 2010–2022", "fa-scale-balanced", "multi", ["HIGH", "MEDIUM"]),
    "classes": ("Niveau de priorité", "fa-bullseye", "multi", []),
    "niveau": ("Niveau d’analyse", "fa-layer-group", "select", "Préfecture"),
}

HELP = {
    "decoupage": "6 régions 2022 : le Grand Lomé (DAGL) est une région à part. 5 régions historiques : le Grand Lomé fait partie de la Maritime (découpage des fichiers d'électricité et d'agences).",
    "region": "Restreint toutes les valeurs, cartes et exports à une région. Un clic sur une carte ou la recherche en haut de la barre latérale remplissent aussi ce filtre ; il est conservé d'une page à l'autre.",
    "prefecture": "Une des 39 préfectures de 2022. Choisir une préfecture sélectionne automatiquement sa région ; le filtre est conservé d'une page à l'autre.",
    "commune": "Une des 117 communes (la ligne « Danyi 1 + Danyi 2 » regroupe deux communes non séparables).",
    "canton": "Un des 375 cantons hors Grand Lomé (les quartiers du Grand Lomé sont traités à part).",
    "annee": "Année du taux d'accès à l'électricité publié (2018 à 2021). 2019 et 2020 n'ont pas de taux national publié.",
    "periode": "Période affichée pour les séries nationales d'état civil et d'identité (2014–2022). Les années absentes de la source restent vides (N/D).",
    "comparabilite": "HIGH : territoire comparable ; MEDIUM : à lire avec prudence ; LOW : non comparable (jamais classé). Décocher MEDIUM ou ajouter LOW change les territoires inclus dans les totaux.",
    "classes": "Niveau de priorité de l'indice IPT (quartiles de l'indice) : très haute = 25 % supérieurs. Vide = tous les niveaux.",
    "niveau": "Niveau territorial des cartes, classements et tableaux de la page (région, préfecture, commune, canton).",
}

PAGE_FILTERS = {
    "overview": {"title": "FILTRES", "fields": ["decoupage", "region", "prefecture", "niveau"]},
    "carte": {"title": "FILTRES", "fields": ["decoupage", "region", "prefecture"]},
    "comparer": {"title": "FILTRES", "fields": ["decoupage"], "note": "Choisissez 2 à 4 territoires dans la page ; le découpage détermine les régions proposées."},
    "demographie": {"title": "FILTRES", "fields": ["decoupage", "region", "prefecture", "commune", "canton", "niveau"]},
    "evolution": {"title": "FILTRES", "fields": ["decoupage", "region", "prefecture", "comparabilite", "niveau"]},
    "services": {"title": "FILTRES", "fields": ["region", "prefecture", "annee"], "note": "Régions historiques (Grand Lomé dans la Maritime), comme dans les fichiers d'électricité."},
    "etat_civil": {"title": "FILTRES", "fields": ["periode"], "extra_keys": ["ec_ind", "ec_types", "ec_sexe", "ec_mode"], "note": "Données nationales : aucune dimension territoriale. Les anomalies de la source restent visibles."},
    "priorites": {"title": "FILTRES AVANCÉS", "fields": ["region", "prefecture", "classes"], "note": "Régions historiques ; l'indice est calculé sur 33 unités électriques."},
    "methode": {"title": "FILTRES", "fields": [], "note": "Cette page décrit la méthode : elle ne dépend d'aucun filtre."},
}
PAGES_DECOUPAGE_FIXE = {"services", "priorites"}            # découpage imposé (régions historiques)
LEVELS_BELOW = {"decoupage": ["region", "prefecture", "commune", "canton"], "region": ["prefecture", "commune", "canton"], "prefecture": ["commune", "canton"], "commune": ["canton"]}
LEVEL_KEYS = {"overview": "ov_level", "demographie": "demo_level", "evolution": "ev_level"}
GLOBAL_FIELDS = set(gstate.FIELDS)


def _key(page: str, name: str) -> str:
    if name == "niveau":
        return LEVEL_KEYS[page]
    return f"w_{page}_{name}"


def _default(page: str, name: str) -> object:
    if name != "niveau":
        return FIELDS[name][3]
    if page == "overview":
        return "Préfecture"
    if page == "demographie":
        return "Région"
    return "Préfecture"


def _decoupage(page: str) -> str:
    return D.DEC5 if page in PAGES_DECOUPAGE_FIXE else st.session_state.get(_key(page, "decoupage"), D.DEC6)


def _cascade(page: str, level: str) -> None:
    """Callback : quand `level` change, les niveaux inférieurs reviennent à leur valeur par défaut."""
    for n in LEVELS_BELOW.get(level, []):
        if n in PAGE_FILTERS[page]["fields"]:
            st.session_state[_key(page, n)] = FIELDS[n][3]


def _reset(page: str) -> None:
    gstate.reset_all()
    for n in PAGE_FILTERS[page]["fields"]:
        st.session_state[_key(page, n)] = _default(page, n)
    for k in PAGE_FILTERS[page].get("extra_keys", []):      # widgets propres à la page : retour à leur valeur par défaut
        st.session_state.pop(k, None)
    st.session_state[f"applied_{page}"] = {}


def _label(text: str, icon: str, help_: str = "") -> None:
    tip = f' <span class="f-help" title="{help_}" aria-label="{help_}" tabindex="0"><i class="fa-solid fa-circle-info"></i></span>' if help_ else ""
    st.markdown(f'<div class="f-label"><i class="fa-solid {icon}"></i><span>{text}</span>{tip}</div>', unsafe_allow_html=True)


def _options(page: str, name: str) -> list:
    """Options d'un filtre selon l'état courant des filtres de niveau supérieur."""
    ss = st.session_state
    dec = _decoupage(page)
    reg_label = ss.get(_key(page, "region"), D.ALL_REGIONS)
    code = D.region_code(dec, reg_label) if reg_label != D.ALL_REGIONS else None
    pref = ss.get(_key(page, "prefecture"), D.ALL_PREFS)
    pref = None if pref == D.ALL_PREFS else pref
    com = ss.get(_key(page, "commune"), D.ALL_COMMUNES)
    com = None if com == D.ALL_COMMUNES else com
    if name == "niveau":
        if page == "overview" and ss.get("ov_metric") == "Indice de priorité territoriale (0–100)":
            return ["Préfecture"]
        return {
            "overview": ["Région", "Préfecture"],
            "demographie": ["Région", "Préfecture", "Commune", "Canton"],
            "evolution": ["Région", "Préfecture", "Commune"],
        }[page]
    return {
        "decoupage": D.DECOUPAGES,
        "region": [D.ALL_REGIONS] + D.regions(dec),
        "prefecture": [D.ALL_PREFS] + D.prefectures_of(dec, code),
        "commune": [D.ALL_COMMUNES] + D.communes_of(dec, code, pref),
        "canton": [D.ALL_CANTONS] + D.cantons_of(com, pref, code, dec),
        "annee": D.ANNEES_ELEC,
        "periode": D.ANNEES_EC,
        "comparabilite": ["HIGH", "MEDIUM", "LOW"],
        "classes": ["Très haute", "Haute", "Moyenne", "Faible"],
    }[name]


def create_sidebar(page: str, extras=None) -> dict:
    """Dessine la sidebar de la page et renvoie le dictionnaire de filtres APPLIQUÉS.
    `extras` : fonction optionnelle dessinant des sections propres à la page (avant la note et le bouton Réinitialiser)."""
    spec = PAGE_FILTERS[page]
    ss = st.session_state
    applied = ss.setdefault(f"applied_{page}", {})
    ss["_page"] = page
    gstate.load_from_url()
    if gstate.apply_pending():                                      # recherche / clic sur une carte : on repart de l'état global
        for n in spec["fields"]:
            if n in GLOBAL_FIELDS:
                ss.pop(_key(page, n), None)
        for k in (LEVEL_KEYS.get(page),):
            if k and page == "demographie":
                ss.pop("demo_sig", None)
    with st.sidebar:
        st.selectbox("Rechercher un territoire", list(gstate.search_index()), index=None, key="g_search", on_change=gstate.on_search, placeholder="Rechercher un territoire…",
                     label_visibility="collapsed", help="Région, préfecture, commune ou canton : la sélection met à jour les filtres de toutes les pages et de la carte.")
        st.markdown(f'<div class="f-title"><i class="fa-solid fa-filter"></i><span>{spec["title"]}</span></div>', unsafe_allow_html=True)
        for name in spec["fields"]:
            label, icon, kind, default = FIELDS[name]
            key = _key(page, name)
            default = _default(page, name)
            if name == "niveau" and page == "demographie":
                dec = _decoupage(page)
                region = ss.get(_key(page, "region"), D.ALL_REGIONS)
                prefecture = ss.get(_key(page, "prefecture"), D.ALL_PREFS)
                commune = ss.get(_key(page, "commune"), D.ALL_COMMUNES)
                sig = (dec, region, prefecture, commune)
                if ss.get("demo_sig") != sig:
                    depth = 3 if ss.get(_key(page, "canton"), D.ALL_CANTONS) != D.ALL_CANTONS or commune != D.ALL_COMMUNES else (2 if prefecture != D.ALL_PREFS else (1 if region != D.ALL_REGIONS else 0))
                    ss["demo_sig"] = sig
                    ss[key] = ["Région", "Préfecture", "Commune", "Canton"][depth]
            if key not in ss:                                   # restaure la valeur globale (partagée entre pages), sinon la valeur appliquée de la page
                gv = gstate.widget_value(name, _decoupage(page)) if name in GLOBAL_FIELDS else None
                ss[key] = gv if gv else applied.get(name, default)
            opts = _options(page, name)
            cur = ss[key]
            # On ne réécrit la valeur d'un widget que si elle est INVALIDE (sinon on écraserait un choix de l'utilisateur en attente).
            if kind == "select" and cur not in opts:
                ss[key] = default if default in opts else opts[0]
            elif kind == "multi" and any(v not in opts for v in cur):
                ss[key] = [v for v in cur if v in opts]
            elif kind == "range":
                valide = isinstance(cur, (list, tuple)) and len(cur) == 2 and cur[0] in opts and cur[1] in opts
                if not valide:
                    ss[key] = default
            _label(label, icon)
            cb = {"decoupage": ("decoupage",), "region": ("region",), "prefecture": ("prefecture",), "commune": ("commune",)}.get(name)
            kw = {"on_change": _cascade, "args": (page, cb[0])} if cb else {}
            if kind == "select":
                st.selectbox(label, opts, key=key, label_visibility="collapsed", **kw)
            elif kind == "range":
                st.slider(label, min_value=int(opts[0]), max_value=int(opts[-1]), step=1, key=key, label_visibility="collapsed")
            else:
                st.multiselect(label, opts, key=key, label_visibility="collapsed", placeholder="Tous", **kw)
        if extras is not None:
            extras()
        if spec.get("note"):
            st.markdown(f'<div class="note" style="margin:6px 4px 12px 4px">{spec["note"]}</div>', unsafe_allow_html=True)
        # application immédiate : les valeurs courantes des widgets deviennent les filtres appliqués
        ss[f"applied_{page}"] = {n: ss[_key(page, n)] for n in spec["fields"] if _key(page, n) in ss}
        gstate.read_back(page, spec["fields"], _decoupage(page), ss[f"applied_{page}"])
        gstate.sync_to_url()
        extra = []
        a_ = ss[f"applied_{page}"]
        if "annee" in a_:
            extra.append(f"Année : {a_['annee']}")
        if "periode" in a_ and tuple(a_["periode"]) != (D.ANNEES_EC[0], D.ANNEES_EC[-1]):
            extra.append(f"Période : {a_['periode'][0]}–{a_['periode'][1]}")
        if a_.get("classes"):
            extra.append("Priorité : " + ", ".join(a_["classes"]))
        if "comparabilite" in a_ and sorted(a_["comparabilite"]) != ["HIGH", "MEDIUM"]:
            extra.append("Comparabilité : " + ", ".join(a_["comparabilite"]))
        ss["_chips_extra"] = extra
        if spec["fields"]:
            st.button("Réinitialiser", key=f"reset_{page}", type="secondary", width="stretch", on_click=_reset, args=(page,))
        st.markdown(f'<div class="side-foot"><img src="{flag_data_uri()}" alt=""><div><b>Data Lab · Défi 2</b>'
                    f'<span>Territoires du Togo</span></div></div>', unsafe_allow_html=True)
    return build_filters(page)


def build_filters(page: str) -> dict:
    """Convertit les valeurs appliquées en filtres exploitables par la couche de données (codes bruts du référentiel)."""
    a = st.session_state.get(f"applied_{page}", {})
    dec = D.DEC5 if page in PAGES_DECOUPAGE_FIXE else a.get("decoupage", D.DEC6)
    reg_label = a.get("region", D.ALL_REGIONS)
    region = D.region_code(dec, reg_label) if reg_label != D.ALL_REGIONS else None
    pref_nom = a.get("prefecture", D.ALL_PREFS)
    pref_nom = None if pref_nom == D.ALL_PREFS else pref_nom
    com_nom = a.get("commune", D.ALL_COMMUNES)
    com_nom = None if com_nom == D.ALL_COMMUNES else com_nom
    can = a.get("canton", D.ALL_CANTONS)
    can = None if can == D.ALL_CANTONS else can
    return {
        "page": page, "decoupage": dec, "region_col": D.region_col(dec),
        "region": region, "region_label": reg_label if region else None,
        "prefecture": D.raw_of("prefecture", pref_nom), "pref_nom": pref_nom,
        "commune": D.raw_of("commune", com_nom), "com_nom": com_nom, "canton": can,
        "annee": a.get("annee", D.ANNEES_ELEC[0]), "periode": tuple(a.get("periode", (D.ANNEES_EC[0], D.ANNEES_EC[-1]))),
        "comparabilite": a.get("comparabilite", ["HIGH", "MEDIUM"]), "classes": a.get("classes", []),
    }
