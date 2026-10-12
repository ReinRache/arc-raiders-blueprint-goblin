# Arc Raiders Blueprint Goblin

A free desktop app for tracking your *Arc Raiders* collection — **Blueprints,
Stencils and Designs** — what you own, what you want, what you have spares of, and
comparing with your friends to spot helpful trades.

> Unofficial fan tool. Not affiliated with nor endorsed by Embark Studios.

## Download (Windows)

1. Go to the [**Releases** page](../../releases/latest) and download
   `ArcRaidersBlueprintGoblin-<version>.zip`.
2. **Extract the whole zip** to a folder (right-click → *Extract All*). Don't run
   the `.exe` from inside the zip, and don't copy the `.exe` out on its own — it
   needs the `_internal` folder next to it.
3. Run `ArcRaidersBlueprintGoblin.exe`.

**Windows may warn "Windows protected your PC"** the first time. The app isn't
code-signed (certificates cost money for a free hobby project), so SmartScreen
doesn't recognize it. Click **More info → Run anyway**. The full source is in this
repository if you'd like to inspect or build it yourself.

Your progress and Goblin ID are saved in `%APPDATA%\ArcRaidersBlueprintGoblin`
(paste that into Explorer's address bar), **not** next to the `.exe`. To update,
just extract the new version anywhere and run it — everything carries over. When a
newer version is released, an **Update available** button appears in the sidebar.

## Using it

- **Click an item's icon or its status button** to cycle it:
  Unowned → Owned → Want → Have (a spare).
- **Tabs and filters:** switch between **All / Blueprints / Stencils / Designs**
  above the grid (the header shows your progress for the view you're in), search by
  name, and use **Show:** to narrow to *Trade opportunities*, *I want*, *I have spare*,
  *I own* or *Missing*.
- **Friends:** share your *Goblin ID* (Goblin ID Friends) and add your friends' IDs.
  Sync to see, on every tile, which friends own, want, or have spares.
- **Trade Highlights** tiles get a green or cyan border when there's a good trade,
  hovering the icon tells you with whom.
- **Steam ID Friends** (optional): link Steam to show Steam names instead of Goblin IDs and to find
  which of your Steam friends already use the app.

### Importing from screenshots

Use **Scan Collection Screenshots** to import what you've found automatically. Each
Collections tab is a single screen, so it's **one screenshot per tab**:

1. In-game, open **Collections** and switch to the tab you want to import
   (Blueprints, Stencils or Designs).
2. Take a **full-window screenshot of the Arc Raiders window** — not a cropped
   capture — and save it as a **PNG**.
3. In the app, open the scan dialog and pick the file for that tab. Repeat for the
   other tabs if you like; you only need the ones you want to update.

The scanner checks which tab the screenshot shows and tells you if you've picked
the wrong one. It relies on the whole game window being in the image (it measures
positions proportionally), so crops and other formats won't work. It only ever
adds what it finds on the tabs you scanned — other tabs are never touched.

### Missing or "Unknown" items

The game keeps adding items, and not every one has been identified yet — tiles we
haven't named show as **Unknown Design #37** (the number is its position in-game).
They're fully usable: you can mark them owned and trade them, and when the real
name is added nothing you've recorded changes. If you know what one is (or an item
is missing or misnamed), use **Options → Report a Missing Item**, or see
[CONTRIBUTING.md](CONTRIBUTING.md) — adding an item is a two-line edit to a text file.

## Privacy

If you sync, a row is stored in a cloud database (Supabase) containing your Goblin
ID, your collection lists (blueprints, stencils, designs), and — only if you choose to link it — your public Steam
ID. Friends can look rows up by Goblin ID. **Options → Delete My Data** clears your
synced blueprint data. The app never sees your Steam password (Steam login happens
in your browser via Steam's own OpenID page).

## Known limitations

- Windows only for now.
- Text can look slightly soft on high-DPI displays, and the window doesn't re-scale
  if you drag it to a monitor with different scaling (restart the app after
  moving). This is deliberate: live re-scaling was freezing the app on multi-monitor
  setups.

## Building from source

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
python main.py                 # run
python -m pytest               # test
python -m PyInstaller arc_companion.spec --noconfirm   # build dist/
```

## Support

Free and always will be. If you and your friends find it useful, you can
[buy me a coffee](https://buymeacoffee.com/alwaysbegoblin).

## License and credits

The app's code is [MIT](LICENSE).

ARC Raiders and EMBARK are trademarks of Embark Studios AB. Item names and icons are
game content, © Embark Studios AB, used here by an unofficial fan tool; many were
compiled from the community-run [ARC Raiders Wiki](https://arcraiders.wiki), whose
community-written content is available under CC BY-SA.
