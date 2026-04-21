# WebPilot — Product Specification

---

## Overview

**WebPilot** is an AI-powered browser automation app. You type a plain English instruction and a real browser opens, navigates, clicks, scrolls, fills forms, and returns what it found — all autonomously. No code, no selectors, no scripting.

---

## What It Does

| You type | What actually happens |
|----------|----------------------|
| "Go to bbc.com and summarise the top 3 stories" | Browser opens BBC, reads headlines and article intros, returns a summary |
| "Search Google for the latest Python version and tell me what's new" | Browser searches Google, opens the Python release page, extracts release notes |
| "Go to github.com/trending and list the top 5 repos today" | Browser opens GitHub trending, reads repo names, stars, and descriptions |
| "Navigate to news.ycombinator.com and find the top story" | Browser opens Hacker News, extracts the #1 story title and link |
| "Go to weather.com and tell me tomorrow's weather for New York" | Browser navigates to weather.com, searches New York, reads the forecast |

---

## How It Works

```
You type a plain English instruction
              │
              ▼
     GPT-4o-mini reads it
              │
              ▼
   Decides what browser actions to take
   (navigate / click / scroll / type / screenshot / extract)
              │
              ▼
   Playwright MCP server executes
   the actions on a real browser
              │
              ▼
   Result returned to Streamlit UI
   as formatted markdown
```

### Why This Is Genuinely Agentic

Unlike a simple chatbot, WebPilot uses **MCP (Model Context Protocol)** — a standard that lets LLMs call real tools. The LLM doesn't generate text about what it would do; it actually calls browser functions and gets real results back. The agent decides:
- Which URL to navigate to
- What to click
- What to type into forms
- When to scroll
- When to take a screenshot
- How to extract the information you asked for

---

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **UI** | Streamlit | Web interface for input and results |
| **Agent Framework** | `mcp-agent` | Connects LLM to MCP tool servers |
| **LLM** | OpenAI `gpt-4o-mini` | Interprets instructions, decides browser actions |
| **Browser Control** | Playwright (`@playwright/mcp`) | Executes actual browser actions |
| **MCP Server** | `npx @playwright/mcp@latest` | Runs the Playwright MCP server (requires Node.js) |
| **Async** | `asyncio` | Handles async agent execution inside Streamlit |

---

## APIs and Prerequisites Required

| Requirement | Purpose | How to Get |
|-------------|---------|-----------|
| `OPENAI_API_KEY` | Powers GPT-4o-mini | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| **Node.js + npm** | Runs the Playwright MCP server via `npx` | [nodejs.org](https://nodejs.org) — install LTS version |
| **Playwright browsers** | Downloads Chromium for browser control | Run `playwright install` after `pip install` |

> **Cost:** Uses `gpt-4o-mini` — the cheapest OpenAI model (~$0.15 per 1M input tokens). A typical browsing task uses ~1,000–3,000 tokens.

---

## Project Structure

```
WebPilot/
├── main.py                         # Streamlit app — all UI and agent logic
├── mcp_agent.config.yaml           # MCP agent config — model, logging, Playwright server
├── mcp_agent.secrets.yaml          # Your API key (gitignored — never committed)
├── mcp_agent.secrets.yaml.example  # Template for the secrets file
├── requirements.txt                # Python dependencies
└── PRODUCT_SPEC.md                 # This file
```

Only **4 runtime files** — this is a lean, focused project.

---

## Streamlit UI

### Sidebar
- **Example commands** — pre-written instructions users can copy and try:
  - Navigation: "Go to www.mcp-agent.com and tell me what it does"
  - Interaction: "Go to GitHub trending and list top 5 repos"
  - Multi-step: "Search Google for OpenAI news, open the first result, summarise it"
- **Setup checklist** — confirms Node.js and Playwright are installed
- **Model info** — shows which OpenAI model is being used

### Main Area
- **Instruction input** — large text area for entering natural language commands
- **Run button** — executes the agent with a loading spinner
- **Results panel** — renders the agent's response as formatted markdown
- **Session history** — previous commands and results in the same session

---

## Configuration Files

### `mcp_agent.config.yaml`
```yaml
execution_engine: asyncio
logger:
  transports: [console, file]
  level: debug
  progress_display: true
  path_settings:
    path_pattern: "logs/mcp-agent-{unique_id}.jsonl"
    unique_id: "timestamp"
    timestamp_format: "%Y%m%d_%H%M%S"

mcp:
  servers:
    playwright:
      command: "npx"
      args: ["@playwright/mcp@latest"]

openai:
  default_model: "gpt-4o-mini"
```

### `mcp_agent.secrets.yaml`
```yaml
openai:
  api_key: YOUR_OPENAI_API_KEY
```

---

## How to Run

### 1. Install Python dependencies
```bash
cd GenAI/WebPilot
pip install -r requirements.txt
```

### 2. Install Playwright browsers
```bash
playwright install
```

### 3. Ensure Node.js is installed
```bash
node --version   # should print v18+ or higher
npm --version
```

### 4. Set up your API key
```bash
cp mcp_agent.secrets.yaml.example mcp_agent.secrets.yaml
```
Edit `mcp_agent.secrets.yaml` and add your OpenAI API key.

### 5. Run the app
```bash
streamlit run main.py
```

Opens at `http://localhost:8501`.

---

## Error Handling

| Error | Behaviour |
|-------|-----------|
| OpenAI API key missing | Clear error message shown in UI before any execution |
| Node.js not installed | Agent init fails with descriptive message pointing to nodejs.org |
| Playwright browsers not installed | Error caught with instruction to run `playwright install` |
| Website unreachable / timeout | Agent returns the error message as a result |
| Agent execution error | Caught in try/except, shown in UI without crashing the app |

---

## Limitations

- **No login support** — cannot handle sites requiring authentication (Google login, etc.)
- **No file downloads** — agent can read page content but not download files
- **Dynamic/JS-heavy sites** — may struggle with complex SPAs or CAPTCHAs
- **One task at a time** — sequential, not parallel browsing
- **Session is not persistent** — browser state resets between Streamlit reruns
