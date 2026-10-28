"""État global des filtres territoriaux, partagé entre toutes les pages (st.session_state) et synchronisé avec l'URL (st.query_params).

Global : découpage, région, préfecture, commune, canton. Chaque page garde ses propres widgets (clés `w_<page>_<nom>`) ; ce module les (re)remplit à l'entrée
d'une page depuis l'état global, et recopie leurs valeurs dans l'état global après chaque exécution. Une recherche ou un clic sur une carte passent par
`request()` (état « en attente » appliqué avant l'instanciation des widgets, puis `st.rerun()`), car un widget déjà instancié ne peut plus être modifié.
Région : le code global est celui du découpage 2022 (DAGL = Grand Lomé) ; sur une page à 5 régions historiques, DAGL est lu comme MARITIME.
"""
from __future__ import annotations

import streamlit as st

from data import loader as D

FIELDS = ("decoupage", "region", "prefecture", "commune", "canton")
KEY = {"decoupage": "g_dec", "region": "g_region", "prefecture": "g_pref", "commune": "g_com", "canton": "g_can"}
QP = {"decoupage": "dec", "region": "reg", "prefecture": "pref", "commune": "com", "canton": "can"}
LOWER = {"decoupage": (), "region": ("prefecture", "commune", "canton"), "prefecture": ("commune", "canton"), "commune": ("canton",), "canton": ()}


def get(name: str):
    return st.session_state.get(KEY[name])


def snapshot() -> dict:
    return {n: get(n) for n in FIELDS}


def _set(name: str, value) -> None:
    st.session_state[KEY[name]] = value


def reset_all() -> None:
    for n in FIELDS:
        _set(n, None)


def dec_of(page_dec: str | None) -> str:
    return page_dec or get("decoupage") or D.DEC6


def region_label(dec: str, code: str | None) -> str | None:
    if not code:
        return None
    if dec == D.DEC5 and code == "DAGL":
        code = "MARITIME"
    return D.labels(dec).get(code)


def widget_value(name: str, dec: str):
    """Valeur que doit prendre le widget `name` d'après l'état global (None = valeur par défaut « Tous/Toutes »)."""
    if name == "decoupage":
        return get("decoupage")
    if name == "region":
        return region_label(dec, get("region"))
    return get(name)


def apply_to_widgets(page: str, fields: list, dec_for_page, key_fn) -> None:
    """Pousse l'état global dans les widgets de la page (à appeler AVANT leur instanciation)."""
    dec = dec_for_page
    for n in fields:
        if n not in FIELDS:
            continue
        v = widget_value(n, dec)
        key = key_fn(page, n)
        defaults = {"decoupage": D.DEC6, "region": D.ALL_REGIONS, "prefecture": D.ALL_PREFS, "commune": D.ALL_COMMUNES, "canton": D.ALL_CANTONS}
        st.session_state[key] = v if v else defaults[n]


def read_back(page: str, fields: list, dec: str, values: dict) -> None:
    """Recopie les valeurs de widgets (libellés) dans l'état global ; `values` : {nom: libellé}. N'écrase pas DAGL si la page lit MARITIME."""
    before = snapshot()
    for n in fields:
        if n not in FIELDS or n not in values:
            continue
        lab = values[n]
        if n == "decoupage":
            if page_free_dec(page):
                _set(n, None if lab == D.DEC6 else lab)
            continue
        if n == "region":
            code = D.region_code(dec, lab) if lab != D.ALL_REGIONS else None
            if code is None:
                if get("region") is not None and lab == D.ALL_REGIONS:
                    _set("region", None)
            elif region_label(dec, get("region")) != lab:          # changement réel (sinon on garde DAGL / MARITIME tel quel)
                _set("region", code)
            continue
        none_lab = {"prefecture": D.ALL_PREFS, "commune": D.ALL_COMMUNES, "canton": D.ALL_CANTONS}[n]
        _set(n, None if lab == none_lab else lab)
    # un niveau supérieur modifié efface les niveaux inférieurs que la page ne pilote pas
    for n in FIELDS:
        if before[n] != get(n):
            for low in LOWER[n]:
                if low not in fields:
                    _set(low, None)


def page_free_dec(page: str) -> bool:
    return page not in {"services", "priorites"}


# ───────────────────────── demandes (recherche, clic sur carte) ─────────────────────────
def request(**kw) -> None:
    """Demande de changement de territoire (valeurs : région = code, autres = nom d'affichage ; None = efface). Appliquée au prochain run, puis rerun."""
    st.session_state["_pending_g"] = kw
    st.rerun()


def request_cb(**kw) -> None:
    """Version pour les callbacks (`on_change`) : pas de rerun explicite, Streamlit relance déjà le script."""
    st.session_state["_pending_g"] = kw


def apply_pending() -> bool:
    kw = st.session_state.pop("_pending_g", None)
    if not kw:
        return False
    for n in FIELDS:
        if n in kw:
            _set(n, kw[n])
            for low in LOWER[n]:
                if low not in kw:
                    _set(low, None)
    return True


def hierarchy_for(kind: str, nom: str) -> dict:
    """Valeurs globales complètes (région, préfecture, commune…) pour un territoire désigné par son type et son nom."""
    T = D.load_tables()
    h = T["hier"]
    if kind == "region":
        return dict(region=nom, prefecture=None, commune=None, canton=None)
    if kind == "prefecture":
        r = h[h.pref_nom == nom]
        return dict(region=r.region_6.iloc[0] if len(r) else None, prefecture=nom, commune=None, canton=None)
    if kind == "commune":
        r = h[h.com_nom == nom]
        return dict(region=r.region_6.iloc[0], prefecture=r.pref_nom.iloc[0], commune=nom, canton=None)
    c = T["canton"]
    r = c[(c.nom == nom) & (c.niveau_feuille == "canton")]
    if len(r) == 0:
        return {}
    r = r.iloc[0]
    pn = T["pref_nom"].get(r.prefecture)
    cn = T["commune"].set_index("commune").nom.get(r.commune)
    return dict(region=r.region_6, prefecture=pn, commune=cn, canton=nom)


# ───────────────────────── URL partageable ─────────────────────────
def load_from_url() -> None:
    """Au premier passage de la session : lit les filtres dans l'URL (?reg=KARA&pref=Kozah…)."""
    if st.session_state.get("_qp_loaded"):
        return
    st.session_state["_qp_loaded"] = True
    try:
        qp = st.query_params
        for n in FIELDS:
            v = qp.get(QP[n])
            if v:
                _set(n, v)
    except Exception:
        pass


def sync_to_url(extra: dict | None = None) -> None:
    """Écrit les filtres actifs dans l'URL (la page est déjà dans le chemin). Sans effet si rien n'a changé."""
    try:
        want = {QP[n]: str(get(n)) for n in FIELDS if get(n)}
        if extra:
            want.update({k: str(v) for k, v in extra.items() if v not in (None, "")})
        cur = {k: st.query_params.get(k) for k in set(QP.values()) | set(extra or {})}
        cur = {k: v for k, v in cur.items() if v}
        if cur != want:
            st.query_params.clear()
            st.query_params.update(want)
    except Exception:
        pass


# ───────────────────────── puces de rappel des filtres actifs ─────────────────────────
def chips(extra: list[str] | None = None) -> list[str]:
    out = []
    dec = get("decoupage")
    if dec:
        out.append(f"Découpage : {dec}")
    r = get("region")
    if r:
        out.append(f"Région : {D.LABEL6.get(r, r)}")
    for n, lab in (("prefecture", "Préfecture"), ("commune", "Commune"), ("canton", "Canton")):
        if get(n):
            out.append(f"{lab} : {get(n)}")
    return out + list(extra or [])


# ───────────────────────── recherche d'un territoire ─────────────────────────
@st.cache_data(show_spinner=False)
def search_index() -> dict:
    """{libellé affiché : (type, nom)} pour toutes les régions, préfectures, communes et cantons."""
    T = D.load_tables()
    idx = {}
    for code in D.ORDRE:
        idx[f"Région · {D.LABEL6[code]}"] = ("region", code)
    for n in sorted(T["pref_nom"].values()):
        idx[f"Préfecture · {n}"] = ("prefecture", n)
    for n in sorted(T["commune"].nom.unique()):
        idx[f"Commune · {n}"] = ("commune", n)
    c = T["canton"]
    for _, r in c[c.niveau_feuille == "canton"].sort_values("nom").iterrows():
        idx.setdefault(f"Canton · {r.nom} ({T['pref_nom'].get(r.prefecture, r.prefecture)})", ("canton", r.nom))
    return idx


def on_search() -> None:
    lab = st.session_state.get("g_search")
    if not lab:
        return
    kind, nom = search_index()[lab]
    request_cb(**hierarchy_for(kind, nom))
    st.session_state["g_search"] = None


def handle_click(key: str, ids: list, resolver) -> None:
    """Traite un clic sur une carte / un classement : n'agit que lorsque la sélection CHANGE (sinon une ancienne sélection, conservée par le graphique,
    écraserait à chaque exécution le choix fait dans la barre latérale). `resolver(id)` → arguments de `request()` (ou None)."""
    sig = tuple(ids or ())
    if sig == st.session_state.get(f"_click_{key}", ()):
        return
    st.session_state[f"_click_{key}"] = sig
    if not sig:
        return
    kw = resolver(sig[-1])
    if kw:
        request(**kw)


def resolver_for(level: str, frame, label: str = "Territoire", idcol: str = "id"):
    """Résolveur de clic pour `handle_click` : `frame` porte l'identifiant (`id`) et le nom (`Territoire`) des territoires affichés au niveau `level`."""
    names = dict(zip(frame[idcol], frame[label]))
    kind = {"Région": "region", "Préfecture": "prefecture", "Commune": "commune", "Canton": "canton"}.get(level)

    def _r(i):
        if i not in names or kind is None:
            return None
        if kind == "region":
            return dict(region=i, prefecture=None, commune=None, canton=None)
        try:
            return hierarchy_for(kind, names[i]) or None
        except Exception:                                        # territoire sans correspondance dans la hiérarchie : on n'agit pas
            return None
    return _r
