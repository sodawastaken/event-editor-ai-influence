# Event Editor - AI Influence

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

Set usage chance and applicable NPC types the same way as the World Info tab. **Important caveat** (found by decompiling the mod, see below): the chance value is *not* a guarantee or even a code-enforced probability — it's just text the AI sees. By default the AI is told to pick its event topic from current kingdom wars/political tension (or from recent dialogue), not from your seeds, so a 100%-chance seed can still be ignored. See "Making seeds actually influence event topics" below to fix that.

### Editing and deleting
Every entry in the "Existing" list has **Edit** and **Delete** buttons. Edits and deletes write a `.bak` backup of the file before saving, so you can always recover the previous version by renaming the `.bak` file back.

## How dynamic event generation actually works (and how to make seeds matter)
This was reverse-engineered by decompiling `AIInfluence.dll` (it has unusual/obfuscated metadata — standard tools like ILSpy fail with "Illegal tables in compressed metadata stream"; `dnlib`-based tooling reads it fine even though local identifiers are renamed to invisible Unicode characters; public API names and string literals survive).

Findings:
- `WorldInfoManager.ReadWorldInfo()` reads `world_info.json` **verbatim** and substitutes it into the prompt via a `{world_info}` placeholder. There is **no code-level probability filter** — every entry's `usageChance` is just text the LLM sees, not a dice roll the C# code performs.
- That placeholder is only used for "what does this world feel like" scene-setting (`DynamicEventsGeneratorStaticRules.txt`: *"You operate in the world of `{world_info}`. Create events that fit this world's setting and atmosphere."*) — not as a topic source.
- The actual topic instruction comes from a separate, hardcoded task file. In **World State mode** (`DynamicEventsGeneratorWorldStateDataTask.txt`), the default text is: *"Create EXACTLY 1 event based on current kingdom relations, wars, or political tension."* In **Dialogue mode** (`DynamicEventsGeneratorDialogueDataTask.txt`), events come only from recent NPC conversations. Neither mode is told to look at your World Info seeds for its topic — so even a 100%-chance seed can be (and usually is) ignored if there's any active war/political tension to write about instead.

**The fix:** these prompt files are plain text, live per-campaign under `prompts/dynamic_events_generator/` and `prompts/rules/`, and are hot-reloaded like the JSON data files. Edit `DynamicEventsGeneratorWorldStateDataTask.txt` to explicitly tell the generator to prioritize World Info seeds, e.g.:
```
TASK: Create EXACTLY 1 event. Prioritize any specific seed ideas described in the WORLD INFO section above if present; otherwise base it on current kingdom relations, wars, or political tension.
Choose the most interesting aspect of the current world state.
```
This file needs editing **per campaign** (`save_data\<campaign_id>\prompts\dynamic_events_generator\DynamicEventsGeneratorWorldStateDataTask.txt`) since each campaign gets its own copy of the default templates. Keep the original UTF-8 BOM + CRLF encoding when hand-editing (Notepad and most editors do this automatically; PowerShell's `Set-Content` does not by default — use `[System.IO.File]::WriteAllText($path, $content, (New-Object System.Text.UTF8Encoding $true))` if scripting it).

## Notes
- All changes are written directly to the campaign's save files. Close any other tool that might also be writing to the same files at the same time.
- The tool works fully offline — no external services, no API keys, no internet connection required.
