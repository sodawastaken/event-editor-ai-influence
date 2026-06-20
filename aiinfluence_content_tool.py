#!/usr/bin/env python3
"""AI Influence Content Tool - Local web editor for secrets, world info, and events."""

import http.server
import json
import os
import shutil
import socket
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, parse_qs

DATA_PATH_CONFIG_FILE = Path(__file__).resolve().parent / "data_path.txt"
DATA_PATH_PLACEHOLDER = r"C:\Users\<username>\AppData\Local\ModOrganizer\Mount & Blade II Bannerlord\overwrite\AIInfluence"
DATA_PATH_TEMPLATE = (
    "# Paste the full path to your AIInfluence data folder below this line, then save this file\n"
    "# and restart the tool. This is the folder that contains the 'save_data' subfolder.\n"
    "# Example: C:\\Users\\YourName\\AppData\\Local\\ModOrganizer\\Mount & Blade II Bannerlord\\overwrite\\AIInfluence\n"
    f"{DATA_PATH_PLACEHOLDER}\n"
)


def load_data_path():
    """Reads the data folder path from data_path.txt (created with a placeholder on first run if missing),
    so non-technical users can configure this by editing a plain text file instead of the script."""
    env_value = os.environ.get("AIINFLUENCE_DATA")
    if env_value:
        return env_value
    if not DATA_PATH_CONFIG_FILE.exists():
        DATA_PATH_CONFIG_FILE.write_text(DATA_PATH_TEMPLATE, encoding="utf-8")
    for line in DATA_PATH_CONFIG_FILE.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line
    return DATA_PATH_PLACEHOLDER


DATA_BASE = load_data_path()
PORT = int(os.environ.get("AIINFLUENCE_PORT", "8765"))
HOST = "127.0.0.1"

NPC_TYPES = ["all", "lords", "companions", "faction_leaders"]
ACCESS_LEVELS = ["low", "medium", "high"]
SEEDS_BLOCK_START = "=== USER EVENT SEEDS (managed by AI Influence Content Tool — edits here will be overwritten) ==="
SEEDS_BLOCK_END = "=== END USER EVENT SEEDS ==="


def find_free_port(start=8765):
    for port in range(start, start + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex((HOST, port)) != 0:
                return port
    return start


def read_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def read_text(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return f.read()


def write_text(path, content):
    with open(path, "w", encoding="utf-8-sig", newline="\r\n") as f:
        f.write(content)


def backup_file(path):
    bak = str(path) + ".bak"
    if os.path.exists(path):
        shutil.copy2(path, bak)


def get_campaigns():
    save_dir = Path(DATA_BASE) / "save_data"
    if not save_dir.exists():
        return []
    campaigns = []
    for entry in save_dir.iterdir():
        if entry.is_dir() and entry.name != "default":
            mtime = entry.stat().st_mtime
            campaigns.append({
                "id": entry.name,
                "last_modified": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S"),
            })
    campaigns.sort(key=lambda c: c["last_modified"], reverse=True)
    return campaigns


def get_secrets_path(campaign_id):
    return Path(DATA_BASE) / "save_data" / campaign_id / "prompts" / "world_data" / "world_secrets.json"


def get_info_path(campaign_id):
    return Path(DATA_BASE) / "save_data" / campaign_id / "prompts" / "world_data" / "world_info.json"


def get_event_seeds_path(campaign_id):
    return Path(DATA_BASE) / "save_data" / campaign_id / "prompts" / "world_data" / "event_seeds.json"


def get_world_lore_path(campaign_id):
    return Path(DATA_BASE) / "save_data" / campaign_id / "prompts" / "world_data" / "world.txt"


def validate_secret(entry, existing, skip_id=None):
    errors = []
    if not entry.get("id", "").strip():
        errors.append("id is required")
    elif any(e["id"] == entry["id"] for e in existing if e["id"] != skip_id):
        errors.append(f"id '{entry['id']}' already exists")
    if not entry.get("description", "").strip():
        errors.append("description is required")
    kc = entry.get("knowledgeChance")
    if not isinstance(kc, int) or kc < 0 or kc > 100:
        errors.append("knowledgeChance must be an integer 0-100")
    npcs = entry.get("applicableNPCs", [])
    if not isinstance(npcs, list) or len(npcs) == 0:
        errors.append("applicableNPCs must be a non-empty array")
    else:
        for npc in npcs:
            if npc not in NPC_TYPES:
                errors.append(f"invalid applicableNPCs value: {npc}")
    if entry.get("accessLevel", "") not in ACCESS_LEVELS:
        errors.append("accessLevel must be one of: low, medium, high")
    return errors


def validate_info(entry, existing, skip_id=None):
    errors = []
    if not entry.get("id", "").strip():
        errors.append("id is required")
    elif any(e["id"] == entry["id"] for e in existing if e["id"] != skip_id):
        errors.append(f"id '{entry['id']}' already exists")
    if not entry.get("description", "").strip():
        errors.append("description is required")
    uc = entry.get("usageChance")
    if not isinstance(uc, int) or uc < 0 or uc > 100:
        errors.append("usageChance must be an integer 0-100")
    npcs = entry.get("applicableNPCs", [])
    if not isinstance(npcs, list) or len(npcs) == 0:
        errors.append("applicableNPCs must be a non-empty array")
    else:
        for npc in npcs:
            if npc not in NPC_TYPES:
                errors.append(f"invalid applicableNPCs value: {npc}")
    if not entry.get("category", "").strip():
        errors.append("category is required")
    return errors


def validate_event_seed(entry):
    errors = []
    if not entry.get("title", "").strip() and not entry.get("description", "").strip():
        errors.append("title or description is required")
    return errors


def sync_seeds_to_world_txt(campaign_id, seeds):
    """Rewrite the seeds block in world.txt — the file actually read into the dynamic event generator's
    prompt (NOT world_info.json, which only feeds per-NPC conversation knowledge)."""
    path = get_world_lore_path(campaign_id)
    try:
        text = read_text(path) if path.exists() else ""
    except Exception:
        text = ""

    start_idx = text.find(SEEDS_BLOCK_START)
    if start_idx != -1:
        text = text[:start_idx].rstrip("\r\n ")
    else:
        text = text.rstrip("\r\n ")

    if seeds:
        lines = [SEEDS_BLOCK_START]
        for i, s in enumerate(seeds):
            title = s.get("title", "").strip()
            description = s.get("description", "").strip()
            line = f"{title}: {description}" if title and description else (title or description)
            marker = "  [MOST RECENT — use this one]" if i == len(seeds) - 1 else ""
            lines.append(f"- {line}{marker}")
        lines.append(SEEDS_BLOCK_END)
        block = "\n".join(lines)
        text = (text + "\n\n" + block + "\n") if text else (block + "\n")

    backup_file(path)
    write_text(path, text)


class RequestHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}")

    def send_json(self, data, status=200):
        body = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, html):
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "" or path == "/":
            self.send_html(HTML_PAGE)
            return

        parts = [p for p in path.split("/") if p]
        if len(parts) == 2 and parts[0] == "api" and parts[1] == "campaigns":
            self.send_json(get_campaigns())
            return

        if len(parts) == 3 and parts[0] == "api":
            campaign_id = parts[1]
            content_type = parts[2]
            if content_type not in ("secrets", "info", "events"):
                self.send_json({"error": "invalid content type"}, 400)
                return
            try:
                if content_type == "secrets":
                    data = read_json(get_secrets_path(campaign_id))
                elif content_type == "info":
                    data = read_json(get_info_path(campaign_id))
                elif content_type == "events":
                    filepath = get_event_seeds_path(campaign_id)
                    data = read_json(filepath) if filepath.exists() else []
                self.send_json(data)
            except FileNotFoundError:
                self.send_json({"error": "campaign or file not found"}, 404)
            except Exception as e:
                self.send_json({"error": str(e)}, 500)
            return

        self.send_json({"error": "not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        parts = [p for p in path.split("/") if p]

        if not (len(parts) == 3 and parts[0] == "api"):
            self.send_json({"error": "not found"}, 404)
            return

        campaign_id = parts[1]
        content_type = parts[2]
        if content_type not in ("secrets", "info", "events"):
            self.send_json({"error": "invalid content type"}, 400)
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            entry = json.loads(body)
        except Exception as e:
            self.send_json({"error": f"invalid JSON: {e}"}, 400)
            return

        try:
            if content_type == "secrets":
                filepath = get_secrets_path(campaign_id)
                existing = read_json(filepath) if filepath.exists() else []
                errors = validate_secret(entry, existing)
                if errors:
                    self.send_json({"errors": errors}, 400)
                    return
                backup_file(filepath)
                existing.append(entry)
                write_json(filepath, existing)
                self.send_json({"ok": True, "entry": entry})

            elif content_type == "info":
                filepath = get_info_path(campaign_id)
                existing = read_json(filepath) if filepath.exists() else []
                errors = validate_info(entry, existing)
                if errors:
                    self.send_json({"errors": errors}, 400)
                    return
                backup_file(filepath)
                existing.append(entry)
                write_json(filepath, existing)
                self.send_json({"ok": True, "entry": entry})

            elif content_type == "events":
                filepath = get_event_seeds_path(campaign_id)
                existing = read_json(filepath) if filepath.exists() else []
                errors = validate_event_seed(entry)
                if errors:
                    self.send_json({"errors": errors}, 400)
                    return
                seed_entry = {
                    "id": str(uuid.uuid4()),
                    "title": entry.get("title", "").strip(),
                    "description": entry.get("description", "").strip(),
                }
                backup_file(filepath)
                existing.append(seed_entry)
                write_json(filepath, existing)
                sync_seeds_to_world_txt(campaign_id, existing)
                self.send_json({"ok": True, "entry": seed_entry})

        except FileNotFoundError:
            self.send_json({"error": f"campaign '{campaign_id}' not found"}, 404)
        except Exception as e:
            self.send_json({"error": str(e)}, 500)


    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        parts = [p for p in path.split("/") if p]

        if not (len(parts) == 4 and parts[0] == "api"):
            self.send_json({"error": "not found"}, 404)
            return

        campaign_id = parts[1]
        content_type = parts[2]
        entry_id = parts[3]

        if content_type not in ("secrets", "info", "events"):
            self.send_json({"error": "invalid content type"}, 400)
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            entry = json.loads(body)
        except Exception as e:
            self.send_json({"error": f"invalid JSON: {e}"}, 400)
            return

        try:
            if content_type == "secrets":
                filepath = get_secrets_path(campaign_id)
                existing = read_json(filepath)
                idx = next((i for i, e in enumerate(existing) if e["id"] == entry_id), None)
                if idx is None:
                    self.send_json({"error": f"entry '{entry_id}' not found"}, 404)
                    return
                errors = validate_secret(entry, existing, skip_id=entry_id)
                if errors:
                    self.send_json({"errors": errors}, 400)
                    return
                backup_file(filepath)
                existing[idx] = entry
                write_json(filepath, existing)
                self.send_json({"ok": True, "entry": entry})

            elif content_type == "info":
                filepath = get_info_path(campaign_id)
                existing = read_json(filepath)
                idx = next((i for i, e in enumerate(existing) if e["id"] == entry_id), None)
                if idx is None:
                    self.send_json({"error": f"entry '{entry_id}' not found"}, 404)
                    return
                errors = validate_info(entry, existing, skip_id=entry_id)
                if errors:
                    self.send_json({"errors": errors}, 400)
                    return
                backup_file(filepath)
                existing[idx] = entry
                write_json(filepath, existing)
                self.send_json({"ok": True, "entry": entry})

            elif content_type == "events":
                filepath = get_event_seeds_path(campaign_id)
                existing = read_json(filepath)
                idx = next((i for i, e in enumerate(existing) if e["id"] == entry_id), None)
                if idx is None:
                    self.send_json({"error": f"entry '{entry_id}' not found"}, 404)
                    return
                errors = validate_event_seed(entry)
                if errors:
                    self.send_json({"errors": errors}, 400)
                    return
                seed_entry = {
                    "id": entry_id,
                    "title": entry.get("title", "").strip(),
                    "description": entry.get("description", "").strip(),
                }
                backup_file(filepath)
                existing[idx] = seed_entry
                write_json(filepath, existing)
                sync_seeds_to_world_txt(campaign_id, existing)
                self.send_json({"ok": True, "entry": seed_entry})

        except FileNotFoundError:
            self.send_json({"error": f"campaign '{campaign_id}' not found"}, 404)
        except Exception as e:
            self.send_json({"error": str(e)}, 500)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        parts = [p for p in path.split("/") if p]

        if not (len(parts) == 4 and parts[0] == "api"):
            self.send_json({"error": "not found"}, 404)
            return

        campaign_id = parts[1]
        content_type = parts[2]
        entry_id = parts[3]

        if content_type not in ("secrets", "info", "events"):
            self.send_json({"error": "invalid content type"}, 400)
            return

        try:
            if content_type == "secrets":
                filepath = get_secrets_path(campaign_id)
                existing = read_json(filepath)
                idx = next((i for i, e in enumerate(existing) if e["id"] == entry_id), None)
                if idx is None:
                    self.send_json({"error": f"entry '{entry_id}' not found"}, 404)
                    return
                backup_file(filepath)
                del existing[idx]
                write_json(filepath, existing)
                self.send_json({"ok": True})

            elif content_type == "info":
                filepath = get_info_path(campaign_id)
                existing = read_json(filepath)
                idx = next((i for i, e in enumerate(existing) if e["id"] == entry_id), None)
                if idx is None:
                    self.send_json({"error": f"entry '{entry_id}' not found"}, 404)
                    return
                backup_file(filepath)
                del existing[idx]
                write_json(filepath, existing)
                self.send_json({"ok": True})

            elif content_type == "events":
                filepath = get_event_seeds_path(campaign_id)
                existing = read_json(filepath)
                idx = next((i for i, e in enumerate(existing) if e["id"] == entry_id), None)
                if idx is None:
                    self.send_json({"error": f"entry '{entry_id}' not found"}, 404)
                    return
                backup_file(filepath)
                del existing[idx]
                write_json(filepath, existing)
                sync_seeds_to_world_txt(campaign_id, existing)
                self.send_json({"ok": True})

        except FileNotFoundError:
            self.send_json({"error": f"campaign '{campaign_id}' not found"}, 404)
        except Exception as e:
            self.send_json({"error": str(e)}, 500)


HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI Influence Content Tool</title>
<style>
:root {
  --bg: #1a1a2e;
  --surface: #16213e;
  --surface2: #0f3460;
  --text: #e0e0e0;
  --muted: #8892b0;
  --accent: #e94560;
  --accent2: #533483;
  --green: #2ecc71;
  --red: #e74c3c;
  --border: #2a2a4a;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  background: var(--bg); color: var(--text);
  min-height: 100vh;
}
header {
  background: var(--surface);
  border-bottom: 2px solid var(--accent);
  padding: 12px 24px;
  display: flex; align-items: center; gap: 16px;
}
header h1 { font-size: 1.2em; color: var(--accent); }
.campaign-selector {
  display: flex; align-items: center; gap: 8px; margin-left: auto;
}
.campaign-selector select {
  background: var(--bg); color: var(--text);
  border: 1px solid var(--border); padding: 6px 12px;
  border-radius: 4px; font-size: 0.9em; min-width: 200px;
}
.campaign-selector label { color: var(--muted); font-size: 0.85em; }

nav.tabs {
  display: flex; gap: 0; background: var(--surface);
  border-bottom: 1px solid var(--border); padding: 0 24px;
}
nav.tabs button {
  background: none; border: none; color: var(--muted);
  padding: 12px 20px; cursor: pointer; font-size: 0.95em;
  border-bottom: 3px solid transparent; transition: all 0.2s;
}
nav.tabs button:hover { color: var(--text); }
nav.tabs button.active { color: var(--accent); border-bottom-color: var(--accent); }

main {
  max-width: 1400px; margin: 0 auto; padding: 24px; display: flex; gap: 24px;
}
.panel { flex: 1; }
.panel h2 {
  font-size: 1em; color: var(--muted); text-transform: uppercase;
  letter-spacing: 1px; margin-bottom: 16px;
}
.card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 8px; padding: 20px;
}
.form-group { margin-bottom: 14px; }
.form-group label {
  display: block; color: var(--muted); font-size: 0.8em;
  margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.5px;
}
.form-group input, .form-group select, .form-group textarea {
  width: 100%; background: var(--bg); color: var(--text);
  border: 1px solid var(--border); padding: 8px 12px;
  border-radius: 4px; font-size: 0.9em; font-family: inherit;
}
.form-group textarea { resize: vertical; min-height: 80px; }
.form-group input:focus, .form-group select:focus, .form-group textarea:focus {
  outline: none; border-color: var(--accent);
}
.checkbox-group { display: flex; flex-wrap: wrap; gap: 8px; }
.checkbox-group label {
  display: flex; align-items: center; gap: 4px;
  color: var(--text); text-transform: none; font-size: 0.85em;
  padding: 4px 10px; background: var(--bg); border-radius: 4px;
  border: 1px solid var(--border); cursor: pointer;
}
.checkbox-group label:has(input:checked) {
  border-color: var(--accent); background: var(--surface2);
}
.checkbox-group input { width: auto; margin: 0; }
.btn {
  background: var(--accent); color: #fff; border: none;
  padding: 10px 24px; border-radius: 4px; cursor: pointer;
  font-size: 0.9em; font-weight: 600;
}
.btn:hover { opacity: 0.9; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.feedback { margin-top: 10px; padding: 8px 12px; border-radius: 4px; font-size: 0.85em; }
.feedback.success { background: #1a3a2a; color: var(--green); border: 1px solid var(--green); }
.feedback.error { background: #3a1a1a; color: var(--red); border: 1px solid var(--red); }

.entry-card {
  background: var(--surface2); border: 1px solid var(--border);
  border-radius: 6px; padding: 12px; margin-bottom: 10px;
}
.entry-card .entry-id { color: var(--accent); font-weight: 600; margin-bottom: 4px; }
.entry-card .entry-desc { color: var(--text); font-size: 0.9em; margin-bottom: 6px; }
.entry-card .entry-meta { color: var(--muted); font-size: 0.78em; display: flex; gap: 12px; flex-wrap: wrap; }
.entry-card .entry-meta span { background: var(--bg); padding: 1px 8px; border-radius: 3px; }
.toggle-row { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; }
.toggle-row label { margin-bottom: 0; color: var(--text); }
.toggle-row select { width: auto; flex: 1; }
.empty-state { color: var(--muted); font-style: italic; padding: 20px; text-align: center; }
.entry-actions { margin-top: 8px; display: flex; gap: 8px; }
.btn-sm {
  background: var(--surface); color: var(--text); border: 1px solid var(--border);
  padding: 4px 12px; border-radius: 4px; cursor: pointer; font-size: 0.78em;
}
.btn-sm:hover { border-color: var(--accent); }
.btn-sm.danger { color: var(--red); border-color: var(--red); }
.btn-sm.danger:hover { background: var(--red); color: #fff; }
.btn-cancel {
  background: var(--surface); color: var(--muted); border: 1px solid var(--border);
  padding: 10px 24px; border-radius: 4px; cursor: pointer; font-size: 0.9em;
  margin-left: 8px;
}
.btn-cancel:hover { border-color: var(--accent); color: var(--text); }
#campaign-info { font-size: 0.8em; color: var(--muted); margin-top: 4px; }
</style>
</head>
<body>
<header>
  <h1>AI Influence Content Tool</h1>
  <div class="campaign-selector">
    <label for="campaign">Campaign:</label>
    <select id="campaign"><option value="">-- loading --</option></select>
    <span id="campaign-info"></span>
  </div>
</header>

<nav class="tabs">
  <button data-tab="secrets" class="active">Secrets</button>
  <button data-tab="info">World Info</button>
  <button data-tab="events">Events</button>
</nav>

<main>
  <div class="panel" id="form-panel">
    <h2>Add New</h2>
    <div class="card" id="form-container"></div>
  </div>
  <div class="panel" id="entries-panel">
    <h2>Existing</h2>
    <div id="entries-container"></div>
  </div>
</main>

<script>
const state = { tab: 'secrets', campaign: '', editingId: null };

document.getElementById('campaign').addEventListener('change', function() {
  state.campaign = this.value;
  clearForms();
  loadEntries();
});

document.querySelectorAll('nav.tabs button').forEach(btn => {
  btn.addEventListener('click', function() {
    state.tab = this.dataset.tab;
    document.querySelectorAll('nav.tabs button').forEach(b => b.classList.remove('active'));
    this.classList.add('active');
    clearForms();
    loadEntries();
  });
});

async function loadCampaigns() {
  try {
    const res = await fetch('/api/campaigns');
    const campaigns = await res.json();
    const sel = document.getElementById('campaign');
    sel.innerHTML = '<option value="">-- select campaign --</option>';
    campaigns.forEach(c => {
      sel.innerHTML += `<option value="${c.id}">${c.id} (${c.last_modified})</option>`;
    });
    if (campaigns.length > 0) {
      sel.value = campaigns[0].id;
      state.campaign = campaigns[0].id;
      loadEntries();
    }
  } catch(e) { console.error(e); }
}

function getApiPath() {
  return '/api/' + state.campaign + '/' + state.tab;
}

async function loadEntries() {
  if (!state.campaign) return;
  const container = document.getElementById('entries-container');
  container.innerHTML = '<div class="empty-state">Loading...</div>';
  try {
    const res = await fetch(getApiPath());
    const data = await res.json();
    if (res.ok) {
      let entries = data;
      state._entries = entries;
      if (entries.length === 0) {
        container.innerHTML = '<div class="empty-state">No entries yet.</div>';
      } else {
        container.innerHTML = entries.map(function(e, i) { return renderEntry(e, i); }).join('');
      }
    } else {
      container.innerHTML = '<div class="empty-state">Error loading: ' + (data.error || 'unknown') + '</div>';
    }
  } catch(e) {
    container.innerHTML = '<div class="empty-state">Failed to load.</div>';
  }
  renderForm();
}

function renderEntry(e, i) {
  var actions = '<div class="entry-actions">'
    + '<button class="btn-sm" onclick="startEdit(\'' + he(e.id) + '\')">Edit</button>'
    + '<button class="btn-sm danger" onclick="deleteEntry(\'' + he(e.id) + '\')">Delete</button>'
    + '</div>';

  if (state.tab === 'secrets') {
    return '<div class="entry-card">'
      + '<div class="entry-id">' + he(e.id) + '</div>'
      + '<div class="entry-desc">' + he(e.description) + '</div>'
      + '<div class="entry-meta">'
      + '<span>Chance: ' + e.knowledgeChance + '%</span>'
      + '<span>Access: ' + he(e.accessLevel) + '</span>'
      + '<span>NPCs: ' + (e.applicableNPCs||[]).join(', ') + '</span>'
      + '<span>Tags: ' + ((e.tags||[]).join(', ') || 'none') + '</span>'
      + '</div>' + actions + '</div>';
  } else if (state.tab === 'info') {
    return '<div class="entry-card">'
      + '<div class="entry-id">' + he(e.id) + '</div>'
      + '<div class="entry-desc">' + he(e.description) + '</div>'
      + '<div class="entry-meta">'
      + '<span>Chance: ' + e.usageChance + '%</span>'
      + '<span>Category: ' + he(e.category) + '</span>'
      + '<span>NPCs: ' + (e.applicableNPCs||[]).join(', ') + '</span>'
      + '</div>' + actions + '</div>';
  } else {
    var uuidShort = (e.id || '').substring(0, 8);
    return '<div class="entry-card">'
      + '<div class="entry-id"><span title="' + he(e.id) + '">' + uuidShort + '...</span></div>'
      + '<div class="entry-desc"><strong>' + he(e.title) + '</strong>' + (e.title && e.description ? ': ' : '') + he(e.description) + '</div>'
      + actions + '</div>';
  }
}

function he(str) {
  var s = String(str);
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

async function submitForm(e) {
  e.preventDefault();
  const form = document.getElementById('entry-form');
  const feedback = document.getElementById('form-feedback');
  feedback.className = 'feedback';
  feedback.textContent = '';

  var data = collectFormData();
  var errors = clientValidate(data);
  if (errors.length > 0) {
    feedback.className = 'feedback error';
    feedback.textContent = errors.join('; ');
    return;
  }

  var method = state.editingId ? 'PUT' : 'POST';
  var url = getApiPath();
  if (state.editingId) {
    url += '/' + encodeURIComponent(state.editingId);
  }

  try {
    var res = await fetch(url, {
      method: method,
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(data)
    });
    var result = await res.json();
    if (res.ok) {
      feedback.className = 'feedback success';
      var msg = state.editingId ? 'Updated successfully!' : 'Added successfully!';
      if (state.tab === 'events' && !state.editingId) {
        msg += ' Added to world.txt, which the event generator reads. Open MCM in-game and click "Force Generate Event Now" to try turning it into a real event immediately, or wait for the next automatic generation cycle.';
      }
      feedback.textContent = msg;
      state.editingId = null;
      form.reset();
      loadEntries();
    } else {
      feedback.className = 'feedback error';
      feedback.textContent = (result.errors || [result.error]).join('; ');
    }
  } catch(err) {
    feedback.className = 'feedback error';
    feedback.textContent = 'Network error: ' + err.message;
  }
}

function clientValidate(data) {
  var errs = [];
  if (state.tab !== 'events' && (!data.id || !data.id.trim())) errs.push('id is required');
  if (state.tab === 'events') {
    if (!data.title.trim() && !data.description.trim()) errs.push('title or description required');
  } else if (!data.description || !data.description.trim()) {
    errs.push('description required');
  }
  if (state.tab === 'secrets' && (data.knowledgeChance < 0 || data.knowledgeChance > 100)) errs.push('knowledgeChance 0-100');
  if (state.tab === 'info' && (data.usageChance < 0 || data.usageChance > 100)) errs.push('usageChance 0-100');
  return errs;
}

function collectFormData() {
  if (state.tab === 'secrets') return collectSecretData();
  if (state.tab === 'info') return collectInfoData();
  return collectEventData();
}

function collectSecretData() {
  const f = document.getElementById('entry-form');
  return {
    id: f.querySelector('[name="id"]').value.trim(),
    description: f.querySelector('[name="description"]').value.trim(),
    knowledgeChance: parseInt(f.querySelector('[name="knowledgeChance"]').value),
    applicableNPCs: getCheckedNPCs(f),
    accessLevel: f.querySelector('[name="accessLevel"]').value,
    tags: f.querySelector('[name="tags"]').value.split(',').map(s=>s.trim()).filter(Boolean),
  };
}

function collectInfoData() {
  const f = document.getElementById('entry-form');
  return {
    id: f.querySelector('[name="id"]').value.trim(),
    description: f.querySelector('[name="description"]').value.trim(),
    usageChance: parseInt(f.querySelector('[name="usageChance"]').value),
    applicableNPCs: getCheckedNPCs(f),
    category: f.querySelector('[name="category"]').value.trim(),
  };
}

function collectEventData() {
  var f = document.getElementById('entry-form');
  return {
    title: f.querySelector('[name="title"]').value.trim(),
    description: f.querySelector('[name="description"]').value.trim(),
  };
}

function getCheckedNPCs(form) {
  return [...form.querySelectorAll('input[name="npcs"]:checked')].map(cb => cb.value);
}

function clearForms() {
  document.getElementById('form-container').innerHTML = '';
  document.getElementById('entries-container').innerHTML = '<div class="empty-state">Select a campaign...</div>';
  state.editingId = null;
}

function buildNPCGroup(selected) {
  var npcs = ['all','lords','companions','faction_leaders'];
  if (!selected) selected = ['all'];
  var selSet = {};
  for (var i = 0; i < selected.length; i++) selSet[selected[i]] = true;
  var html = '<div class="form-group"><label>Applicable NPCs</label><div class="checkbox-group">';
  for (var i = 0; i < npcs.length; i++) {
    var n = npcs[i];
    html += '<label><input type="checkbox" name="npcs" value="' + n + '"' + (selSet[n] ? ' checked' : '') + '> ' + n.replace(/_/g, ' ') + '</label>';
  }
  html += '</div></div>';
  return html;
}

function renderForm() {
  if (!state.campaign) return;
  var container = document.getElementById('form-container');
  var editData = null;

  if (state.editingId && state._entries) {
    for (var i = 0; i < state._entries.length; i++) {
      if (state._entries[i].id === state.editingId) { editData = state._entries[i]; break; }
    }
  }

  var isEdit = !!editData;
  var idDisabled = isEdit ? ' disabled' : '';
  var idVal = isEdit ? (' value="' + he(editData.id) + '"') : '';
  var idReadonly = isEdit ? ' (read-only)' : '';
  var submitLabel = isEdit ? 'Update Entry' : 'Add Entry';
  var cancelHtml = isEdit ? ' <button type="button" class="btn-cancel" onclick="cancelEdit()">Cancel</button>' : '';

  var html = '<form id="entry-form" onsubmit="submitForm(event)">';
  if (state.tab !== 'events') {
    html += '<div class="form-group"><label>ID' + idReadonly + '</label><input name="id" required placeholder="unique-id"' + idDisabled + idVal + '></div>';
  } else if (isEdit) {
    var shortId = editData.id ? editData.id.substring(0, 12) + '...' : '';
    html += '<div class="form-group"><label>Seed ID</label><input disabled value="' + shortId + '" style="font-family:monospace;font-size:0.8em;"></div>';
  }

  if (state.tab === 'secrets') {
    var desc = editData ? he(editData.description) : '';
    var kc = editData ? editData.knowledgeChance : 50;
    var acc = editData ? editData.accessLevel : 'medium';
    var tags = editData ? (editData.tags||[]).join(', ') : '';
    html += '<div class="form-group"><label>Description</label><textarea name="description" required>' + desc + '</textarea></div>';
    html += '<div class="form-group"><label>Knowledge Chance (0-100)</label><input name="knowledgeChance" type="number" value="' + kc + '" min="0" max="100"></div>';
    html += buildNPCGroup(editData ? editData.applicableNPCs : null);
    html += '<div class="form-group"><label>Access Level</label><select name="accessLevel">'
      + '<option value="low"' + (acc==='low'?' selected':'') + '>Low</option>'
      + '<option value="medium"' + (acc==='medium'?' selected':'') + '>Medium</option>'
      + '<option value="high"' + (acc==='high'?' selected':'') + '>High</option>'
      + '</select></div>';
    html += '<div class="form-group"><label>Tags (comma-separated)</label><input name="tags" value="' + tags + '" placeholder="templar_hunt, secret_order"></div>';

  } else if (state.tab === 'info') {
    var desc = editData ? he(editData.description) : '';
    var uc = editData ? editData.usageChance : 10;
    var cat = editData ? he(editData.category) : '';
    html += '<div class="form-group"><label>Description</label><textarea name="description" required>' + desc + '</textarea></div>';
    html += '<div class="form-group"><label>Usage Chance (0-100)</label><input name="usageChance" type="number" value="' + uc + '" min="0" max="100"></div>';
    html += buildNPCGroup(editData ? editData.applicableNPCs : null);
    html += '<div class="form-group"><label>Category</label><input name="category" required value="' + cat + '" placeholder="world"></div>';

  } else if (state.tab === 'events') {
    var title = editData ? he(editData.title) : '';
    var desc = editData ? he(editData.description) : '';
    html += '<div class="form-group"><label>Title</label><input name="title" value="' + title + '" placeholder="e.g. Northern Empire faces grain shortage"></div>';
    html += '<div class="form-group"><label>Description</label><textarea name="description">' + desc + '</textarea></div>';
  }

  html += '<button type="submit" class="btn">' + submitLabel + '</button>' + cancelHtml;
  html += '<div id="form-feedback" class="feedback"></div>';
  html += '</form>';

  container.innerHTML = html;

  var formPanel = document.getElementById('form-panel').querySelector('h2');
  if (formPanel) formPanel.textContent = isEdit ? 'Edit Entry' : 'Add New';
}

function startEdit(id) {
  state.editingId = id;
  renderForm();
  document.getElementById('form-panel').scrollIntoView({behavior: 'smooth'});
}

function cancelEdit() {
  state.editingId = null;
  renderForm();
}

async function deleteEntry(id) {
  if (!confirm('Delete "' + id + '"? This cannot be undone.')) return;
  var url = getApiPath() + '/' + encodeURIComponent(id);
  try {
    var res = await fetch(url, { method: 'DELETE' });
    var result = await res.json();
    if (res.ok) {
      if (state.editingId === id) { state.editingId = null; }
      loadEntries();
    } else {
      alert('Delete failed: ' + (result.error || 'unknown'));
    }
  } catch(err) {
    alert('Network error: ' + err.message);
  }
}

clearForms();
loadCampaigns();
</script>
</body>
</html>"""


def main():
    actual_port = find_free_port(PORT)
    server = http.server.HTTPServer((HOST, actual_port), RequestHandler)
    url = f"http://{HOST}:{actual_port}"
    print(f"AI Influence Content Tool running at {url}")
    print(f"Data directory: {DATA_BASE}")
    if DATA_BASE == DATA_PATH_PLACEHOLDER:
        print(f"  ^ This is a placeholder! Edit {DATA_PATH_CONFIG_FILE} with your real AIInfluence data folder path.")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
