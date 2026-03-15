# MindShell 🧠

A powerful AI assistant for the terminal. Chat with Claude, automate tasks, and enhance your workflow directly from your command line.

## Features

### 🤖 Core Capabilities
- **Interactive Chat Mode** — Real-time streaming conversations with Claude AI
- **Autonomous Agent Mode** — Break down tasks into steps and execute them automatically
- **Script/CI Mode** — Non-interactive single-shot prompts for automation and pipelines
- **Session Management** — Save and resume conversations, export as Markdown or JSON

### 🛠️ Built-in Tools
- **Filesystem Operations** — Read, write, search, and explore files and directories
- **Web Tools** — Search the web and fetch page content (Brave Search, Serper, DuckDuckGo)
- **Git Integration** — View status, diffs, logs, create commits, and manage branches
- **Shell Execution** — Run shell commands with optional confirmation
- **PDF Reader** — Extract and analyze PDF documents
- **Image Analyzer** — Analyze and describe images using Claude Vision
- **Web Scraper** — Convert web pages to clean Markdown

### ⚙️ Configuration
- **TOML-based Settings** — Local or global configuration files
- **Multiple LLM Models** — Support for Claude Opus and Haiku models
- **Flexible Tool Settings** — Enable/disable tools, set timeouts, control confirmations
- **Agent Modes** — `confirm` (approve each action) or `yolo` (full automation)

### 💾 Session Persistence
- **Auto-save** — Sessions automatically save after each message
- **Human-readable Format** — Sessions stored as Markdown with TOML frontmatter
- **Easy Resumption** — Resume previous sessions by ID or load the latest

---

## Quick Start

### Installation

```bash
pip install mind-shell
```

Or from source:
```bash
git clone https://github.com/yourusername/mind-shell.git
cd mind-shell
pip install -e .
```

### Set up API Key

Get your Anthropic API key from [console.anthropic.com](https://console.anthropic.com/):

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

### First Chat

```bash
mind_shell chat
```

You'll see:
```
╔═══════════════════════════════════╗
║      NEXUS CLI  ·  v0.1.0         ║
╚═══════════════════════════════════╝

Type your message to start chatting.
Commands: /help · /export · /session · /tools · /clear · /exit

Session: a1b2c3d4 · Model: claude-opus-4-5 · Tools: 7 enabled

you › 
```

Type your question and press Enter. Claude will respond with streaming output:

```
you › what's in this directory?

nexus › 
Looking at your current directory...

[Directory listing with files and structure]

↑450 ↓380 tokens
```

---

## Usage Guide

### 1️⃣ Interactive Chat Mode

Start an interactive session:

```bash
mind_shell chat
```

Or resume a previous session:

```bash
mind_shell chat abc12345  # Session ID or prefix
```

**Commands available in chat:**

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/exit` or `/quit` | Exit the chat |
| `/clear` | Clear the screen |
| `/session` | Show current session info |
| `/tools` | List enabled tools |
| `/export [md\|json]` | Export session as Markdown or JSON |
| `/model <name>` | Switch to a different model |

**Tips:**
- Paste multi-line code directly — press Enter twice to send
- Use `@filename` to include file contents in your message
- Sessions auto-save after every message

### 2️⃣ Script Mode (One-shot Prompts)

Run a single query without interactive mode:

```bash
mind_shell --prompt "write a python function to calculate fibonacci"
```

**Options:**
- `--model` — Override the default model
- `--json` — Output response as JSON (for CI/automation)
- `--no-tools` — Disable all tools for pure conversation
- `--session` — Resume an existing session with your prompt

**Example for CI:**
```bash
mind_shell --prompt "check if all tests pass" --json > result.json
```

### 3️⃣ Agent Mode (Autonomous Tasks)

Coming soon! Run high-level tasks that Claude breaks down and executes:

```bash
mind_shell agent "refactor this codebase to use dependency injection"
```

The agent will:
1. Break the task into concrete steps
2. Execute tools automatically (with confirmation option)
3. Adapt based on results
4. Report completion with a summary

---

## Configuration

### Configuration File

Create `~/.config/mind-shell/mind-shell.toml` (or `./mind-shell.toml` for local override):

```toml
[llm]
provider = "anthropic"
model = "claude-opus-4-5"      # Default model
fast_model = "claude-haiku-4-5"  # For quick operations
max_tokens = 8096
temperature = 0.7
stream = true

[session]
auto_save = true
save_dir = "~/.mind-shell/sessions"
max_history = 50    # Messages kept in context

[tools]
enabled = ["filesystem", "web_search", "web_fetch", "git", "shell", "pdf", "image"]
shell_confirm = true     # Ask before running shell commands
shell_timeout = 30       # seconds
web_search_provider = "brave"  # brave, serper, or duckduckgo
max_search_results = 5
max_file_size_kb = 512

[agent]
mode = "confirm"    # confirm: approve each action, yolo: full automation
max_iterations = 20
plan_before_act = true

[ui]
theme = "dark"
markdown_render = true        # Render responses as Markdown
show_tool_calls = true        # Display tool executions
show_token_count = true       # Show token usage
```

### Environment Variables

```bash
# Required
export ANTHROPIC_API_KEY="sk-ant-..."

# Optional
export BRAVE_API_KEY="..."     # For web search
export SERPER_API_KEY="..."    # Alternative web search
```

---

## Examples

### Analyze a File

```
you › analyze this file for security issues: @src/auth.py

nexus › [Reads auth.py and provides detailed security analysis]
```

### Search the Web

```
you › what are the latest developments in quantum computing?

nexus › [Performs web search and summarizes results]
```

### Git Workflow

```
you › show me the recent commits and what changed

nexus › [Displays git log and diffs]
```

### Run Commands

```
you › run python -m pytest tests/ and tell me about any failures

nexus › [Executes command and analyzes output]
```

**Note:** Shell commands require confirmation by default (disable with `shell_confirm = false` in config)

### Export a Session

```
you › /export md

nexus › ✅ Exported to nexus-export-a1b2c3d4.md
```

Session files are Markdown with TOML metadata:
```markdown
---
session_id: a1b2c3d4
created_at: 2026-03-15T14:30:00
model: claude-opus-4-5
message_count: 12
---

# NexusShell Session — What's in this directory?

## [2026-03-15 14:30] 👤 User
what's in this directory?

## [2026-03-15 14:30] 🤖 Nexus
Looking at your current directory...

[Response content]
```

---

## Advanced Features

### Web Scraping to Markdown

```
you › fetch and summarize https://example.com/docs

nexus › [Converts HTML to clean Markdown and summarizes]
```

### PDF Analysis

```
you › analyze this PDF and extract the key findings: @report.pdf

nexus › [Reads PDF and provides analysis]
```

### Image Understanding

```
you › what's in this screenshot? @screenshot.png

nexus › [Uses Claude Vision to analyze and describe the image]
```

---

## Troubleshooting

### "ANTHROPIC_API_KEY not set"
Make sure your API key is exported:
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

### Command not found: `mind_shell`
Ensure the package is installed:
```bash
pip install -e .  # If installing from source
```

### Web search not working
- For Brave Search: Get API key from [api.search.brave.com](https://api.search.brave.com)
- For Serper: Get API key from [serper.dev](https://serper.dev)
- Without these, DuckDuckGo is used as fallback (limited results)

### Sessions not saving
Check that `~/.mind-shell/sessions` directory is writable:
```bash
mkdir -p ~/.mind-shell/sessions
chmod 755 ~/.mind-shell/sessions
```

---

## Development

### Project Structure

```
mind-shell/
├── mind_shell/
│   ├── cli.py              # Command-line interface
│   ├── config/             # Settings management
│   ├── core/               # Session, context, agent logic
│   ├── llm/                # Claude API client
│   ├── tools/              # All tool implementations
│   └── ui/                 # Chat interface
├── mind_shell.toml         # Project config
└── README.md
```

### Running from Source

```bash
git clone https://github.com/yourusername/mind-shell.git
cd mind-shell
pip install -e ".[dev]"
pytest
```

---

## License

MIT

## Contributing

Contributions welcome! Please open issues and pull requests on GitHub.
