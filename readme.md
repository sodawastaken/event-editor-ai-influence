# Event Editor - AI Diplomacy

A local web tool for authoring **secrets**, **world info**, and **event seeds** for the Mount & Blade II: Bannerlord *AI Influence (AI Diplomacy)* mod, without hand-editing JSON save files.

## Requirements
- Python 3.9+ (stdlib only — no `pip install` needed)
- The AI Influence mod installed and run at least once, so its save data folder exists
- A modern web browser

## Installation
1. Make sure Python is installed and available on your PATH (`python --version` in a terminal).
2. Place `aiinfluence_content_tool.py` anywhere on disk — it doesn't need to live inside the game or mod folder.
3. That's it. There's nothing to build or install; the script is self-contained.

## Running the tool
From a terminal, in the folder containing the script:
```
python aiinfluence_content_tool.py
```
This starts a local server (default `http://127.0.0.1:8765`, auto-picking the next free port if that one's busy) and prints the URL to open. Open that URL in your browser.

Stop the server with `Ctrl+C` in the terminal.

### Configuration (optional environment variables)
- `AIINFLUENCE_DATA` — path to the mod's data folder, if it's not at the default location:
  `C:\Users\<you>\AppData\Local\ModOrganizer\Mount & Blade II Bannerlord\overwrite\AIInfluence`
- `AIINFLUENCE_PORT` — preferred port (default `8765`)

Example (PowerShell):
```
$env:AIINFLUENCE_DATA = "D:\Games\Bannerlord\overwrite\AIInfluence"
python aiinfluence_content_tool.py
```

## Using the tool

### Pick a campaign
The dropdown in the top-right lists all campaigns found under `save_data\`, newest first. Select the one you're currently playing.

### Secrets tab
Author hidden facts NPCs may know about. Fields: unique ID, description, knowledge chance (0-100%), which NPC types can know it, access level, and optional tags. Hot-reloaded by the mod — no restart needed.

### World Info tab
Author general world-knowledge facts NPCs can reference in conversation. Fields: unique ID, description, usage chance (0-100%), applicable NPC types, and a category label. Also hot-reloaded — no restart needed.

### Events tab
Add a **seed idea** (title + description) for something you want to happen in the world — e.g. "Northern Empire faces grain shortage." This does **not** create a finished event directly. Instead it's written into the mod's world-info data so the mod's own AI can pick it up.

To make it become a real event:
- Open the in-game MCM settings for AI Influence and click **"Force Generate Event Now"** to generate one immediately, or
- Just wait — the mod automatically generates new events on its own schedule (every `DynamicEventsInterval` days, default 7), and your seed will be available as context for that generation.

Set usage chance and applicable NPC types the same way as the World Info tab — this controls how likely/relevant the seed is when the mod's AI considers what to write about.

### Editing and deleting
Every entry in the "Existing" list has **Edit** and **Delete** buttons. Edits and deletes write a `.bak` backup of the file before saving, so you can always recover the previous version by renaming the `.bak` file back.

## Notes
- All changes are written directly to the campaign's save files. Close any other tool that might also be writing to the same files at the same time.
- The tool works fully offline — no external services, no API keys, no internet connection required.
