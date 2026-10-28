"""
Génère assets/embedded_fonts.css : polices Nunito Sans + sous-ensemble de Font Awesome (icônes réellement
utilisées) encodés en base64 DANS le CSS. Le dashboard n'a ainsi besoin ni d'Internet, ni du service de fichiers
statiques de Streamlit, ni d'un fichier de configuration pour afficher ses icônes et sa typographie.

À relancer après avoir ajouté une icône `fa-xxx` dans le code :

    pip install fonttools brotli
    npm pack @fortawesome/fontawesome-free @fontsource/nunito-sans   # puis décompresser les deux archives
    python tools/build_embedded_fonts.py <dossier fontawesome-free/package> <dossier nunito-sans/package/files>
"""
from __future__ import annotations

import base64
import io
import re
import sys
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "embedded_fonts.css"
SKIP = {"solid", "regular", "brands", "fw", "classic"}


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def fa_codepoints(css_path: Path) -> dict[str, str]:
    """nom d'icône (sans 'fa-') -> point de code hexadécimal, alias compris."""
    css = css_path.read_text(encoding="utf-8")
    table: dict[str, str] = {}
    for sel, code in re.findall(r'((?:\.fa-[a-z0-9-]+,?)+)\{--fa:"\\([0-9a-f]+)"\}', css):
        for name in sel.split(","):
            table[name.removeprefix(".fa-")] = code
    return table


def used_icons() -> tuple[set[str], set[str]]:
    """(noms d'icônes `fa-xxx`, points de code `--fa:"\\fxxx"`) trouvés dans le code Python du projet."""
    names, codes = set(), set()
    for f in ROOT.rglob("*.py"):
        if "tools" in f.parts:
            continue
        txt = f.read_text(encoding="utf-8")
        names |= {n for n in re.findall(r"fa-([a-z0-9]+(?:-[a-z0-9]+)*)", txt) if n not in SKIP}
        codes |= set(re.findall(r'--fa:\s*"\\+([0-9a-f]+)"', txt))
    return names, codes


def main(fa_dir: Path, nunito_dir: Path) -> None:
    table = fa_codepoints(fa_dir / "css" / "all.min.css")
    names, codes = used_icons()
    missing = sorted(n for n in names if n not in table)
    if missing:
        sys.exit(f"Icônes inconnues de Font Awesome : {missing}")
    wanted = {table[n] for n in names} | codes

    # --- sous-ensemble de la police d'icônes ---
    opts = subset.Options(flavor="woff2", layout_features=[], notdef_outline=False, glyph_names=False)
    font = TTFont(fa_dir / "webfonts" / "fa-solid-900.woff2")
    sub = subset.Subsetter(opts)
    sub.populate(unicodes=[int(c, 16) for c in wanted])
    sub.subset(font)
    buf = io.BytesIO()
    font.flavor = "woff2"
    font.save(buf)
    icon_font = buf.getvalue()

    css = ["/* GÉNÉRÉ par tools/build_embedded_fonts.py — ne pas modifier à la main. */"]
    for w in (400, 600, 700, 800):
        data = (nunito_dir / f"nunito-sans-latin-{w}-normal.woff2").read_bytes()
        css.append("@font-face{font-family:'Nunito Sans';font-style:normal;font-display:swap;font-weight:%d;"
                   "src:url(data:font/woff2;base64,%s) format('woff2');}" % (w, b64(data)))
    css.append("@font-face{font-family:'Font Awesome 7 Free';font-style:normal;font-display:block;font-weight:900;"
               "src:url(data:font/woff2;base64,%s) format('woff2');}" % b64(icon_font))
    css.append(".fa-solid{-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale;display:inline-block;"
               "font-family:'Font Awesome 7 Free';font-style:normal;font-variant:normal;font-weight:900;line-height:1;"
               "text-align:center;text-rendering:auto;width:1.25em;}")
    css.append(".fa-solid::before{content:var(--fa);}")
    css += [".fa-%s{--fa:\"\\%s\";}" % (n, table[n]) for n in sorted(names)]
    OUT.write_text("\n".join(css), encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)} : {OUT.stat().st_size // 1024} Ko, {len(names)} icônes + {len(codes)} codes CSS, "
          f"police d'icônes {len(icon_font) // 1024} Ko")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(Path(sys.argv[1]), Path(sys.argv[2]))
