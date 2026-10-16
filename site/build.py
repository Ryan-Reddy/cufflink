"""Builds cufflink.reddy.world into _site/.

    python site/build.py

The sitemap is written last, by the template's scripts/sitemap.mjs (so Node is
needed too), from the pages in _site/ and sitemap.routes.json.

The site is plain HTML in site/. What is generated here is what would drift if
it were kept by hand: the privacy page comes from PRIVACY.md, the same file the
Store listing points at, and the pictures come from assets/, the same files the
app and the listing use.

Needs Pillow and Markdown (CI installs both), and Node for the sitemap.
"""

import re
import shutil
import subprocess
from pathlib import Path

import markdown
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
OUT = ROOT / "_site"
SCREENSHOTS = ROOT / "assets" / "store" / "screenshots"
BG = (13, 27, 51)
# (left, top, right, bottom) of the window in each Store screenshot.
CROPS = {
    "01-reading": (196, 322, 1170, 686),
    "02-voices": (776, 36, 1270, 720),
}          # --bg in styles.css, and the plate behind the hero


def copy_site():
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(SITE, OUT, ignore=shutil.ignore_patterns("build.py", "__pycache__"))


def privacy():
    md = (ROOT / "PRIVACY.md").read_text(encoding="utf-8")
    # On the website "this file" is a page, so say which file is meant.
    md = md.replace("will appear in this file,",
                    "will appear in [PRIVACY.md](https://github.com/Ryan-Reddy/cufflink/blob/main/PRIVACY.md),")
    # Bare addresses become links; the contact lines keep their line break.
    md = re.sub(r"(?<![(<\[])(https://[^\s)]+)", r"<\1>", md)
    md = md.replace("https://reddy.world>\n", "https://reddy.world>  \n")
    html = markdown.markdown(md, extensions=["sane_lists"])
    html = html.replace("<h1>Privacy Policy</h1>", "<h1>Privacy policy</h1>")
    page = OUT / "privacy" / "index.html"
    text = page.read_text(encoding="utf-8")
    marker = "<!-- PRIVACY.md, rendered by site/build.py -->"
    assert marker in text, "privacy template lost its marker"
    page.write_text(text.replace(marker, html), encoding="utf-8")


def pictures():
    img = OUT / "img"
    img.mkdir(exist_ok=True)
    # The Store screenshots are 1366x768 with the app small in the middle, which
    # is right for a listing and too small on a page. The page shows the window
    # itself, cut from the same file.
    for name, box in CROPS.items():
        im = Image.open(SCREENSHOTS / f"{name}.png").convert("RGB").crop(box)
        im.save(img / f"{name}.png", optimize=True)
        im.save(img / f"{name}.webp", quality=88, method=6)

    # Social card: the reading screenshot, cropped to 1200x630 around the pill.
    im = Image.open(SCREENSHOTS / "01-reading.png").convert("RGB")
    w, h = im.size
    scale = 1200 / w
    im = im.resize((1200, round(h * scale)), Image.LANCZOS)
    top = (im.height - 630) // 2
    im.crop((0, top, 1200, top + 630)).save(OUT / "og-image.png", optimize=True)

    icons = OUT / "icons"
    icons.mkdir(exist_ok=True)
    hero = Image.open(ROOT / "assets" / "cufflink-hero.png").convert("RGB")
    for size in (192, 512):
        hero.resize((size, size), Image.LANCZOS).save(icons / f"icon-{size}.png", optimize=True)
    hero.resize((180, 180), Image.LANCZOS).save(icons / "apple-touch-icon.png", optimize=True)
    # Maskable: the plate already sits inside a margin, so pad a little more
    # to keep the hand inside the safe circle.
    pad = Image.new("RGB", (int(hero.width * 1.15), int(hero.height * 1.15)), BG)
    pad.paste(hero, ((pad.width - hero.width) // 2, (pad.height - hero.height) // 2))
    pad.resize((512, 512), Image.LANCZOS).save(icons / "icon-maskable-512.png", optimize=True)

    mark = Image.open(ROOT / "assets" / "cufflink-mark.png").convert("RGBA")
    mark.resize((64, 64), Image.LANCZOS).save(icons / "mark-64.png", optimize=True)
    mark.save(OUT / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])


if __name__ == "__main__":
    copy_site()
    privacy()
    pictures()
    subprocess.run(["node", "scripts/sitemap.mjs", "--dist", "_site",
                    "--base", "https://cufflink.reddy.world",
                    "--routes", "sitemap.routes.json"], cwd=ROOT, check=True)
    print(f"built {OUT}")
