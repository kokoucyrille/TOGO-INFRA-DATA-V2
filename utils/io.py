"""Chemins relatifs et chargement des données brutes."""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "outputs" / "data"

FICHIERS = {
    "pop2022": "observationdata-kwwolwb.csv",
    "pop2010": "observationdata-sapxctg.csv",
    "elec": "observationdata-puncgpd.csv",
    "etat_civil": "observationdata-vrsicxf.csv",
    "identite": "observationdata-fsemhj.csv",
    "ceet": "file-agences-ceet-23-12-2024-11-06-42.csv",
    "tde": "file-agences-togolaise-des-eaux-tde-19-12-2024-17-48-23.csv",
    "meta_ceet": "metadata_agences_ceet.csv",
    "meta_tde": "metadata_agences_tde.csv",
}


def load_data(raw_dir: Path = RAW) -> dict:
    """Charge tous les CSV bruts en texte (aucune conversion implicite) : {nom: DataFrame}."""
    return {k: pd.read_csv(Path(raw_dir) / f, dtype=str, keep_default_na=False, encoding="utf-8")
            for k, f in FICHIERS.items()}


def fmt_int(x) -> str:
    """Format français des entiers : espace fine insécable pour les milliers."""
    return f"{x:,.0f}".replace(",", "\u202f")


def fmt_pct(x, d=1) -> str:
    return f"{x:.{d}f}".replace(".", ",") + " %"
