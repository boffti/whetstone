"""Draw docs/brand/social-preview.png, the card GitHub shows when the repo's link is shared.

    uv run --group demo python scripts/demo/social_card.py [--guides]

It reuses the outlined text and the stone from docs/brand/banner-light.svg (made by brand.py), so
it needs no fonts. GitHub crops the card's edges in some places, so everything that matters sits
inside an 80 px margin of the 1280 x 640 card, as GitHub's repository card template asks.
`--guides` draws that margin in red, to check by eye. Upload the PNG in the repository's
Settings > General > Social preview.
"""

from __future__ import annotations

import argparse
import asyncio
import xml.etree.ElementTree as ET
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[2]
SVG_NS = "http://www.w3.org/2000/svg"
W, H, SAFE = 1280, 640, 80

# Each part's scale, and the space above it, in card pixels. They stack centred in the safe area.
LAYOUT = [("lockup", 1.2, 0), ("line1", 1.08, 40), ("line2", 1.08, 10), ("pills", 1.2, 34)]

PLACE = """([parts, W, H, SAFE]) => {
  const boxes = parts.map(([id, scale, gap]) => {
    const b = document.getElementById(id).getBBox();
    return { id, scale, gap, b, w: b.width * scale, h: b.height * scale };
  });
  const total = boxes.reduce((sum, x) => sum + x.gap + x.h, 0);
  let y = SAFE + (H - 2 * SAFE - total) / 2;
  for (const x of boxes) {
    y += x.gap;
    const left = (W - x.w) / 2;
    document.getElementById(x.id).setAttribute("transform",
      `translate(${left - x.b.x * x.scale} ${y - x.b.y * x.scale}) scale(${x.scale})`);
    y += x.h;
  }
  return boxes.map((x) => [x.id, Math.round(x.w), Math.round(x.h)]);
}"""


def card(guides: bool) -> str:
    banner = ET.parse(ROOT / "docs/brand/banner-light.svg").getroot()
    parts = [el for el in banner if el.tag != f"{{{SVG_NS}}}title"]
    _background, _dots, stone, title, line1, line2, *pills = parts
    xml = lambda els: "".join(ET.tostring(e, encoding="unicode") for e in els)  # noqa: E731
    guide = (
        f'<rect x="{SAFE}" y="{SAFE}" width="{W - 2 * SAFE}" height="{H - 2 * SAFE}" fill="none" stroke="#C0392B" stroke-width="2"/>'
        if guides
        else ""
    )
    svg = (
        f'<svg xmlns="{SVG_NS}" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
        f'<rect width="{W}" height="{H}" fill="#FAF9F5"/>'
        # The wordmark comes down level with the stone's middle; in the wide banner it sits higher.
        f'<g id="lockup">{xml([stone])}<g transform="translate(0 52)">{xml([title])}</g></g>'
        f'<g id="line1">{xml([line1])}</g><g id="line2">{xml([line2])}</g>'
        f'<g id="pills">{xml(pills)}</g>{guide}</svg>'
    )
    return svg.replace("ns0:", "").replace(":ns0", "")


async def render(out: Path, guides: bool) -> None:
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page(viewport={"width": W, "height": H})
        await page.set_content(f"<html><body style='margin:0'>{card(guides)}</body></html>")
        placed = await page.evaluate(PLACE, [LAYOUT, W, H, SAFE])
        await page.screenshot(path=out, clip={"x": 0, "y": 0, "width": W, "height": H})
        await browser.close()
    print(f"Wrote {out} ({out.stat().st_size // 1024} KB): " + ", ".join(f"{i} {w}x{h}" for i, w, h in placed))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--guides", action="store_true", help="draw GitHub's 80 px safe margin")
    parser.add_argument("--out", default=str(ROOT / "docs/brand/social-preview.png"))
    args = parser.parse_args()
    asyncio.run(render(Path(args.out), args.guides))


if __name__ == "__main__":
    main()
