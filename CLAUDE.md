# Arc Raiders Blueprint Companion App

## Project Overview
Desktop hobby app (CustomTkinter) that helps *Arc Raiders* players track which crafting blueprints they own, and eventually share "wants/haves" with Steam friends via a cloud DB. Independent project — not part of `python-mech-sim`, separate git repo and venv.

## Key Documents
- **[arc_raiders_companion_app_gemini_kickoff_plan.md](arc_raiders_companion_app_gemini_kickoff_plan.md)** — authoritative phased plan (7 phases). Read this before making scope decisions; it governs feature set and ordering.

## Current Status
- Phase 1 in progress: dark-mode window, blueprint grid, local save/load

## Data
- `data/blueprints.csv` and `data/images/` are the real master blueprint list (83 items, sourced from the Arc Raiders Wiki and an existing HTML prototype the user maintained) — not placeholder data. Treat edits to this file as data-entry changes, not code changes.
- Rarity is sourced per-item from `arcraiders.wiki/wiki/<Item_Name>` infobox pages; some entries may legitimately be `null` where the name didn't resolve to a wiki page — don't backfill these with guesses.

## Persistence
- `src/arc_companion/storage/base.py` defines a `Store` ABC (`load_state`/`save_state`) so the Phase 1 `LocalJSONStore` can be swapped for a Phase 3 cloud-backed store without changing the data model.
- State shape follows the kickoff doc's Day-1 guardrail: `{"steam_id": ..., "blueprints_owned": [...], "blueprints_wanted": [...], "updated_at": ...}`. Use `blueprints_owned`/`blueprints_wanted` (not the doc's shorthand `blueprints`/`wants` names from its intro example — Phase 6 already spells out the real field names).

## Working Conventions
- Run `python -m pytest` from the repo root to verify tests pass.
- Run `python main.py` to launch the app for manual UI verification — GUI code is not unit-tested (CustomTkinter needs a real display).
- Environment: `venv` + `requirements.txt`/`requirements-dev.txt` (no `pyproject.toml`/build backend — kept intentionally simple for a single-dev hobby app).

## Guideline: Surfacing Problems Early
When something unexpected comes up during implementation — a design ambiguity, missing data, a kickoff-doc detail that doesn't cover the case — flag it and suggest a note in the kickoff plan doc rather than silently resolving it in a way that can't be reviewed later.
