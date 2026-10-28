"""Formats français (mêmes conventions que le template : espace insécable pour les milliers, virgule décimale) ; N/D pour toute valeur absente."""
import numpy as np
import pandas as pd

ND = "N/D"
NBSP = "\u00a0"


def _na(x) -> bool:
    return x is None or (isinstance(x, float) and np.isnan(x)) or x is pd.NA or x is pd.NaT


def fmt_int(n) -> str:
    """19788 -> '19 788' ; valeur absente -> N/D (jamais 0 inventé)."""
    return ND if _na(n) else f"{int(round(float(n))):,}".replace(",", NBSP)


def fmt_dec(x, nd: int = 1) -> str:
    return ND if _na(x) else f"{float(x):,.{nd}f}".replace(",", NBSP).replace(".", ",")


def fmt_pct(x, nd: int = 1) -> str:
    return ND if _na(x) else f"{fmt_dec(x, nd)}%"


def fmt_pp(x, nd: int = 1) -> str:
    """Écart en points de pourcentage, avec signe : +3,2 pp / −4,0 pp."""
    return ND if _na(x) else f"{'+' if x >= 0 else '−'}{fmt_dec(abs(x), nd)}{NBSP}pp"


def fmt_signe(x, nd: int = 1, suffixe: str = "%") -> str:
    return ND if _na(x) else f"{'+' if x >= 0 else '−'}{fmt_dec(abs(x), nd)}{suffixe}"


def liste_fr(items, max_n: int = 4) -> str:
    """['A','B','C'] -> 'A, B et C' ; au-delà de max_n : 'A, B, C et 3 autres'."""
    items = [str(i) for i in items]
    if len(items) <= 1:
        return "".join(items)
    if len(items) > max_n:
        return ", ".join(items[:max_n]) + f" et {len(items) - max_n} autre{'s' if len(items) - max_n > 1 else ''}"
    return ", ".join(items[:-1]) + " et " + items[-1]
