# Event Editor - AI Influence

A local web tool for authoring **secrets**, **world info**, and **event seeds** for the Mount & Blade II: Bannerlord *AI Influence (AI Diplomacy)* mod, without hand-editing JSON save files.

## About the AI Influence mod
AI Influence gives every lord, companion, and notable in Bannerlord an LLM-driven personality: they hold real conversations, remember what you've told them, gossip and form opinions, and can start conversations with you on their own initiative. Kingdoms conduct AI-generated diplomacy (war/peace, trade deals, tribute, reparations, kingdom statements), and the world periodically generates its own news-style events (political intrigue, wars, economic shifts, social scandals, disease outbreaks) — all written by the AI, woven into ongoing storylines over time.

This tool lets you seed that simulation with your own ideas instead of leaving everything to chance:
- **Secrets** — a hidden fact a specific NPC (or NPC type) might know and could reveal if you build enough trust or catch them off guard.
- **World Info** — general knowledge any qualifying NPC might bring up naturally in conversation.
- **Events** — a story idea you want the world's own AI event generator to weave into a real, AI-written world event.

### Example ideas
- *Secret:* "The court physician has been poisoning the old duke slowly, on the queen's orders." (`applicableNPCs: companions`, high access level)
- *Secret:* "Lord X is secretly the bastard child of the rival kingdom's ruler." (`applicableNPCs: lords`)
- *World Info:* "A famine in the eastern villages has driven up grain prices; merchants are profiteering." (general knowledge, any NPC)
- *World Info:* "Rumors of a sea monster sighted off the northern coast are spreading among sailors and villagers."
- *Event seed:* "Two rival merchant guilds are caught smuggling weapons to bandit camps — a scandal that threatens to topple the city council."
- *Event seed:* "A forbidden romance between a Vlandian lady and an Aserai lord becomes public, scandalizing both courts."
- *Event seed:* "A cult claiming descent from the old Calradian Empire begins recruiting disillusioned nobles."

Mix and match: plant a Secret about an affair, add World Info about the families' rivalry, then seed an Event about the scandal breaking — and let the mod's AI turn it into an evolving storyline.

## Requirements
- Python 3.9+ (stdlib only — no `pip install` needed)
- The AI Influence mod installed and run at least once, so its save data folder exists
- A modern web browser

## Installation
1. Make sure Python is installed and available on your PATH (`python --version` in a terminal).
2. Place `aiinfluence_content_tool.py` anywhere on disk — it doesn't need to live inside the game or mod folder.
3. That's it. There's nothing to build or install; the script is self-contained.

## Configuring your data folder path
The tool needs to know where the AI Influence mod stores its save data (the folder that contains a `save_data` subfolder — typically `...\overwrite\AIInfluence`).

The first time you run the script, it creates a `data_path.txt` file next to it with a placeholder — **this is the only file the tool actually reads**, so just run it once, then open the auto-created `data_path.txt` in any text editor, replace the placeholder line with your real path, save, and restart the tool. No code editing, no renaming anything required.

(`data_path.example.txt` is not read by the script at all — it's only there so the expected format is visible on GitHub without having to run the tool first. Editing it does nothing.)

If `data_path.txt` is missing or still has the placeholder, the tool will print a warning on startup telling you to edit it.

(Advanced/optional) Setting the `AIINFLUENCE_DATA` environment variable overrides `data_path.txt` entirely, e.g.:
```
$env:AIINFLUENCE_DATA = "D:\Games\Bannerlord\overwrite\AIInfluence"
python aiinfluence_content_tool.py
```

## Running the tool
From a terminal, in the folder containing the script:
```
python aiinfluence_content_tool.py
```
This starts a local server (default `http://127.0.0.1:8765`, auto-picking the next free port if that one's busy) and prints the URL to open. Open that URL in your browser.

Stop the server with `Ctrl+C` in the terminal.

### Other configuration (optional environment variable)
- `AIINFLUENCE_PORT` — preferred port (default `8765`)

## Using the tool

### Pick a campaign
The dropdown in the top-right lists all campaigns found under `save_data\`, newest first. Select the one you're currently playing.

### Secrets tab
Author hidden facts NPCs may know about. Fields: unique ID, description, knowledge chance (0-100%), which NPC types can know it, access level, and optional tags. Hot-reloaded by the mod — no restart needed.

### World Info tab
Author general world-knowledge facts NPCs can reference in conversation. Fields: unique ID, description, usage chance (0-100%), applicable NPC types, and a category label. Also hot-reloaded — no restart needed.

### Events tab
Add a **seed idea** (title + description) for something you want to happen in the world — e.g. "Northern Empire faces grain shortage." This does **not** create a finished event directly. Instead it's appended into `prompts/world_data/world.txt` — the actual lore document the mod's dynamic event generator reads on every generation (see below for how this was figured out; an earlier version of this tool wrote seeds into `world_info.json` instead, which turned out to never reach the event generator's prompt at all).

To make it become a real event:
- Open the in-game MCM settings for AI Influence and click **"Force Generate Event Now"** to generate one immediately, or
- Just wait — the mod automatically generates new events on its own schedule (every `DynamicEventsInterval` days, default 7).

There's still no guarantee — see below for why — but unlike the old approach, the seed is now actually visible to the generator.

### Editing and deleting
Every entry in the "Existing" list has **Edit** and **Delete** buttons. Edits and deletes write a `.bak` backup of the file before saving, so you can always recover the previous version by renaming the `.bak` file back.

## How dynamic event generation actually works (and how to make seeds matter)
This was reverse-engineered by decompiling `AIInfluence.dll` (it has unusual/obfuscated metadata — standard tools like ILSpy fail with "Illegal tables in compressed metadata stream"; `dnlib`-based tooling reads it fine even though local identifiers are renamed to invisible Unicode characters; public API names and string literals survive), then **confirmed by reading the literal prompt text the mod logs to `logs/dynamicEvents.log` on every generation** — the log records the exact prompt sent to the LLM, which is the most reliable source of truth here.

Findings:
- `world_info.json` (and `world_secrets.json`) entries are **only** used for per-NPC conversation knowledge — each NPC has a chance (`usageChance`/`knowledgeChance`, `applicableNPCs`) of "knowing" a fact and bringing it up if you talk to them. They are **never included in the Dynamic Events Generator's prompt at all.** An earlier version of this tool (and an earlier version of this doc) assumed seeds written there would feed event generation — confirmed wrong by inspecting the actual logged prompt, which contained no trace of `world_info.json` content.
- The `{world_info}` placeholder in `DynamicEventsGeneratorStaticRules.txt` (*"You operate in the world of `{world_info}`..."*) is substituted from a **different file**: `prompts/world_data/world.txt`, a free-form lore document (kingdoms, geography, daily life, custom additions). This is the only per-campaign text that actually reaches the event generator's prompt as "world info."
- There is no code-level probability filter anywhere in this pipeline — any "chance" field is just text the LLM sees, never a dice roll the C# code performs.
- The actual instruction for *what topic* to write about is a separate, hardcoded task file. In **World State mode** (`DynamicEventsGeneratorWorldStateDataTask.txt`), default text: *"Create EXACTLY 1 event based on current kingdom relations, wars, or political tension."* In **Dialogue mode** (`DynamicEventsGeneratorDialogueDataTask.txt`), events come only from recent NPC conversations. Neither mode is told to use `world.txt` content as its topic by default — it's framed purely as scene-setting/atmosphere.

**The fix this tool applies:** the Events tab appends seed ideas directly into `world.txt` (under a clearly delimited `=== USER EVENT SEEDS ===` block it manages — your own hand-written lore above that block is left untouched), and tags the most recently added one `[MOST RECENT — use this one]` so prompt instructions have something concrete to point at. Three per-campaign prompt files under `prompts/dynamic_events_generator/` were edited to push compliance as high as possible:
- `DynamicEventsGeneratorWorldStateDataTask.txt` — *"You MUST base this event on the LAST entry listed in the USER EVENT SEEDS section above... Only if that section is completely absent should you fall back to kingdom relations/wars/political tension."*
- `DynamicEventsGeneratorMandatoryRules.txt` — added as the **first** mandatory rule (most prominent position): *"...the event you generate MUST be about its entry marked 'MOST RECENT'. This overrides every other topic consideration."*
- `DynamicEventsGeneratorFinalInstructionWorldState.txt` — the literal last line before generation (highest-recency LLM attention): *"...your event MUST be based on its 'MOST RECENT' entry — this is non-negotiable."*

**This is still not a hard guarantee** — it's the strongest instruction wording achievable while staying inside the AI-driven generator, but compliance ultimately depends on the LLM actually following it, not code. A true guarantee would require bypassing the AI and writing a complete event straight into `aiinfluence_campaign_diplomacy.json` yourself (skips the AI's narrative elaboration, requires a game restart since that file isn't hot-reloaded). After clicking "Force Generate Event Now", check `logs/dynamicEvents.log` (search `PROMPT SENT TO AI:`) to see exactly what the model was shown and whether the generated event actually matches your seed.

Keep the original UTF-8 BOM + CRLF encoding when hand-editing prompt `.txt` files (Notepad does this automatically; PowerShell's `Set-Content` does not by default — use `[System.IO.File]::WriteAllText($path, $content, (New-Object System.Text.UTF8Encoding $true))`).

**Note:** if you used an earlier version of this tool, any seed you added before this fix is sitting in `world_info.json` tagged `category: "event_seed"` — it's harmless there (it now just behaves as a normal World Info fact NPCs may know and mention in conversation) but won't influence event generation. Re-add it via the Events tab if you want it to actually reach the generator.

## Notes
- All changes are written directly to the campaign's save files. Close any other tool that might also be writing to the same files at the same time.
- The tool works fully offline — no external services, no API keys, no internet connection required.
