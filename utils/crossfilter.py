"""Filtrage croisé : applique la sélection faite dans le classement aux jeux de données des autres éléments de la page (sans dépendance Streamlit)."""
import pandas as pd


def restreindre(code: str, d: pd.DataFrame, ids, com_g: pd.DataFrame, can_g: pd.DataFrame, qua_g: pd.DataFrame, region_col: str):
    """`code` : niveau du classement (region, prefecture, commune, canton, quartier) ; `d` : table du niveau (colonne id_aff) ; `ids` : identifiants sélectionnés.

    Retourne (communes, cantons, quartiers, ids_en_surbrillance). Sans sélection, rien ne change.
    """
    ids = [i for i in (ids or []) if i in set(d.id_aff)]
    if not ids:
        return com_g, can_g, qua_g, []
    rows = d[d.id_aff.isin(ids)]
    if code == "region":
        codes = set(rows.code_region)
        return tuple(x[x[region_col].isin(codes)] for x in (com_g, can_g, qua_g)) + ([],)
    if code == "prefecture":
        prefs = set(rows.prefecture)
        return tuple(x[x.prefecture.isin(prefs)] for x in (com_g, can_g, qua_g)) + ([],)
    if code == "commune":
        coms = set(rows.commune)
        return com_g[com_g.territoire_id.isin(ids)], can_g[can_g.commune.isin(coms)], qua_g[qua_g.commune.isin(coms)], ids
    return com_g, can_g, qua_g, ids          # canton / quartier : surbrillance seulement
