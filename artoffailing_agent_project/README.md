# Personal MCP Agent — Scaffold

A Python MCP (Model Context Protocol) server that connects GitHub Copilot (or any
MCP-compatible client) to your digital life: Gmail, Calendar, Spotify, iRacing,
news, notes, reminders, a daily briefing, ChromaDB semantic memory, and more.

Run it locally over stdio transport — no open ports, no auth tokens exposed to the
network. VS Code spawns and manages the process automatically.

> This scaffold was published alongside the blog post
> [My AI Sidekick Has a Better Memory Than I Do](https://ropeadope62.github.io/2026/04/05/my-ai-sidekick-has-a-better-memory-than-i-do.html).
> Clone it, wire up the credentials you care about, and build your own tools on top.

---

## Quick Start

### 1. Clone and create a virtual environment

```bash
git clone https://github.com/your-username/personal-mcp-agent
cd personal-mcp-agent
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Copy example configs

```bash
cp .env.example .env
cp config/credentials.json.example     config/credentials.json
cp config/spotify_credentials.json.example  config/spotify_credentials.json
cp config/devices.json.example         config/devices.json   # optional — for network tools
```

Fill in the values for the integrations you want to use (see below).

### 3. Configure VS Code

Edit `.vscode/mcp.json` if needed — the default uses `${workspaceFolder}/.venv/bin/python`,
which works on macOS/Linux. On Windows, change to:

```json
"command": "${workspaceFolder}/.venv/Scripts/python.exe"
```

### 4. Open the folder in VS Code

VS Code reads `.vscode/mcp.json`, starts the server as a subprocess, and Copilot
can call all registered tools. Open Copilot Chat → **Agent** mode → start asking.

---

## Integration Setup

### Google (Gmail + Calendar)

1. Go to [Google Cloud Console](https://console.cloud.google.com/) and create a project.
2. Enable the **Gmail API** and **Google Calendar API**.
3. **Credentials → Create Credentials → OAuth 2.0 Client ID → Desktop app**.
4. Download the JSON and save it as `config/credentials.json`
   (use `config/credentials.json.example` as a reference for the expected shape).
5. Authenticate once:

```bash
python -m tools.google_auth
```

A browser opens for consent. After approving, `config/token.json` is saved automatically
and used for all subsequent calls.

Required scopes (already configured in `google_auth.py`):
- `https://www.googleapis.com/auth/gmail.modify`
- `https://www.googleapis.com/auth/calendar`

### Spotify

1. Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).
2. Create an app. Set the redirect URI to `http://localhost:8888/callback`.
3. Copy the **Client ID** and **Client Secret** into `config/spotify_credentials.json`.
4. In Copilot Chat, ask: `"Authenticate Spotify"` — the agent will open the auth URL
   and handle the callback automatically.

### Jira (optional)

Add to your `.env`:

```
JIRA_BASE_URL=https://your-org.atlassian.net
JIRA_EMAIL=you@example.com
JIRA_API_TOKEN=your_api_token
```

Generate an API token at [id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens).

### Network tools (optional)

Edit `config/devices.json` with your homelab device IPs and MACs. Use
`config/devices.json.example` as a template. If you skip this, the network tools
still work for ad-hoc ping/scan/port checks — they just won't resolve friendly names.

### News RSS (optional)

The news tools use built-in feed lists by default. To override them, set
`NEWS_FEEDS_TECHNOLOGY`, `NEWS_FEEDS_GENERAL`, etc. in `.env` (see `.env.example`).

### Blog tools (optional)

Set `BLOG_REPO_PATH` in `.env` to your local Jekyll repo root. The blog tools will
list drafts, create new posts, and manage front matter.

---

## What's Included

| Module | Tools | Description |
|---|---|---|
| `gmail_tools.py` | 12 | List, read, send, draft, label, batch modify, bulk organize |
| `calendar_tools.py` | 7 | List events, today's schedule, create/delete events, availability |
| `file_tools.py` | 11 | List, search, move, copy, delete, organize by extension |
| `spotify_tools.py` | 28 | Playback control, search, playlists, library, devices, auth |
| `weather_tools.py` | 4 | Current conditions, forecast, daily report |
| `news_tools.py` | 2 | Category listing, curated news report from RSS |
| `notes_tool.py` | 4 | Add/list/delete notes, tag-based export |
| `daily_notes.py` | 6 | Work & personal daily notes, daily/weekly summaries |
| `reminders.py` | 5 | Add/list/dismiss/delete reminders, due check |
| `work_journal.py` | 5 | Daily log, read, search, range view, weekly summary |
| `meeting_notes.py` | 7 | Create 1:1s, meeting notes, add items, search, open action items |
| `jira_tools.py` | 4 | Create tickets, format comments, draft management |
| `focus_timer.py` | 4 | Start/stop named focus sessions, status check, work log |
| `daily_briefing.py` | 2 | Morning briefing aggregating calendar, email, weather, memory |
| `daily_digest.py` | 3 | Generate/read/list end-of-day activity digests |
| `weekly_review.py` | 2 | Weekly retrospective with memory context |
| `context_memory.py` | 3 | ChromaDB semantic memory — index and search past activity |
| `iracing_tools.py` | 3 | Scan/organize/cleanup iRacing setup files |
| `iracing_api.py` | — | iRacing data API client (stats, results) |
| `network_tools.py` | — | Ping, port check, traceroute, homelab device lookup |
| `price_search.py` | 3 | Price search across Canadian retailers |
| `car_rental_tools.py` | 3 | Extract, normalize, and rank rental car listings |
| `codedoc_tools.py` | 5 | Scan codebase, document modules, generate README |
| `blog_tools.py` | — | Jekyll draft/publish management |
| `writing_assistant.py` | — | Style analysis, voice check, outline generation |

---

## Project Structure

```
personal-mcp-agent/
├── server.py                   ← MCP server entry point; all tool registrations
├── tools/
│   ├── google_auth.py          ← Shared OAuth2 helper for Google APIs
│   ├── gmail_tools.py
│   ├── calendar_tools.py
│   ├── context_memory.py       ← ChromaDB semantic memory
│   ├── daily_briefing.py
│   ├── daily_digest.py
│   └── ...                     ← (see table above)
├── config/
│   ├── credentials.json.example    ← Google OAuth client template
│   ├── spotify_credentials.json.example
│   └── devices.json.example        ← Homelab device registry template
├── data/
│   └── chroma/                 ← ChromaDB vector store (auto-created)
├── notes/                      ← Notes, reminders, daily notes, digests
├── logs/                       ← Focus session state
├── .vscode/
│   └── mcp.json                ← Registers the server with VS Code Copilot
├── .env.example
├── .gitignore
└── requirements.txt
```

---

## Architecture Notes

**stdio transport** — The server communicates with VS Code over stdin/stdout.
There are no open ports, no auth tokens on the network, and no background daemons.
VS Code starts the process when you open the workspace and kills it when you close.

**Lazy-loaded Google clients** — The Gmail and Calendar API clients are initialized
on first use, not at import time. This keeps startup fast enough that VS Code's
handshake doesn't time out.

**Tool design principles** (carried over from the hackathon origin):
1. Each tool does one thing. The AI composes them as needed.
2. Docstrings are the tool's documentation — write them clearly.
3. Return structured data (JSON or well-formatted markdown), not prose.

**ChromaDB memory** — The `context_memory` tools use an embedded ChromaDB instance
in `data/chroma/`. Sentence-transformers run locally for embeddings (no API calls,
no token costs). Index activity at end of day with `index_day`; the daily briefing
queries it automatically for relevant context.

---

## Customizing

- **Add a tool**: create a function in the relevant `tools/*.py` module, decorate
  with `@mcp.tool()`, and register it in `server.py`. That's it.
- **Remove tools you don't need**: comment out or delete the `register_*()` calls in
  `server.py`. Unused tool modules are never imported.
- **Copilot instructions**: add a `.github/copilot-instructions.md` (or a custom
  Copilot mode file) to tell the agent how to use your tools together — which ones
  to call for a morning briefing, how to handle email triage, etc. The tools stay
  atomic; the orchestration lives in the instructions.

---

## Security Notes

- `config/credentials.json` and `config/token.json` are git-ignored. Never commit them.
- `FILE_TOOLS_ROOT` in `.env` sets a hard boundary for file operations. The agent
  cannot read or write outside this path.
- The `file_tools.py` module enforces this boundary server-side, not just by convention.
- The server has no `run_command` or arbitrary code execution tool by design.

---

## License

MIT
