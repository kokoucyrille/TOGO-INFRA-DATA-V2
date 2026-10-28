"""Cartes « Priorité » de la page Recommandations : en-tête (icône, titre, badge) + lignes d'actions."""
from __future__ import annotations

import html


def create_action_row(tag: str, label: str, text: str) -> str:
    """Une ligne d'action : badge (A1…), titre en gras, description, chevron à droite."""
    return (f'<div class="reco-row"><span class="reco-tag">{html.escape(tag)}</span>'
            f'<span class="reco-text"><b>{html.escape(label)}</b> : {html.escape(text)}</span>'
            f'<i class="fa-solid fa-chevron-right reco-chev"></i></div>')


def create_priority_card(icon_html: str, title: str, title_color: str, badge: str, actions: list[tuple[str, str, str]]) -> str:
    """HTML d'une carte de priorité. `actions` : liste de (badge, titre, description)."""
    rows = "".join(create_action_row(*a) for a in actions)
    return (f'<div class="reco-card"><div class="reco-head"><div class="reco-ico">{icon_html}</div>'
            f'<span class="reco-title" style="color:{title_color}">{html.escape(title)}</span>'
            f'<span class="reco-badge">{html.escape(badge)}</span></div><div class="reco-rows">{rows}</div></div>')
