"""Draw the README's banner and feature icons as SVG, in light and dark versions.

    uv run --group demo python scripts/demo/brand.py path/to/IBMPlexSansCondensed-*.ttf

GitHub shows SVG images without outside fonts, so all text is converted to outlines from IBM Plex
Sans Condensed (SIL Open Font License; get it from google/fonts, ofl/ibmplexsanscondensed). The
output goes to docs/brand/ and is committed; the fonts are not.
"""

from __future__ import annotations

import sys
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/brand"
CLAY, STEEL, GREEN, AMBER = "#B8572F", "#2F6497", "#2E7A4D", "#E0A84F"
TAGLINE_1 = "Learn what you don\u2019t know. Relearn what you do."
TAGLINE_2 = "Keep every skill sharp, privately, around your own work."
THEMES = {
    "light": {"bg": "#FAF9F5", "rule": "#E3E1D8", "ink": "#141413", "soft": "#5A5954", "dots": "#E8E5DA"},
    "dark": {"bg": "#262624", "rule": "#3E3D39", "ink": "#F5F4EF", "soft": "#B9B7AE", "dots": "#33332F"},
}


class Type:
    """Text set in one font, as SVG path data."""

    def __init__(self, path: Path) -> None:
        self.font = TTFont(path)
        self.glyphs = self.font.getGlyphSet()
        self.cmap = self.font.getBestCmap()
        self.upm = self.font["head"].unitsPerEm

    def width(self, text: str, size: float) -> float:
        return sum(self.glyphs[self.cmap[ord(c)]].width for c in text) * size / self.upm

    def path(self, text: str, size: float, x: float, y: float) -> str:
        """Path data for `text` with its baseline at y."""
        scale = size / self.upm
        pen = SVGPathPen(self.glyphs)
        for c in text:
            glyph = self.glyphs[self.cmap[ord(c)]]
            glyph.draw(TransformPen(pen, (scale, 0, 0, -scale, x, y)))
            x += glyph.width * scale
        return pen.getCommands()


STONE = """<g transform="translate({x} {y}) scale({s})">
  <path d="M30 92 L130 112 L130 132 L30 112 Z" fill="#9C4526"/>
  <path d="M130 112 L210 82 L210 102 L130 132 Z" fill="#244C77"/>
  <path d="M30 92 L110 62 L160 72 L80 102 Z" fill="#D97757"/>
  <path d="M80 102 L160 72 L210 82 L130 112 Z" fill="#4A7FB8"/>
  <path d="M80 102 L160 72" stroke="#F5F4EF" stroke-width="2.5" stroke-linecap="round" opacity="0.85"/>
  <g fill="#F5F4EF" opacity="0.55"><circle cx="62" cy="88" r="1.6"/><circle cx="78" cy="82" r="1.3"/><circle cx="95" cy="76" r="1.6"/><circle cx="70" cy="95" r="1.2"/><circle cx="88" cy="89" r="1.5"/><circle cx="104" cy="83" r="1.2"/><circle cx="118" cy="74" r="1.4"/></g>
  <g fill="{amber}"><path d="M196 38 Q198 56 216 58 Q198 60 196 78 Q194 60 176 58 Q194 56 196 38 Z"/><path d="M222 32 Q223 40 230 41 Q223 42 222 50 Q221 42 214 41 Q221 40 222 32 Z"/></g>
</g>"""


def banner(theme: str, bold: Type, regular: Type, medium: Type) -> str:
    t = THEMES[theme]
    w, h = 1280, 380
    # Grit: a field of dots fading in from the right edge, like the stone's surface.
    dots = "".join(
        f'<circle cx="{x}" cy="{y}" r="{1.6 + ((x * 7 + y * 3) % 5) * 0.35:.2f}"/>'
        for x in range(900, 1260, 22)
        for y in range(28, 360, 22)
        if (x * 13 + y * 7) % 100 < (x - 880) / 4
    )
    title = bold.path("Whetstone", 96, 400, 165)
    lines = (TAGLINE_1, TAGLINE_2)
    size = min(38, 820 / max(regular.width(line, 1) for line in lines))  # fit the longer line
    line1 = regular.path(lines[0], size, 404, 222)
    line2 = regular.path(lines[1], size, 404, 266)
    pills, x = [], 404
    for label, color in (("Learn", CLAY), ("Relearn", STEEL), ("Sharpen", GREEN)):
        pw = medium.width(label, 24) + 40
        pills.append(f'<rect x="{x}" y="296" width="{pw:.1f}" height="44" rx="22" fill="{color}"/>')
        pills.append(f'<path d="{medium.path(label, 24, x + 20, 326)}" fill="#FFFFFF"/>')
        x += pw
        if label != "Sharpen":
            pills.append(
                f'<path d="M{x + 10} 318 h18 m-7 -7 l7 7 l-7 7" fill="none" stroke="{t["soft"]}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>'
            )
            x += 38
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" role="img" aria-labelledby="t">
<title id="t">Whetstone. {TAGLINE_1} {TAGLINE_2} Learn, relearn, sharpen.</title>
<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="28" fill="{t["bg"]}" stroke="{t["rule"]}" stroke-width="2"/>
<g fill="{t["dots"]}">{dots}</g>
{STONE.format(x=48, y=58, s=1.45, amber=AMBER)}
<path d="{title}" fill="{t["ink"]}"/>
<path d="{line1}" fill="{t["soft"]}"/>
<path d="{line2}" fill="{t["soft"]}"/>
{"".join(pills)}
</svg>
"""


# Feature icons: a solid tile in a brand colour with a cream glyph, readable in both themes.
GLYPHS = {
    "for-you": (
        CLAY,
        '<circle cx="28" cy="21" r="7"/><path d="M14 42 Q14 30 28 30 Q42 30 42 42 Z"/>'
        '<path d="M43 9 Q44 15 50 16 Q44 17 43 23 Q42 17 36 16 Q42 15 43 9 Z"/>',
    ),
    "systems": (
        STEEL,
        '<path d="M12 36 L28 20 L44 30" fill="none" stroke="#FAF9F5" stroke-width="3.5" stroke-linecap="round"/>'
        '<circle cx="12" cy="36" r="5.5"/><circle cx="28" cy="20" r="5.5"/><circle cx="44" cy="30" r="5.5"/>',
    ),
    "tests": (
        GREEN,
        '<path d="M14 18 l4 4 l7 -8 M14 30 l4 4 l7 -8 M14 42 l4 4 l7 -8" fill="none" stroke="#FAF9F5" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>'
        '<rect x="30" y="15" width="14" height="4" rx="2"/><rect x="30" y="27" width="14" height="4" rx="2"/><rect x="30" y="39" width="14" height="4" rx="2"/>',
    ),
    "spaced": (
        CLAY,
        '<path d="M40 22 A13 13 0 1 0 41 33" fill="none" stroke="#FAF9F5" stroke-width="4" stroke-linecap="round"/>'
        '<path d="M42 12 L42 23 L31 23 Z"/>',
    ),
    "agent": (
        STEEL,
        '<path d="M10 14 h36 a4 4 0 0 1 4 4 v18 a4 4 0 0 1 -4 4 h-20 l-9 8 v-8 h-7 a4 4 0 0 1 -4 -4 v-18 a4 4 0 0 1 4 -4 Z"/>'
        '<g fill="#2F6497"><circle cx="19" cy="27" r="3"/><circle cx="28" cy="27" r="3"/><circle cx="37" cy="27" r="3"/></g>',
    ),
    "design": (
        GREEN,
        '<rect x="9" y="13" width="15" height="11" rx="2"/><rect x="32" y="13" width="15" height="11" rx="2"/><rect x="20" y="34" width="16" height="11" rx="2"/>'
        '<path d="M24 18.5 h8 M39.5 24 L32 34 M16.5 24 L24 34" fill="none" stroke="#FAF9F5" stroke-width="2.5" stroke-linecap="round"/>',
    ),
    "local": (
        CLAY,
        '<rect x="13" y="25" width="30" height="21" rx="4"/><path d="M19 25 v-6 a9 9 0 0 1 18 0 v6" fill="none" stroke="#FAF9F5" stroke-width="4"/>'
        '<circle cx="28" cy="35" r="3.5" fill="#B8572F"/>',
    ),
    "mastery": (
        STEEL,
        '<rect x="9" y="25" width="38" height="7" rx="3.5" fill="#FAF9F5" opacity="0.35"/><rect x="9" y="25" width="26" height="7" rx="3.5"/>'
        '<path d="M38 14 Q39 19 44 20 Q39 21 38 26 Q37 21 32 20 Q37 19 38 14 Z"/>',
    ),
}


def icon(name: str) -> str:
    color, glyph = GLYPHS[name]
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 56 56" width="56" height="56" aria-hidden="true">'
        f'<rect width="56" height="56" rx="14" fill="{color}"/><g fill="#FAF9F5">{glyph}</g></svg>\n'
    )


def main() -> None:
    fonts = {Path(p).stem.split("-")[-1]: Type(Path(p)) for p in sys.argv[1:]}
    missing = {"SemiBold", "Regular", "Medium"} - set(fonts)
    if missing:
        raise SystemExit(f"Pass IBM Plex Sans Condensed .ttf files; missing weights: {', '.join(sorted(missing))}")
    (OUT / "icons").mkdir(parents=True, exist_ok=True)
    for theme in THEMES:
        (OUT / f"banner-{theme}.svg").write_text(banner(theme, fonts["SemiBold"], fonts["Regular"], fonts["Medium"]))
    for name in GLYPHS:
        (OUT / "icons" / f"{name}.svg").write_text(icon(name))
    print(f"Wrote {OUT.relative_to(ROOT)}: 2 banners, {len(GLYPHS)} icons")


if __name__ == "__main__":
    main()
