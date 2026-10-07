# Arc Raiders Blueprint Goblin

A free desktop app for tracking your *Arc Raiders* blueprint collection — what you
own, what you want, what you have spares of — and comparing with your friends to
spot helpful trades.

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

- **Click a blueprint's icon or its status button** to cycle it:
  Unowned → Owned → Want → Have (a spare).
- **Search** by name above the grid.
- **Friends:** share your *Goblin ID* (Manage Friends) and add your friends' IDs.
  Sync to see, on every tile, which friends own, want, or have spares.
- **Trade Highlights** tiles get a green or cyan border when there's a good trade,
  hovering the icon tells you with whom.
- **Link Steam** (optional) to show Steam names instead of Goblin IDs and to find
  which of your Steam friends already use the app.

### Importing from screenshots

Use **Scan Collection Screenshots** to import your blueprints automatically:

1. In-game, open the Blueprints panel and scroll to the very **top**. Take a
   **full-window screenshot of the Arc Raiders window** — not a cropped capture.
2. Scroll to the very **bottom** and take a second one the same way.
3. Both must be **PNG** files. Select them in the two steps of the dialog.

The scanner relies on the whole game window being in the image (it measures
positions proportionally), so crops and other formats won't work.

## Privacy

If you sync, a row is stored in a cloud database (Supabase) containing your Goblin
ID, your blueprint lists, and — only if you choose to link it — your public Steam
ID. Friends can look rows up by Goblin ID. **Settings → Delete My Data** clears your
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

## License

[MIT](LICENSE)
