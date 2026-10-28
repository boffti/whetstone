"""Take the README screenshots in docs/screenshots/.

    uv run --group demo python scripts/demo/screenshots.py

It runs the app for the sample learner "Sam" (demo_home.py) in headless Chromium and photographs
each page at side-pane size (820 px wide, as next to an agent's chat), plus two at full screen, in
the light theme and again in the dark one (files ending in -dark).
Pages are set up the way a learner would leave them: a question with a failing hidden test and a
note from the agent, a path filtered by one module, a design drawn on the whiteboard and graded.
"""

from __future__ import annotations

import argparse
import asyncio
import shutil
from pathlib import Path

from demo_home import ROOT, install, running_app
from PIL import Image
from playwright.async_api import Page, async_playwright
from record_demo import FIRST_TRY, FIX, KEY, MODULE, NOTE

from whetstone.content import find_challenge
from whetstone.runner import grade_design

OUT = ROOT / "docs/screenshots"
PANE = {"width": 820, "height": 1100}
FULL = {"width": 1440, "height": 900}
DESIGN = "url-shortener/01-short-links"

DESIGN_DRAFT = """# Short links for a launch campaign

## Requirements

Create short links in bulk before launch and one at a time after. Redirect in under 50 ms at p99, count every click for the campaign report, and let some links expire.

## Estimates

50 million redirects a day is about 600 a second; the TV spot at 20:00 brings 20 times that for 15 minutes, so plan for 12,000 a second. 100 million links at about 500 bytes is 50 GB.

## API

POST /links {url, expires_at} returns {code}. GET /{code} redirects, or returns 410 once the link has expired.

## Data model

links(code PRIMARY KEY, url, expires_at, created_by). Clicks are events, aggregated per code and hour.

## High-level design

Redirects go from the CDN to stateless redirect servers, which read Redis, then a Postgres replica on a miss. Each redirect emits a click event to Kafka; an aggregator writes hourly counts.

## Deep dives

Codes come from a counter. The cache holds the 2 million active campaign links, about 1 GB.

## Trade-offs

A cache in front of the database means an edited link can be stale for up to the cache's time to live.

## Failure modes

If Redis is down, redirects fall back to the replica and get slower. If Kafka is down, the servers buffer clicks in memory for a few minutes.
"""

DRAWING = """async () => {
  // Measure labels in the handwriting font, not a fallback, or they overflow their boxes.
  await Promise.all([document.fonts.load("20px Excalifont"), document.fonts.load("16px Excalifont")]);
  const b = state.board, X = b.lib.X, at = {};
  const box = (id, x, y, w, text, type = "rectangle") => { at[id] = { x, y, w, h: 64 }; return { type, id, x, y, width: w, height: 64, label: { text } }; };
  // An arrow from the side of one box that faces the other, so Excalidraw binds both ends.
  const arrow = (from, to, text, extra = {}) => {
    const a = at[from], z = at[to];
    const right = z.x >= a.x + a.w, down = z.y >= a.y + a.h;
    const [sx, sy, ex, ey] = right ? [a.x + a.w, a.y + a.h / 2, z.x, z.y + z.h / 2]
      : down ? [a.x + a.w / 2, a.y + a.h, z.x + z.w / 2, z.y] : [a.x + a.w / 2, a.y, z.x + z.w / 2, z.y + z.h];
    return { type: "arrow", x: sx, y: sy, width: ex - sx, height: ey - sy, start: { id: from }, end: { id: to }, ...(text ? { label: { text } } : {}), ...extra };
  };
  const shapes = [
    box("user", 0, 170, 140, "Browser"),
    box("cdn", 280, 170, 160, "CDN edge"),
    box("api", 580, 170, 230, "Redirect service"),
    box("redis", 605, 0, 180, "Redis", "ellipse"),
    box("db", 950, 160, 230, "Postgres replica", "ellipse"),
    box("kafka", 580, 360, 230, "Click events"),
    box("agg", 950, 360, 230, "Hourly counts"),
  ];
  const elements = X.convertToExcalidrawElements([
    ...shapes,
    arrow("user", "cdn", "GET /x7Kp"),
    arrow("cdn", "api"),
    arrow("api", "redis", "read"),
    arrow("api", "db", "miss"),
    arrow("api", "kafka", "click", { strokeStyle: "dashed" }),
    arrow("kafka", "agg"),
  ]);
  b.api.updateScene({ elements });
  b.api.scrollToContent(elements, { fitToContent: true });
}"""

GRADE = {
    "summary": "A clear read path sized from the estimates, with clicks off the hot path. Code generation and the redirect status are not decided yet.",
    "points": {
        "unique-codes": {
            "verdict": "missing",
            "note": "Two servers create a link in the same millisecond. Who hands out the counter, and what if it is down?",
        },
        "cached-read-path": {"verdict": "covered", "quote": "The cache holds the 2 million active campaign links, about 1 GB."},
        "redirect-status": {
            "verdict": "partial",
            "quote": "GET /{code} redirects",
            "note": "Which status code? What does a browser do with it the second time?",
        },
        "async-click-counting": {
            "verdict": "covered",
            "quote": "Each redirect emits a click event to Kafka; an aggregator writes hourly counts.",
        },
        "expiry": {"verdict": "covered", "quote": "returns 410 once the link has expired"},
        "launch-hot-keys": {
            "verdict": "partial",
            "quote": "plan for 12,000 a second",
            "note": "At 20:00 one link takes most of that. What do you do before the spike?",
        },
        "abuse": {"verdict": "missing", "note": "Anyone can create a link. What stops a phishing link riding on your domain?"},
        "failure-modes": {"verdict": "covered", "quote": "If Redis is down, redirects fall back to the replica and get slower."},
    },
}


async def snap(page: Page, name: str, width: int) -> None:
    """Save a PNG at `width` pixels, reduced to 256 colors so the README stays light."""
    path = OUT / f"{name}.png"
    await page.screenshot(path=path)
    image = Image.open(path).convert("RGB")
    image = image.resize((width, round(image.height * width / image.width)), Image.LANCZOS)
    image.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).save(path, optimize=True)
    print(f"{path.relative_to(ROOT)}: {path.stat().st_size // 1024} KB")


async def code(page: Page, text: str) -> None:
    await page.evaluate("(text) => state.models['solution.py'].setValue(text)", text)


async def submit_skipping_the_guess(page: Page) -> None:
    await page.click("#submit-btn")
    skip = page.locator("#results").get_by_role("button", name="Skip")
    if await skip.count():
        await skip.click()
    await page.wait_for_selector("#results .verdict", timeout=30_000)


async def take(base: str, store, home: Path, theme: str) -> None:
    """Every shot in one theme. Dark ones get a -dark suffix; the README picks by the reader's theme."""
    OUT.mkdir(parents=True, exist_ok=True)

    async def shot(page: Page, name: str, width: int) -> None:
        await snap(page, name if theme == "light" else f"{name}-{theme}", width)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch()

        async def open_page(viewport: dict) -> Page:
            context = await browser.new_context(viewport=viewport, device_scale_factor=2, color_scheme=theme)
            await context.add_init_script(f"localStorage.setItem('whetstone-theme', '{theme}');")
            return await context.new_page()

        page = await open_page(PANE)

        # Today and Progress
        await page.goto(f"{base}/#/practice")
        await page.wait_for_selector("#home-body li", timeout=20_000)
        await page.wait_for_timeout(800)
        await shot(page, "today", 1000)
        await page.goto(f"{base}/#/progress")
        await page.wait_for_timeout(1200)
        await shot(page, "progress", 1000)

        # A question: the guess before the first run, then a failing hidden test with the agent's note.
        install(home, "memoize", MODULE, "01-memoize")
        await page.goto(f"{base}/#/{KEY}")
        await page.reload()
        await page.wait_for_selector("#challenge-title", timeout=20_000)
        await page.wait_for_timeout(1500)
        await page.click(".tab-code")
        await code(page, FIRST_TRY)
        # In a side pane each section of the problem opens over the editor.
        await page.locator("#peek-row .chip").nth(1).click()
        await page.wait_for_timeout(400)
        await shot(page, "question-sections", 1000)
        await page.keyboard.press("Escape")
        await page.click("#run-btn")
        await page.wait_for_selector("#results .guess-row")
        for row in await page.locator("#results .guess-row").all():
            await row.get_by_role("button", name="Pass").click()
        await page.wait_for_timeout(300)
        await shot(page, "question-guess", 1000)
        await page.get_by_role("button", name="Run with my guess").click()
        await page.wait_for_selector("#results .verdict", timeout=30_000)
        await submit_skipping_the_guess(page)
        store.add_note(KEY, NOTE, 13)
        await page.wait_for_selector(".pair-note", timeout=10_000)
        await page.evaluate("() => { state.editor.revealLineInCenter(13); }")
        await page.wait_for_timeout(600)
        await shot(page, "question-note", 1000)

        full = await open_page(FULL)
        await full.goto(f"{base}/#/{KEY}")
        await full.wait_for_selector("#challenge-title", timeout=20_000)
        await full.wait_for_timeout(1500)
        await submit_skipping_the_guess(full)
        await full.wait_for_selector(".pair-note", timeout=10_000)
        await full.click(".tab[data-tab='problem']")
        await full.wait_for_timeout(600)
        await shot(full, "full-question", 1600)

        await code(page, FIRST_TRY.replace(*FIX))
        await submit_skipping_the_guess(page)
        await page.wait_for_timeout(600)
        await shot(page, "question-solved", 1000)

        # The same idea, prepared again for a company: the header links the versions.
        original = home / "tracks" / MODULE / "01-memoize"
        (original / "challenge.yaml").write_text((original / "challenge.yaml").read_text() + "framing: work\n")
        again = original.parent / "02-memoize-doordash"
        shutil.copytree(original, again)
        yaml_text = (again / "challenge.yaml").read_text().replace("framing: work\n", "")
        (again / "challenge.yaml").write_text(yaml_text + f"variant_of: {KEY}\nframing: company:DoorDash\n")
        await page.goto(f"{base}/#/{KEY}")
        await page.reload()
        await page.wait_for_selector("#challenge-versions .version", timeout=20_000)
        await page.click(".tab[data-tab='problem']")
        await page.wait_for_timeout(600)
        await shot(page, "question-versions", 1000)

        # Paths: filtered by one module, then one path's route.
        await page.goto(f"{base}/#/paths")
        await page.wait_for_selector("#paths-list .path-tile", timeout=20_000)
        await page.locator("#paths-list .path-tile button.stop[data-focus]").first.click()
        await page.wait_for_timeout(500)
        await page.evaluate("() => document.querySelector('#paths').scrollTo(0, 0)")
        await shot(page, "paths", 1000)
        await page.locator("#paths-list .path-open").first.click()
        await page.wait_for_timeout(700)
        await shot(page, "path-detail", 1000)
        await page.keyboard.press("Escape")
        # Pointing at a stop shows its module.
        await page.click("#p-clear")
        await page.wait_for_timeout(400)
        stop = page.locator("#paths-list .path-tile").nth(1).locator("button.stop[data-s='built'], button.stop[data-focus]").first
        await stop.scroll_into_view_if_needed()
        await page.wait_for_timeout(300)
        await stop.hover()
        await page.wait_for_selector("#stop-tip:popover-open")
        await page.wait_for_timeout(200)
        await shot(page, "path-stop", 1000)
        await page.mouse.move(0, 0)  # let go of the stop, so its popover closes before the next page

        # Catalog and Design
        await page.goto(f"{base}/#/catalog")
        await page.wait_for_selector("#catalog-grid .row", timeout=20_000)
        await page.wait_for_timeout(500)
        await shot(page, "catalog", 1000)
        # Prepare asks what the question is for.
        await page.locator(".req").get_by_role("button", name="Prepare").first.click()
        await page.wait_for_selector("#prep-pop:popover-open")
        await page.wait_for_timeout(900)  # the module's companies load in
        await shot(page, "prepare-for", 1000)
        await page.keyboard.press("Escape")
        await page.goto(f"{base}/#/design")
        await page.wait_for_selector("#design-list .row", timeout=20_000)
        await page.wait_for_timeout(500)
        await shot(page, "design", 1000)

        # A design: drawn on the whiteboard, previewed as the agent reads it, then graded.
        store.save_draft(DESIGN, DESIGN_DRAFT)
        await page.goto(f"{base}/#/{DESIGN}")
        await page.wait_for_selector("#challenge-title", timeout=20_000)
        await page.wait_for_timeout(1200)
        await page.click(".tab-code")
        await page.click(".file-tab[data-file='Whiteboard']")
        await page.wait_for_function("() => state.board && state.board.api", timeout=30_000)
        await page.wait_for_timeout(1200)
        await page.evaluate(DRAWING)
        await page.wait_for_timeout(2500)  # the drawing saves a second after it changes
        await shot(page, "design-whiteboard", 1000)
        await page.click(".file-tab[data-file='Preview']")
        await page.wait_for_selector("#preview .diagram svg", timeout=20_000)
        await page.evaluate("() => { const h = [...document.querySelectorAll('#preview h2')].pop(); h.scrollIntoView({block: 'start'}); }")
        await page.wait_for_timeout(500)
        await shot(page, "design-preview", 1000)

        challenge = find_challenge(home / "tracks", *DESIGN.split("/"))
        grade, problems = grade_design(challenge, GRADE)
        assert not problems, problems
        store.add_review(DESIGN, grade["points"], grade["summary"])
        store.record_run(DESIGN, "submit", grade["status"], grade["covered"], grade["total"], 0.0, DESIGN_DRAFT)
        await page.reload()
        await page.wait_for_selector("#results .verdict", state="attached", timeout=20_000)
        await page.click(".tab-code")
        await page.click(".file-tab[data-file='design.md']")
        await page.evaluate("() => document.querySelector('.bench').classList.remove('results-hidden')")
        await page.wait_for_timeout(600)
        await shot(page, "design-review", 1000)

        full_paths = await open_page(FULL)
        await full_paths.goto(f"{base}/#/paths")
        await full_paths.wait_for_selector("#paths-list .path-tile", timeout=20_000)
        await full_paths.click("#p-foryou")
        await full_paths.wait_for_timeout(800)
        await shot(full_paths, "full-paths", 1600)
        await browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--theme", choices=["light", "dark", "both"], default="both")
    args = parser.parse_args()
    for theme in ("light", "dark") if args.theme == "both" else (args.theme,):
        with running_app() as (base, store, home, _):  # a fresh learner per theme: each run changes it
            asyncio.run(take(base, store, home, theme))


if __name__ == "__main__":
    main()
