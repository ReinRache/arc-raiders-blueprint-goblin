import csv
from dataclasses import dataclass
from pathlib import Path

from arc_companion.paths import resource_root

BLUEPRINTS_CSV = resource_root() / "data" / "blueprints.csv"
IMAGES_DIR = resource_root() / "data" / "images"

# The in-game collection has three kinds of item (since the Frozen Trail
# update). They share one flat list of stable integer ids -- everything
# downstream (status, friend overlay, cloud arrays, config.json) is keyed on
# the bare id -- and are told apart only by `category`. Each category gets a
# reserved id range so new items never collide: an addition is just a new CSV
# row taking the next free id in its range, never a renumbering.
CATEGORIES: tuple[str, ...] = ("blueprint", "stencil", "design")
CATEGORY_LABELS: dict[str, str] = {"blueprint": "Blueprints", "stencil": "Stencils", "design": "Designs"}
CATEGORY_ID_RANGES: dict[str, tuple[int, int]] = {
    "blueprint": (1, 999),
    "stencil": (1001, 1999),
    "design": (2001, 2999),
}


@dataclass(frozen=True)
class Blueprint:
    """One collectible item. (Named for the original category -- stencils and
    designs are the same shape of thing, so they share the class.)"""

    id: int
    name: str
    # None for a placeholder: a slot that exists in the game but whose item
    # isn't known yet. It still has a real, stable id (so it can be owned,
    # synced and traded); naming it later is an edit to its CSV row.
    image_path: Path | None
    rarity: str | None
    category: str = "blueprint"


def load_blueprints(csv_path: Path = BLUEPRINTS_CSV) -> list[Blueprint]:
    """Reads the item list. Raises ValueError on a malformed file (unknown
    category, id outside its category's range, duplicate id) -- this file is
    hand-edited and crowdsourced, and a silent mistake here would corrupt
    people's saved collections, so it fails loudly at startup instead."""
    blueprints: list[Blueprint] = []
    seen: set[int] = set()
    with open(csv_path, newline="", encoding="utf-8") as f:
        for line_number, row in enumerate(csv.DictReader(f), start=2):
            item_id = int(row["id"])
            # A file from before categories existed has no column: blueprints.
            category = (row.get("category") or "").strip() or "blueprint"
            if category not in CATEGORIES:
                raise ValueError(f"{csv_path.name} line {line_number}: unknown category {category!r}")
            low, high = CATEGORY_ID_RANGES[category]
            if not low <= item_id <= high:
                raise ValueError(
                    f"{csv_path.name} line {line_number}: id {item_id} is outside the "
                    f"{category} range {low}-{high}"
                )
            if item_id in seen:
                raise ValueError(f"{csv_path.name} line {line_number}: duplicate id {item_id}")
            seen.add(item_id)

            rarity = (row.get("rarity") or "").strip() or None
            image = (row.get("image") or "").strip()
            blueprints.append(
                Blueprint(
                    id=item_id,
                    name=row["name"],
                    image_path=IMAGES_DIR / image if image else None,
                    rarity=rarity,
                    category=category,
                )
            )
    return blueprints
