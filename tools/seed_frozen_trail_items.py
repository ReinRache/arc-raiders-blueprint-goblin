"""One-time seed of the Frozen Trail item data from the designer's hand-listed
ground truth (tests/fixtures/frozen_trail/ground_truth.json: every tile of the
three collection screens, in on-screen order, with its name or 'Unknown').

What it writes (and why it's safe to re-read, never re-run blindly):
  * data/blueprints.csv   -- APPENDS new rows only; existing rows are never touched
      - new named blueprints take the next free ids (84, 85, ...)
      - every stencil/design/unknown-blueprint tile becomes a row too; an
        'Unknown' tile is a PLACEHOLDER (blank image) with a real, stable id
        so it can be owned/synced/traded now and simply renamed later
      - stencil ids = 1000 + tile number; design ids = 2000 + tile number
  * data/layouts/<category>.csv -- the on-screen order (item ids, reading order)

Refuses to run if stencil/design rows already exist: after the first run these
files are hand-edited data (a rename = edit one CSV row; a new in-game item =
one new row + one layout line), not generated output.

Names in the list are typed from the screen, so a few differ from our existing
item names; KNOWN_CORRECTIONS pins those by tile number (confirmed matches).
"""

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRUTH = ROOT / "tests" / "fixtures" / "frozen_trail" / "ground_truth.json"
ITEMS = ROOT / "data" / "blueprints.csv"
LAYOUTS = ROOT / "data" / "layouts"

# blueprint tile number -> existing item id, where the listed name is a typo or
# variant of an existing item. Typo-level differences (Aphellon, Silencer 1)
# resolve by fuzzy name; these two are real judgment calls and are pinned.
KNOWN_CORRECTIONS = {
    28: 27,  # listed "Padded Stock III"; the only unmatched old item is "Stable Stock III"
    44: 42,  # listed "Tactical Mk.3 (Survivor)"; the old item is "Looting Mk. 3 (Survivor)"
}
FUZZY_ALIASES = {"aphellon": "aphelion", "silencer1": "silencer i"}


def norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def main() -> None:
    truth = json.loads(TRUTH.read_text(encoding="utf-8"))
    with open(ITEMS, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if any(r["category"] in ("stencil", "design") for r in rows):
        sys.exit("stencil/design rows already exist -- this seed has been applied; edit the CSVs by hand now.")

    existing = {norm(r["name"]): int(r["id"]) for r in rows}
    for alias, target in FUZZY_ALIASES.items():
        existing[alias] = existing[norm(target)]
    next_blueprint_id = max(int(r["id"]) for r in rows if r["category"] == "blueprint") + 1

    new_rows: list[dict] = []
    layouts: dict[str, list[int]] = {"blueprint": [], "stencil": [], "design": []}

    for tile in truth["blueprint"]["tiles"]:
        n, name = tile["n"], tile["name"]
        if n in KNOWN_CORRECTIONS:
            item_id = KNOWN_CORRECTIONS[n]
        elif name != "Unknown" and norm(name) in existing:
            item_id = existing[norm(name)]
        else:
            item_id, next_blueprint_id = next_blueprint_id, next_blueprint_id + 1
            display = f"Unknown Blueprint #{n}" if name == "Unknown" else name
            new_rows.append(dict(id=item_id, name=display, image="", rarity="", category="blueprint"))
        layouts["blueprint"].append(item_id)

    for category, base in (("stencil", 1000), ("design", 2000)):
        for tile in truth[category]["tiles"]:
            item_id = base + tile["n"]
            label = category.capitalize()
            name = f"Unknown {label} #{tile['n']}" if tile["name"] == "Unknown" else tile["name"]
            new_rows.append(dict(id=item_id, name=name, image="", rarity="", category=category))
            layouts[category].append(item_id)

    with open(ITEMS, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "name", "image", "rarity", "category"], lineterminator="\n")
        writer.writerows(new_rows)
    for category, ids in layouts.items():
        (LAYOUTS / f"{category}.csv").write_text("item_id\n" + "\n".join(map(str, ids)) + "\n", encoding="utf-8")

    named = sum(1 for r in new_rows if not r["name"].startswith("Unknown"))
    print(f"appended {len(new_rows)} rows ({named} named, {len(new_rows) - named} placeholders)")
    print({c: len(v) for c, v in layouts.items()})


if __name__ == "__main__":
    main()
