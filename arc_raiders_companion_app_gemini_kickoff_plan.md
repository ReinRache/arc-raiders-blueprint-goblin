# **Project Kickoff Document: *Arc Raiders* Blueprint Companion App**

## **Project Overview**

This project is a lightweight, portable desktop hobby application designed to help *Arc Raiders* players manage, track, and share duplicate crafting blueprints with their Steam friends. Because the game utilizes drop-and-share mechanics, this tool acts as a "wants and haves" directory for teams. To eliminate the risk of automated anti-cheat bans (e.g., from memory hooking), the application operates purely via **manual input, local image processing (OCR/CV), and the Steamworks Web API**.

## **Core Architecture & Technical Stack**

To maximize development speed and keep cloud costs at **$0**, the project will use a lightweight, modular Python architecture:

* **Frontend UI:** `customtkinter` (for a native, modern dark-mode desktop window).  
* **Image Processing:** `opencv-python` \+ `numpy` \+ `pillow` (for parsing screenshots).  
* **Backend & Networking:** `requests` (for the Steamworks Web API and Cloud DB communications).  
* **Cloud Database:** `supabase` or `cloudflare-d1` (Free Tier).  
* **Compilation:** `pyinstaller` (to bundle into a single, standalone portable `.exe`).

---

## **Data Optimization & Security Guardrails**

To ensure GDPR/COPPA compliance and maintain a free database tier, the app must adhere to these data modeling constraints from Day 1:

1. **Bitmask / Encoded Array Rows:** Do not log a row per item per user. Map every game blueprint to a fixed index. A user's collection must be stored in the cloud database as a single flat array per player:  
2. JSON

{ "steam\_id": "7656119xxxxxxxxxx", "blueprints": \[101, 102, 205\], "wants": \[301, 402\], "updated\_at": 1718134560 }

3.   
4.   
5. **Explicit Consent:** A clear opt-in notice must be presented next to the Steam sign-in step.  
6. **Data Deletion:** A dedicated "Wipe Cloud Data / Delete Account" button must exist in the UI settings to satisfy the right to be forgotten.  
7. **Client-Side Caching:** Friend lists and blueprint inventories must be heavily cached in the client application state to prevent API/DB request spam.

---

## **Phases of Development**

### **Phase 1: Local-First (Manual Input & Visual Dev)**

* **Goal:** Build the visual layout and core data structures.  
* **Tasks:**  
  * Initialize a CustomTkinter window with a dark-mode theme.  
  * Create a local master dictionary mapping *Arc Raiders* blueprint IDs to names/rarities.  
  * Build a clean scrollable grid of checkboxes representing the blueprints.  
  * Implement saving and loading the checklist state locally using a basic `config.json` file.

### **Phase 2: Automated Update (Local Computer Vision)**

* **Goal:** Allow users to update their local checklist automatically from an in-game screenshot.  
* **Tasks:**  
  * Build a UI button to import a screenshot (`.png`/`.jpg`) or listen for a screenshot hotkey.  
  * Use OpenCV to isolate the inventory/vault grid container bounds from a standard 1080p image feed.  
  * Implement slice logic to isolate individual item icons.  
  * Use average pixel brightness or HSV color saturation loops to identify if a tile is "unlocked" or "grayed out/locked."

### **Phase 3: Steam Integration & Cloud Database Sync**

* **Goal:** Connect profiles to allow group visibility.  
* **Tasks:**  
  * Implement Steam OpenID web authentication to securely retrieve the user’s unique 64-bit SteamID.  
  * Connect the Python client to the serverless Cloud DB provider.  
  * Use the Steamworks Web API (`ISteamUser/GetFriendList`) to grab the user's friend list.  
  * Query the Cloud DB for matching friend SteamIDs, then compare item arrays to highlight overlap.

### **Phase 4: Optional Support Link**

* **Goal:** Provide an ethical channel for community donations to cover potential scaling.  
* **Tasks:**  
  * Set up a non-intrusive landing page via a platform like Buy Me a Coffee or Ko-fi.  
  * Add a themed button (`☕ Support this project`) in the application footer or settings panel.  
  * Utilize Python's native `webbrowser` module to securely trigger the URL in the user's default browser window.

### **Phase 5: Self-Contained Updates**

* **Goal:** Give users an easy way to stay up to date with new blueprint additions or patch fixes.  
* **Tasks:**  
  * Host a tiny public `version.json` text file on GitHub Pages.  
  * Have the app ping this file on startup to compare local version variables against the server version.  
  * Provide a notification element or a discrete "Update App" button that links out to the latest release bundle if out of date.

### **Phase 6: Needs & Extras Tracking ("Wants and Haves")**

* **Goal:** Introduce specific trade tagging filters.  
* **Tasks:**  
  * Expand the local checklist and cloud DB structure to maintain *two* distinct arrays per user: `blueprints_owned` and `blueprints_wanted`.  
  * Add UI visual tags (e.g., green for "Extra Copy to Share", red for "Actively Looking For").  
  * Implement a comparison filter view: "Show me what my online friends need that I have a spare of."

### **Phase 7: Contextual Map & Ingredient Tooltips**

* **Goal:** Add reference tooltips to help players plan their next extraction deployment.  
* **Tasks:**  
  * Add a hover or right-click tooltip context overlay window to each blueprint item row.  
  * Embed a static lookup array containing crafting ingredients (e.g., Fabric, Rubber, ARC Alloy) and known map drop spots (e.g., Grandioso Apartments, Marano Station, Dam Battlegrounds) to display inside the tooltip UI.

## **Deferred Ideas / Future TODOs**

Not scoped to a phase yet — noted here so they aren't lost, revisit when there's room.

* **Friend nicknames.** Friend-facing UI (the friend-overlay dot tooltips, the friend-selector sidebar list) now prefers a friend's resolved Steam persona name over their bare Goblin ID, but that only helps for friends who've linked Steam. A friend who hasn't (or can't — see the Steam Web API Proxy work, which exists specifically because not everyone can even get a Steam Web API key) still shows as a raw `GBLN-XXXXX` string, which is hard for a player to remember "who is who" for. A local, per-install nickname a player sets for each of their own friends (stored alongside the roster, never synced — this is the viewer's own private label for someone else, not that person's actual identity) would cover that gap without depending on Steam at all.

* **Backup / restore of identity.** User data now lives in `%APPDATA%\ArcRaidersBlueprintGoblin` (survives updates; older next-to-exe installs are copied over once), but deleting that folder, switching Windows accounts, or moving to a new PC still starts a fresh Goblin ID and orphans the old cloud row. A Settings "Back Up / Restore" action (export `config.json` + the recovery secret to a file, import it on the new machine -- the existing `reclaim_profile` flow already supports re-parenting a row given the recovery secret) would close that gap. Not needed for launch; revisit if users ask.
