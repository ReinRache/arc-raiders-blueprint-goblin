# Contributing

The most useful contribution is **item data**: the game adds blueprints, stencils and designs
faster than one person can track. The app is built so that adding or fixing an item is a small
edit to two text files — no code, no database changes, nobody's saved collection is disturbed.

## How the data fits together

| File | What it is |
| --- | --- |
| `data/blueprints.csv` | Every item: `id,name,image,rarity,category`. |
| `data/layouts/<category>.csv` | The items of one tab in the order the game shows them (`blueprint`, `stencil`, `design`). |
| `data/images/` | Item icons (PNG, ~256px). |

**Ids are permanent.** Saved collections, friends' data and the cloud are all keyed on an item's id,
so an id is never reused or renumbered. Each category has its own range so additions never collide:
blueprints `1–999`, stencils `1001–1999`, designs `2001–2999`.

**Position is separate from identity.** *Where* an item sits on the in-game screen lives only in the
layout file. If the game slips a new item into the middle of a tab, that's a new item row plus one
new line in the layout — every existing id keeps meaning the same item.

## Recipes

**Name an "Unknown" tile** (e.g. `Unknown Design #37` → what it really is)
1. Find its row in `data/blueprints.csv` (search `Unknown Design #37`).
2. Change only the `name` — keep the `id`. Optionally add an `image` and `rarity`.
3. That's it. The tile keeps its id, so anyone who already marked it owned keeps that.

**Add a brand-new item the game just released**
1. In `data/blueprints.csv` add a row with the **next free id in that category's range**
   (e.g. the highest design id + 1).
2. In `data/layouts/<category>.csv` add the new id **on the line matching its in-game position**
   (insert it; later lines simply shift down).
3. If it's a placeholder (name not known yet), call it `Unknown <Category> #<tile number>` and
   leave `image` blank.

**Add or fix an icon**
- Put a square PNG (256px is plenty) in `data/images/` and put its filename in the item's `image`
  column. `python tools/import_wiki_icons.py` can fetch many from the ARC Raiders Wiki for you
  (it does a dry run first so you can review every match).

## Checking your change

```
python -m pytest
```

The tests catch the mistakes that matter: a duplicate or out-of-range id, an item missing from its
layout (a scan could never credit it), a layout line pointing at an unknown id, or a missing icon file.

To see exactly which cell the scanner reads for each position, `tools/debug_grid_overlay.py` draws the
cell numbers and found/empty state on a screenshot.

## Reporting instead of editing

Not comfortable with Git? Use **Options → Report a Missing Item** in the app (or open the issue form
on GitHub). Tell us the tab and the tile number (counting left-to-right, top-to-bottom from 1) and,
if you can, the item's exact in-game name.
