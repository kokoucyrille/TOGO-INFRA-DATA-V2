"""Charte graphique (§10) : couleurs, contrastes WCAG, template Plotly unique, formats français, cartes KPI et badges."""
import plotly.graph_objects as go
import plotly.io as pio
import pandas as pd

# ─────────────── Couleurs de la charte ───────────────
PRIMAIRE, SECONDAIRE, ACCENT = "#003f8c", "#016b4b", "#fdcf00"          # charte du template-modele : bleu, vert institutionnel, or
FOND_PAGE, FOND_CARTE = "#f7fcfe", "#ffffff"
TEXTE, TEXTE_2 = "#1e3a4c", "#4f6270"
PRIORITE = {"Très haute": "#f20e36", "Haute": "#f58a1f", "Moyenne": "#fec902", "Faible": "#35a37a"}
GRILLE = "#e3edf2"

# Police du template : Nunito Sans (sous-ensemble embarqué dans assets/embedded_fonts.css).
POLICE_STREAMLIT = "Nunito Sans (embarquée dans assets/embedded_fonts.css)"
POLICE_PLOTLY = "Nunito Sans, -apple-system, 'Segoe UI', Roboto, Arial, sans-serif"
HAUTEUR_STANDARD = 380

# Statuts de données dérivées (§3) → (fond, texte)
STATUTS = {"OBSERVATION": (PRIMAIRE, "#FFFFFF"), "CALCUL": (SECONDAIRE, "#FFFFFF"), "ESTIMATION": (ACCENT, TEXTE),
           "PROXY": (PRIORITE["Moyenne"], TEXTE), "HYPOTHÈSE": ("#E3E8EC", TEXTE)}
FLAG_LIBELLE = {"HIGH": "Fiable", "MEDIUM": "Prudence", "LOW": "Non comparable"}
FLAG_COULEUR = {"HIGH": SECONDAIRE, "MEDIUM": ACCENT, "LOW": TEXTE_2}


# ─────────────── Contrastes (WCAG 2.1) ───────────────
def _lin(c: float) -> float:
    c /= 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_: str) -> float:
    h = hex_.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contraste(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def texte_lisible(fond: str) -> str:
    """Couleur de texte (sombre de la charte ou blanc) offrant le meilleur contraste sur `fond`."""
    return TEXTE if contraste(TEXTE, fond) >= contraste("#FFFFFF", fond) else "#FFFFFF"


def table_contrastes() -> pd.DataFrame:
    """Ratio de contraste WCAG de chaque paire texte/fond de la charte du template et des ajouts du tableau de bord (cible ≥ 4,5 : 1 pour le texte)."""
    paires = [
        ("Texte courant sur fond de page", TEXTE, FOND_PAGE), ("Texte courant sur blanc", TEXTE, FOND_CARTE), ("Titres bleus sur blanc", PRIMAIRE, FOND_CARTE),
        ("Vert institutionnel sur blanc", SECONDAIRE, FOND_CARTE), ("Blanc sur vert institutionnel (navbar, boutons)", "#ffffff", SECONDAIRE),
        ("Texte vert foncé sur or (menu actif)", "#004f31", ACCENT), ("Blanc sur or", "#ffffff", ACCENT), ("Or en texte sur blanc", ACCENT, FOND_CARTE),
        ("Rouge du gabarit en texte sur blanc", PRIORITE["Très haute"], FOND_CARTE), ("Rouge foncé ajouté pour le texte", "#c4102f", FOND_CARTE),
        ("Gris-bleu du gabarit en texte sur blanc", "#a2b8cc", FOND_CARTE), ("Gris-bleu foncé ajouté pour les notes", TEXTE_2, FOND_CARTE),
        ("Badge HIGH", "#004f31", "#e1f3ea"), ("Badge MEDIUM", "#5f4300", "#fff3c4"), ("Badge LOW", "#34424c", "#eceff1"),
        ("Badge priorité très haute", "#8f0b24", "#fdebef"), ("Badge priorité haute", "#6e3600", "#ffeed8"), ("Badge priorité moyenne", "#554200", "#fff8d6"),
    ]
    rows = []
    for nom, t, f in paires:
        r = contraste(t, f)
        rows.append(dict(paire=nom, texte=t, fond=f, ratio=round(r, 2), seuil=4.5, conforme=r >= 4.5))
    return pd.DataFrame(rows)


# ─────────────── Formats français ───────────────
ESPACE_FINE = "\u202f"


def fmt_int(x) -> str:
    return "—" if pd.isna(x) else f"{x:,.0f}".replace(",", ESPACE_FINE)


def fmt_dec(x, d=1) -> str:
    return "—" if pd.isna(x) else f"{x:,.{d}f}".replace(",", ESPACE_FINE).replace(".", ",")


def fmt_pct(x, d=1) -> str:
    return "—" if pd.isna(x) else fmt_dec(x, d) + "\u202f%"


# ─────────────── Template Plotly unique ───────────────
def _template() -> go.layout.Template:
    t = go.layout.Template(pio.templates["plotly_white"])
    t.layout.update(
        font=dict(family=POLICE_PLOTLY, size=13, color=TEXTE), paper_bgcolor=FOND_CARTE, plot_bgcolor=FOND_CARTE,
        colorway=[PRIMAIRE, SECONDAIRE, ACCENT, TEXTE_2, "#7A9CB5", "#8FBFB9"],
        title=dict(font=dict(size=16, color=PRIMAIRE), x=0.0, xanchor="left"),
        xaxis=dict(gridcolor=GRILLE, zerolinecolor=GRILLE, linecolor=TEXTE_2, ticks="outside"),
        yaxis=dict(gridcolor=GRILLE, zerolinecolor=GRILLE, linecolor=TEXTE_2),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0, font=dict(size=12)),
        margin=dict(l=10, r=20, t=70, b=90), height=HAUTEUR_STANDARD,
        separators=",\u202f",          # virgule décimale, espace fine pour les milliers
    )
    return t


pio.templates["defi2"] = _template()
pio.templates.default = "defi2"


def mise_en_forme(fig: go.Figure, titre: str, sous_titre: str = "", source: str = "", statut: str = "", note: str = "", hauteur: int = HAUTEUR_STANDARD) -> go.Figure:
    """Applique : titre-message, unité/période en sous-titre, source + statut + note en bas du graphique (positionnés en pixels)."""
    fig.update_layout(template="defi2", height=hauteur, title=dict(text=titre, subtitle=dict(text=sous_titre, font=dict(size=12, color=TEXTE_2))))
    ligne1 = " · ".join(x for x in [f"Source : {source}" if source else "", statut] if x)
    pied = "<br>".join(x for x in [ligne1, note] if x)
    if pied:
        zone = max(hauteur - 70 - 90, 120)                      # hauteur de la zone de tracé (marges haute 70, basse 90)
        fig.add_annotation(text=pied, xref="paper", yref="paper", x=0, y=-52 / zone, xanchor="left", yanchor="top",
                           showarrow=False, font=dict(size=11, color=TEXTE_2), align="left")
    return fig


# ─────────────── Composants HTML (cartes KPI, badges) ───────────────
def badge(statut: str) -> str:
    fond, txt = STATUTS.get(statut, STATUTS["HYPOTHÈSE"])
    return (f"<span style='display:inline-block;padding:1px 8px;border-radius:10px;background:{fond};color:{txt};"
            f"font-size:11px;font-weight:600;letter-spacing:.3px;vertical-align:middle'>{statut}</span>")


def badge_flag(flag: str) -> str:
    fond = FLAG_COULEUR.get(flag, TEXTE_2)
    return (f"<span style='display:inline-block;padding:1px 8px;border-radius:10px;background:{fond};color:{texte_lisible(fond)};"
            f"font-size:11px;font-weight:600'>{flag} · {FLAG_LIBELLE.get(flag, '')}</span>")


def carte_kpi(libelle: str, valeur: str, note: str = "", statut: str = "") -> str:
    """Carte KPI : fond blanc, bordure gauche 4 px primaire, libellé gris petit, valeur 28 px gras, source 11 px."""
    b = f" {badge(statut)}" if statut else ""
    return (f"<div style='background:{FOND_CARTE};border-left:4px solid {PRIMAIRE};border-radius:4px;padding:10px 14px;"
            f"box-shadow:0 1px 2px rgba(31,41,51,.08);height:100%'>"
            f"<div style='color:{TEXTE_2};font-size:13px'>{libelle}{b}</div>"
            f"<div style='color:{TEXTE};font-size:28px;font-weight:700;line-height:1.25'>{valeur}</div>"
            f"<div style='color:{TEXTE_2};font-size:11px'>{note}</div></div>")


def bandeau(texte: str, couleur: str = SECONDAIRE) -> str:
    """Bandeau « À retenir » : texte sombre sur fond blanc, bordure colorée."""
    return (f"<div style='background:{FOND_CARTE};border:1px solid {GRILLE};border-left:6px solid {couleur};border-radius:4px;"
            f"padding:10px 14px;color:{TEXTE};font-size:15px'>{texte}</div>")
