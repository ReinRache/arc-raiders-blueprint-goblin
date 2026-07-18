import csv
from dataclasses import dataclass
from pathlib import Path

from arc_companion.paths import resource_root

BLUEPRINTS_CSV = resource_root() / "data" / "blueprints.csv"
IMAGES_DIR = resource_root() / "data" / "images"


@dataclass(frozen=True)
class Blueprint:
    id: int
    name: str
    image_path: Path
    rarity: str | None


def load_blueprints(csv_path: Path = BLUEPRINTS_CSV) -> list[Blueprint]:
    blueprints = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rarity = (row.get("rarity") or "").strip() or None
            blueprints.append(
                Blueprint(
                    id=int(row["id"]),
                    name=row["name"],
                    image_path=IMAGES_DIR / row["image"],
                    rarity=rarity,
                )
            )
    return blueprints
