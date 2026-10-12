"""Fetches icons for items that have a name but no image yet, from the ARC
Raiders Wiki (arcraiders.wiki, a community wiki supported by Embark Studios).

    python tools/import_wiki_icons.py            # dry run: report matches, write nothing
    python tools/import_wiki_icons.py --apply    # download icons + fill the CSV `image` column

How it finds them: it reads the wiki's own tables (Stencils, Furniture) for
name -> file pairs, then matches by normalized name. Anything that isn't an
exact name match (a plural, a trailing " Design", a typo like "Terraccota")
is reported as a FUZZY match for you to eyeball -- the dry run is the review
step, and nothing is written without --apply. Items with no match are listed
so they can be filled in by hand (or crowdsourced). Placeholder items
("Unknown ...") and items that already have an image are never touched.

Etiquette: a descriptive User-Agent, a short delay between downloads, and it's
meant to be run once per game update, not on a schedule.

Licensing: the wiki states all game content and materials are copyright of
Embark Studios AB, with community-written content under CC BY-SA. The icons
are game assets; the README carries the attribution/unofficial-tool notice.
"""

import argparse
import csv
import difflib
import io
import re
import sys
import time
from pathlib import Path

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ITEMS = ROOT / "data" / "blueprints.csv"
IMAGES = ROOT / "data" / "images"
WIKI = "https://arcraiders.wiki"
API = f"{WIKI}/w/api.php"
HEADERS = {"User-Agent": "ARBG-icon-import/0.1 (hobby fan tool; github.com/ReinRache/arc-raiders-blueprint-goblin)"}
ICON_SIZE = 256  # the wiki serves 512px; the app shows ~86px, so 256 keeps files small and crisp
FUZZY_CUTOFF = 0.86


def norm(name: str) -> str:
    """Lowercase alphanumerics only; also drops a trailing 'design' since the
    wiki titles some furniture 'Study Piano Design' where the game says 'Study Piano'."""
    text = re.sub(r"[^a-z0-9]", "", name.lower())
    return text[: -len("design")] if text.endswith("design") and len(text) > len("design") else text


def _strip_tags(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def parse_table_rows(html: str) -> list[tuple[str, str]]:
    """(item name, full-size file path) for every table row that has an image.
    The name is the first non-empty, non-numeric text cell (Stencils rows start
    with a '1', '2', ... index cell; Furniture rows start with the image)."""
    pairs = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, flags=re.S):
        files = re.findall(r'href="(/w/images/[0-9a-f]/[0-9a-f]{2}/[^"]+\.(?:png|webp|jpg))"', row)
        if not files:
            continue
        cells = [_strip_tags(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row, flags=re.S)]
        name = next((c for c in cells if c and not c.isdigit()), "")
        if name:
            pairs.append((name, files[0]))
    return pairs


def match_icon(name: str, available: dict[str, tuple[str, str]]) -> tuple[str, str, str] | None:
    """-> (matched wiki name, file path, 'exact' | 'fuzzy') or None."""
    key = norm(name)
    if key in available:
        wiki_name, path = available[key]
        return wiki_name, path, "exact"
    close = difflib.get_close_matches(key, list(available), n=1, cutoff=FUZZY_CUTOFF)
    if close:
        wiki_name, path = available[close[0]]
        return wiki_name, path, "fuzzy"
    return None


def _wiki_pairs(page: str) -> list[tuple[str, str]]:
    response = requests.get(
        API,
        params={"action": "parse", "page": page, "prop": "text", "format": "json", "formatversion": 2},
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    return parse_table_rows(response.json()["parse"]["text"])


def _file_lookup(name: str) -> tuple[str, str] | None:
    """Fallback for items not in a table (e.g. a new blueprint): ask the wiki
    whether a file named after the item exists."""
    base = name.replace(" ", "_")
    for title in (f"File:{base}.png", f"File:Icon_{base}.png"):
        response = requests.get(
            API,
            params={"action": "query", "format": "json", "formatversion": 2, "prop": "imageinfo", "iiprop": "url", "titles": title},
            headers=HEADERS,
            timeout=30,
        )
        pages = response.json().get("query", {}).get("pages", [])
        info = pages[0].get("imageinfo") if pages else None
        if info:
            return title, info[0]["url"].replace(WIKI, "")
    return None


def _slug(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="download icons and update blueprints.csv")
    args = parser.parse_args()

    with open(ITEMS, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    todo = [r for r in rows if not r["image"].strip() and not r["name"].startswith("Unknown ")]
    print(f"{len(todo)} named items have no icon yet")

    available: dict[str, tuple[str, str]] = {}
    for page in ("Stencils", "Furniture"):
        for name, path in _wiki_pairs(page):
            available.setdefault(norm(name), (name, path))
    print(f"wiki tables list {len(available)} icons")

    plan: list[tuple[dict, str, str, str]] = []  # (row, wiki name, path, kind)
    missing: list[dict] = []
    for row in todo:
        hit = match_icon(row["name"], available) if row["category"] != "blueprint" else None
        if hit is None:
            fallback = _file_lookup(row["name"])
            hit = (fallback[0], fallback[1], "file-lookup") if fallback else None
        if hit is None:
            missing.append(row)
        else:
            plan.append((row, *hit))

    for row, wiki_name, path, kind in plan:
        flag = "" if kind == "exact" else f"   <-- {kind.upper()}: check this one"
        print(f"  [{row['category']:9s}] {row['name']!r:34s} -> {wiki_name!r} {path.rsplit('/', 1)[-1]}{flag}")
    print(f"\nNO MATCH ({len(missing)}): {[r['name'] for r in missing]}")

    if not args.apply:
        print("\n(dry run -- re-run with --apply to download and update the CSV)")
        return

    IMAGES.mkdir(parents=True, exist_ok=True)
    by_id = {r["id"]: r for r in rows}
    for row, _wiki_name, path, _kind in plan:
        prefix = "" if row["category"] == "blueprint" else f"{row['category'].capitalize()}_"
        filename = f"{prefix}{_slug(row['name'])}.png"
        data = requests.get(WIKI + path, headers=HEADERS, timeout=60)
        data.raise_for_status()
        image = Image.open(io.BytesIO(data.content)).convert("RGBA")
        if max(image.size) > ICON_SIZE:
            image.thumbnail((ICON_SIZE, ICON_SIZE), Image.LANCZOS)
        image.save(IMAGES / filename, optimize=True)
        by_id[row["id"]]["image"] = filename
        time.sleep(0.4)

    with open(ITEMS, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "name", "image", "rarity", "category"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"downloaded {len(plan)} icons into {IMAGES}")


if __name__ == "__main__":
    sys.exit(main())
