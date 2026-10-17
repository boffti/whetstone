"""Turn a screenshot of an agent's desktop app into the backdrop for docs/demo.webp.

The screenshot shows the agent's chat on the left and an empty browser pane on the right. This
paints over everything personal (the list of other threads and the account name) with plain
placeholder bars, which leak nothing, unlike a blur. It also titles the pane "Whetstone" with
localhost:8000 in its address bar. The window's shadow stays transparent, so the demo sits on
either GitHub theme. record_demo.py then plays the app inside the pane.

    uv run --group demo python scripts/demo/clean_frame.py screenshot.png docs/demo-frame.png

The pixel boxes below fit the 2000 x 1299 screenshot this was made from. For a new screenshot,
measure the boxes again and update PANE in record_demo.py too.
"""

import random
import sys

from PIL import Image, ImageDraw, ImageFont

SIDEBAR = (66, 286, 332, 1178)  # every thread below the current one
ACCOUNT = (66, 1184, 332, 1214)  # the account name and plan
TAB_TITLE = (1116, 55, 1206, 77)  # the title and the new-tab button
URL_TEXT = (1206, 93, 1921, 110)
PANE = (1111, 121, 1931, 1211)  # the browser pane's page area
SIDEBAR_BG, PANE_BG, FIELD_BG = (16, 16, 16), (24, 24, 24), (35, 35, 35)
FONT = "/System/Library/Fonts/SFNS.ttf"


def clean(src: str, dest: str) -> None:
    page = Image.open(src).convert("RGBA")  # keep the shadow's transparency
    draw = ImageDraw.Draw(page)
    rng = random.Random(7)  # the same placeholder layout every time

    # The other threads become placeholder rows: a short header bar per group, then items.
    draw.rectangle(SIDEBAR, fill=SIDEBAR_BG)
    y = SIDEBAR[1] + 12
    while y < SIDEBAR[3] - 20:
        draw.rounded_rectangle((78, y, 78 + rng.randint(48, 80), y + 8), radius=4, fill=(38, 38, 38))
        y += 30
        for _ in range(rng.randint(2, 4)):
            if y > SIDEBAR[3] - 20:
                break
            draw.rounded_rectangle((78, y, 78 + rng.randint(110, 220), y + 10), radius=5, fill=(30, 30, 30))
            y += 31
        y += 12

    draw.rectangle(ACCOUNT, fill=SIDEBAR_BG)
    draw.ellipse((72, 1190, 90, 1208), fill=(70, 70, 70))
    draw.rounded_rectangle((98, 1194, 170, 1204), radius=5, fill=(38, 38, 38))

    ui = ImageFont.truetype(FONT, 14)
    draw.rectangle(TAB_TITLE, fill=PANE_BG)
    draw.text((1122, 57), "Whetstone", font=ui, fill=(225, 225, 222))
    draw.rectangle(URL_TEXT, fill=FIELD_BG)
    draw.text((1211, 93), "localhost:8000", font=ui, fill=(205, 205, 200))
    draw.rectangle(PANE, fill=PANE_BG)

    page.save(dest, optimize=True)


if __name__ == "__main__":
    clean(sys.argv[1], sys.argv[2])
