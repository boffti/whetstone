"""Record docs/demo.webp: Whetstone in a browser side pane, next to an AI agent's chat.

    uv run --group demo playwright install chromium        # once
    uv run --group demo python scripts/demo/record_demo.py

It builds a throwaway home for a sample learner, "Sam" (a profile, two finished questions and a few
weeks of history), starts the app on a free port, and plays a short session in headless Chromium:
Sam presses Prepare, the "agent" (this script) builds the question, Sam solves it with one nudge
in the editor's margin, then looks at Paths and Design. Frames come from Chrome's screencast and
are laid into the browser pane of docs/demo-frame.png (made by clean_frame.py) with ffmpeg, then
packed into an animated WebP with img2webp (from libwebp: `brew install webp`). WebP keeps the
window's soft shadow transparent, so the demo sits on either GitHub theme. Nothing touches your
own my/ folder.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import subprocess
from pathlib import Path

from demo_home import ROOT, install, running_app
from playwright.async_api import Page, async_playwright

from whetstone.store import Store

PANE = (1111, 121, 821, 1091)  # x, y, width, height of the pane's page area in demo-frame.png
MODULE, KEY = "thread-safe-memo-cache", "thread-safe-memo-cache/01-memoize"

FIRST_TRY = '''from collections.abc import Callable


class CachedAPI:
    """Wraps a slow, pure function. Each unique input is computed only once."""

    def __init__(self, compute: Callable[[int], int]) -> None:
        self._compute = compute
        self._cache: dict[int, int] = {}
        self._hits = self._misses = 0

    def get(self, n: int) -> int:
        if self._cache.get(n):
            self._hits += 1
            return self._cache[n]
        self._misses += 1
        self._cache[n] = self._compute(n)
        return self._cache[n]

    def stats(self) -> dict[str, int]:
        return {"hits": self._hits, "misses": self._misses}
'''
FIX = ("        if self._cache.get(n):", "        if n in self._cache:")
NOTE = "What does line 13 do when the saved value is 0?"
EXPLANATION = ".get() returned 0, and I treated a falsy value as missing. The key existed; the value was just falsy."


# ---------- The session ----------
CURSOR = """(() => {
  if (document.getElementById('demo-cursor')) return;
  const c = document.createElement('div');
  c.id = 'demo-cursor';
  c.innerHTML = '<svg width="22" height="22" viewBox="0 0 22 22"><path d="M3 2 L3 18 L7.5 13.8 L10.6 20.4 L13.4 19.2 L10.4 12.6 L16.4 12.4 Z" fill="#141413" stroke="#fff" stroke-width="1.4" stroke-linejoin="round"/></svg>';
  Object.assign(c.style, {position: 'fixed', left: '0', top: '0', zIndex: 99999, pointerEvents: 'none',
    transition: 'transform 480ms cubic-bezier(.3,.7,.2,1)', transform: 'translate(560px, 760px)', filter: 'drop-shadow(0 1px 2px rgba(0,0,0,.5))'});
  document.body.append(c);
})()"""


class Session:
    def __init__(self, page: Page, store: Store, home: Path) -> None:
        self.page, self.store, self.home = page, store, home

    async def pause(self, seconds: float) -> None:
        await asyncio.sleep(seconds)

    async def click(self, locator, wait: float = 0.35) -> None:
        """Glide the pointer to the element, then click it, so viewers can follow."""
        await locator.scroll_into_view_if_needed()
        box = await locator.bounding_box()
        await self.page.evaluate(CURSOR)
        await self.page.evaluate(
            "([x, y]) => { document.getElementById('demo-cursor').style.transform = `translate(${x}px, ${y}px)`; }",
            [box["x"] + box["width"] / 2 - 3, box["y"] + box["height"] / 2 - 2],
        )
        await self.pause(0.6)
        await locator.click()
        await self.pause(wait)

    async def hover(self, locator, wait: float = 1.4) -> None:
        """Glide the pointer to the element and rest there, so its popover opens."""
        await locator.scroll_into_view_if_needed()
        box = await locator.bounding_box()
        await self.page.evaluate(CURSOR)
        await self.page.evaluate(
            "([x, y]) => { document.getElementById('demo-cursor').style.transform = `translate(${x}px, ${y}px)`; }",
            [box["x"] + box["width"] / 2 - 3, box["y"] + box["height"] / 2 - 2],
        )
        await self.pause(0.5)
        await locator.hover()
        await self.pause(wait)

    async def type_code(self, code: str, per_line: float = 0.09) -> None:
        lines = code.splitlines()
        for i in range(1, len(lines) + 1):
            await self.page.evaluate(
                "([text, line]) => { const m = state.models['solution.py']; m.setValue(text);"
                " state.editor.setPosition({lineNumber: line, column: 999}); state.editor.revealLine(line); }",
                ["\n".join(lines[:i]) + "\n", i],
            )
            await self.pause(per_line)

    async def agent_builds(self) -> None:
        """Play the agent: claim the queued request, build the question, mark it done."""
        for _ in range(100):
            queued = [r for r in self.store.requests(open_only=True) if r["target"] == MODULE]
            if queued:
                break
            await self.pause(0.1)
        rid = queued[0]["id"]
        self.store.update_request(rid, "claimed")
        await self.pause(2.4)
        install(self.home, "memoize", MODULE, "01-memoize")
        self.store.update_request(rid, "done", KEY)

    async def run(self) -> None:
        page = self.page
        await self.pause(1.6)  # Today: Sam's focus, edges and week

        # Prepare a question from the focus list; the agent builds it.
        row = (
            page.locator("li, .edge").filter(has_text="Thread-safe cache and locks").filter(has=page.get_by_role("button", name="Prepare"))
        )
        await self.click(row.first.get_by_role("button", name="Prepare"))
        await self.agent_builds()
        start = page.get_by_role("link", name="Start").first
        await start.wait_for(timeout=15_000)
        await self.pause(0.8)
        await self.click(start, wait=1.4)

        # Read the problem, then write a first try in the editor. Its sections open over the code.
        await self.click(page.locator(".tab-code"), wait=0.6)
        await self.hover(page.locator("#peek-row .chip").nth(0), wait=1.3)
        await self.hover(page.locator("#peek-row .chip").nth(1), wait=1.6)
        await self.hover(page.locator(".editor-wrap"), wait=0.3)
        await self.type_code(FIRST_TRY)
        await self.pause(0.6)

        # Run: guess first, then the visible tests.
        await self.click(page.locator("#run-btn"))
        for pick in await page.locator("#results .guess-row").all():
            await self.click(pick.get_by_role("button", name="Pass"), wait=0.15)
        await self.click(page.get_by_role("button", name="Run with my guess"), wait=2.2)

        # Submit: guess again, then the hidden tests catch the slip.
        await self.click(page.locator("#submit-btn"))
        await self.click(page.locator("#results .guess-row").nth(0).get_by_role("button", name="Yes"), wait=0.15)
        await self.click(page.locator("#results .guess-row").nth(1).get_by_role("button", name="4"), wait=0.15)
        await self.click(page.get_by_role("button", name="Submit with my guess"), wait=2.6)

        # The agent, watching, asks one question in the margin at line 13.
        self.store.add_note(KEY, NOTE, 13)
        await page.locator(".pair-note").first.wait_for(timeout=10_000)
        await self.pause(2.6)

        # Sam fixes the line and submits again.
        await self.type_code(FIRST_TRY.replace(*FIX), per_line=0)
        await self.page.evaluate("() => { state.editor.setPosition({lineNumber: 13, column: 30}); state.editor.revealLineInCenter(13); }")
        await self.pause(1.2)
        await self.click(page.locator("#submit-btn"))
        await self.click(page.locator("#results .guess-row").nth(0).get_by_role("button", name="Yes"), wait=0.15)
        await self.click(page.locator("#results .guess-row").nth(1).get_by_role("button", name="5"), wait=0.15)
        await self.click(page.get_by_role("button", name="Submit with my guess"), wait=2.0)

        # Explain it in a sentence: the agent reads this later.
        box = page.locator(".explain textarea")
        if await box.count():
            await self.click(box, wait=0.2)
            await box.press_sequentially(EXPLANATION, delay=18)
            await self.click(page.locator(".explain").get_by_role("button", name="Save"), wait=1.6)

        # A quick look around: the paths, then system design.
        await self.click(page.locator("#nav-paths"), wait=1.6)
        await self.hover(page.locator("#paths-list .path-tile").first.locator("button.stop").nth(2), wait=1.8)
        await self.click(page.locator("#nav-design"), wait=2.6)


# ---------- Recording and encoding ----------
async def record(base: str, store: Store, home: Path, frames_dir: Path) -> list[tuple[float, Path]]:
    frames: list[tuple[float, Path]] = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        context = await browser.new_context(viewport={"width": PANE[2], "height": PANE[3]}, device_scale_factor=2, color_scheme="dark")
        await context.add_init_script("localStorage.setItem('whetstone-theme', 'dark');")
        page = await context.new_page()
        await page.goto(f"{base}/#/practice")
        await page.wait_for_selector("#home-body .home-row, #home-body li", timeout=20_000)
        await page.wait_for_timeout(1500)  # fonts and the editor settle before the first frame

        cdp = await context.new_cdp_session(page)

        async def on_frame(event: dict) -> None:
            path = frames_dir / f"f{len(frames):05d}.png"
            path.write_bytes(base64.b64decode(event["data"]))
            frames.append((event["metadata"]["timestamp"], path))
            await cdp.send("Page.screencastFrameAck", {"sessionId": event["sessionId"]})

        cdp.on("Page.screencastFrame", lambda e: asyncio.ensure_future(on_frame(e)))
        await cdp.send("Page.startScreencast", {"format": "png", "everyNthFrame": 1})
        await Session(page, store, home).run()
        await page.wait_for_timeout(1800)
        await cdp.send("Page.stopScreencast")
        await page.wait_for_timeout(300)
        await browser.close()
    return sorted(frames)


def encode(frames: list[tuple[float, Path]], backdrop: Path, out: Path, width: int, fps: int, speed: float, quality: int) -> None:
    listing = frames[0][1].parent / "frames.txt"
    lines = []
    for (t, path), (t_next, _) in zip(frames, frames[1:] + [(frames[-1][0] + 1.5, None)], strict=True):
        lines += [f"file '{path.name}'", f"duration {max(t_next - t, 0.001):.3f}"]
    lines.append(f"file '{frames[-1][1].name}'")
    listing.write_text("\n".join(lines) + "\n")
    x, y, w, h = PANE
    # ffmpeg lays each frame into the pane at a steady rate, keeping the backdrop's transparency...
    composed = listing.parent / "composed"
    composed.mkdir(exist_ok=True)
    graph = (
        f"[0:v]format=rgba[bg];[1:v]setpts=PTS/{speed},scale={w}:{h}:flags=lanczos,fps={fps}[app];"
        f"[bg][app]overlay={x}:{y}:shortest=1:format=auto,fps={fps},scale={width}:-1:flags=lanczos,format=rgba"  # the looped backdrop runs at 25 fps
    )
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-y", "-loop", "1", "-i", str(backdrop)]
        + ["-f", "concat", "-safe", "0", "-i", str(listing), "-filter_complex", graph, str(composed / "%05d.png")],
        check=True,
    )
    # ...and img2webp packs the frames into one looping animation with an alpha channel.
    pngs = [str(f) for f in sorted(composed.glob("*.png"))]
    subprocess.run(
        ["img2webp", "-loop", "0", "-lossy", "-q", str(quality), "-m", "4", "-d", str(round(1000 / fps)), *pngs, "-o", str(out)],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    # A transparent background colour, for any viewer that reads it instead of the page's.
    subprocess.run(["webpmux", "-set", "bgcolor", "0,0,0,0", str(out), "-o", str(out)], check=True, stdout=subprocess.DEVNULL)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--backdrop", default=str(ROOT / "docs/demo-frame.png"))
    parser.add_argument("--out", default=str(ROOT / "docs/demo.webp"))
    parser.add_argument("--width", type=int, default=1400, help="width of the animation in pixels")
    parser.add_argument("--quality", type=int, default=72, help="WebP quality, 0 to 100")
    parser.add_argument("--fps", type=int, default=12)
    parser.add_argument("--speed", type=float, default=1.25, help="play the session this much faster")
    args = parser.parse_args()

    with running_app() as (base, store, home, work):
        frames_dir = work / "frames"
        frames_dir.mkdir()
        frames = asyncio.run(record(base, store, home, frames_dir))
    print(f"{len(frames)} frames over {frames[-1][0] - frames[0][0]:.1f} s")
    encode(frames, Path(args.backdrop), Path(args.out), args.width, args.fps, args.speed, args.quality)
    print(f"Wrote {args.out} ({Path(args.out).stat().st_size / 1e6:.1f} MB). Scratch files: {work}")


if __name__ == "__main__":
    main()
