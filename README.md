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

### Option 1: Using Anthropic Claude (Cloud)

Get your Anthropic API key from [console.anthropic.com](https://console.anthropic.com/):

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
mind_shell chat
```

### Option 2: Using Ollama (Local LLM) — 🔥 Recommended for Development

**1. Install Ollama:**
- Download from [ollama.ai](https://ollama.ai)
- Or on macOS: `brew install ollama`
- Or on Linux: `curl https://ollama.ai/install.sh | sh`

**2. Start Ollama server:**
```bash
ollama serve
# Runs on http://localhost:11434
```

**3. Pull a model** (in another terminal):
```bash
ollama pull mistral          # Fast, good quality (7B)
# or
ollama pull llama2           # Larger, slower (7B)
# or
ollama pull neural-chat      # Chat-optimized (7B)
```

**4. Run MindShell with Ollama:**
```bash
# Interactive mode
mind_shell chat --provider ollama --model mistral

# Or create a local config file: mind-shell.toml
cat > mind-shell.toml << 'EOF'
[llm]
provider = "ollama"
model = "mistral"
base_url = "http://localhost:11434"
max_tokens = 2048
EOF

mind_shell chat
```

**5. Try the minimal example:**
```bash
python main.py
```

### Model Recommendations

| Model | Size | Speed | Quality | Best For |
|-------|------|-------|---------|----------|
| **mistral** | 7B | ⚡⚡⚡ | ⭐⭐⭐⭐ | General tasks, **recommended** |
| neural-chat | 7B | ⚡⚡⚡ | ⭐⭐⭐⭐ | Chat, slightly smaller |
| llama2 | 7B | ⚡⚡ | ⭐⭐⭐ | Stable, safe |
| mistral-openorca | 7B | ⚡ | ⭐⭐⭐⭐ | Instruction-following |
| mixtral | 46B | 🐢 | ⭐⭐⭐⭐⭐ | Best quality (requires 24GB RAM) |

**Quick setup:**
```bash
ollama pull mistral
ollama serve &
python main.py
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

### Ollama not connecting
Ensure Ollama is running:
```bash
# Check if service is running
curl http://localhost:11434/api/tags

# If not, start it
ollama serve
```

---

## 🚀 What to Build Next?

### Priority 1: Core Workflow (Next 2 weeks)
- [ ] **Fix Tool Integration** — Ensure tools properly return structured results to LLM
  - Add `tool_result` message type in session
  - Implement tool calling loop in `Agent` class
  - Add error handling when tools fail

- [ ] **Refine Agent Mode** — Make autonomous task execution work smoothly
  - Implement proper `plan_and_act` loop
  - Add iteration counter and max_iterations limit
  - Implement fallback strategies

- [ ] **ChatUI Polish** — Improve interactive experience
  - Add streaming tokens display
  - Show token usage (input/output)
  - Better error messages
  - Support for `/commands` within chat

### Priority 2: Experience (3-4 weeks)
- [ ] **Memory System** — Add context-aware memory
  - Store summaries of past conversations
  - Embedding-based semantic search of session history
  - Auto-load relevant context on session resume

- [ ] **Plugin System** — Allow custom tools
  - Define plugin interface
  - Load plugins from `~/.mind-shell/plugins/`
  - Hot-reload during runtime

- [ ] **Web UI** — Optional browser interface
  - Simple Flask/FastAPI server
  - WebSocket for real-time chat
  - Session management dashboard

### Priority 3: Advanced Features (Weeks 5+)
- [ ] **Multi-turn Tool Calls** — Proper function calling
  - Handle concurrent tool calls
  - Dependency resolution between tools
  - Async tool execution

- [ ] **Knowledge Base Integration**
  - RAG (Retrieval Augmented Generation)
  - Vector database support (Milvus, Weaviate, Pinecone)
  - Document indexing

- [ ] **Monitoring & Logging**
  - OpenTelemetry integration
  - Cost tracking (tokens, API calls)
  - Performance metrics dashboard

---

## 🏗️ Architectural Improvements

### Current State
```
User Input → CLI → LLM → Tools → Session Store
```

### Recommended Enhancements

#### 1. **Tool Execution Engine** ⭐ HIGH Priority
```
┌─────────────────────────────────────────┐
│  Tool Orchestrator (NEW)                 │
├─────────────────────────────────────────┤
│ Responsibilities:                        │
│ • Parse tool calls from LLM              │
│ • Execute tools (sync & async)           │
│ • Handle errors and retries              │
│ • Format results back to LLM context     │
│ • Track execution history                │
└─────────────────────────────────────────┘
       ↓
   Tools Layer
       ↓
   System (filesystem, shell, git, etc.)
```

**File:** `mind_shell/core/tool_executor.py`
```python
class ToolExecutor:
    async def execute(self, tool_call: ToolCall) -> ToolResult:
        # Dispatch to tool
        # Handle errors
        # Format result
        pass
    
    def validate(self, tool_call: ToolCall) -> bool:
        # Check permissions
        # Validate inputs
        pass
```

#### 2. **Message Protocol** - Standardize Communication
```python
# Current: Multiple message formats
# Proposed: Unified protocol

class Message(BaseModel):
    role: Literal["user", "assistant", "tool"]
    content: str
    tool_name: Optional[str] = None
    tool_call_id: Optional[str] = None
    metadata: Dict[str, Any] = {}  # logs, timing, etc.
    timestamp: datetime
```

#### 3. **Context Builder** - Smart Context Window Management
```
Issue: Too many messages overflow context window

Solution:
┌──────────────────────────┐
│ Smart Context Builder    │
├──────────────────────────┤
│ • Summarize old messages │
│ • Keep recent N messages │
│ • Prioritize tool calls  │
│ • Track token usage      │
└──────────────────────────┘
```

**File:** `mind_shell/core/context_builder.py` (improve existing)

#### 4. **Session Format Upgrade** - Better Persistence
**Current:** TOML frontmatter + Markdown
**Issue:** Tool calls not properly logged

**Proposed:**
```markdown
---
session_id: abc123
version: 2  # NEW
---

# Session Title

## Message 1 [USER]
content...

## Message 2 [ASSISTANT]
content...

## Tool Call 3 [SYSTEM]
tool: filesystem
input: {}
output: {}
duration_ms: 145
status: success
---
```

#### 5. **Error Handling & Recovery** - Graceful Degradation
```python
class ToolResult:
    success: bool
    data: Optional[Any]
    error: Optional[str]
    suggestion: Optional[str]  # Help user fix
    retry_args: Optional[Dict]  # Auto-retry config
```

Example:
```
Tool: shell | Command: "rm -rf /"
Error: "Cannot execute destructive commands"
Suggestion: "Did you mean 'rm -rf ./tmpdir'?"
```

#### 6. **Model Abstraction Layer** - Support More LLMs
**Current:** Anthropic + OpenAI + Ollama
**Improve:**
```
LLMClient (abstract)
    ├── AnthropicClient
    ├── OpenAIClient  
    ├── OllamaClient
    ├── GroqClient (NEW - super fast inference)
    └── LocalLLMClient (LLaMA.cpp, etc.)
```

**Add:** Unified response format + capability detection

#### 7. **Observability** - Track What's Happening
```python
# NEW: Metrics collection
class ExecutionMetrics:
    total_tokens: int
    tool_calls: int
    errors: int
    duration_sec: float
    cost_estimate: float  # For cloud models
```

---

## 📊 Architecture Diagram (Enhanced)

```
┌──────────────────┐
│   User Input     │
│    (Chat/CLI)    │
└────────┬─────────┘
         │
         ↓
┌──────────────────────────────┐
│    Command Parser & Router   │
│  (understand intent)          │
└────────┬─────────────────────┘
         │
         ├─→ Chat Mode?     ──→ ChatUI
         ├─→ Agent Mode?    ──→ Agent Planner
         √─→ Script Mode?   ──→ SingleShot
         │
         ↓
┌──────────────────────────────┐
│   Context Manager (NEW)      │
│  • Build message history     │
│  • Manage token budget       │
│  • Compress old messages     │
└────────┬─────────────────────┘
         │
         ↓
┌──────────────────────────────┐
│   LLM Client (Abstract)      │
│  • Anthropic / OpenAI        │
│  • Ollama / Groq             │
│  • Unified response format   │
└────────┬─────────────────────┘
         │
         ↓
┌──────────────────────────────┐
│  Tool Executor (NEW) ⭐       │
│  • Parse tool calls          │
│  • Validate & dispatch       │
│  • Error handling            │
│  • Format results for LLM    │
└────────┬─────────────────────┘
         │
    ┌────┴────┬───────┬────────┬─────┐
    ↓         ↓       ↓        ↓     ↓
┌────────┐┌──────┐┌──────┐┌─────────┐
│FileSystem WebAPI   Git  │Shell    │...
│ Read   Search Fetch    │Execute
│ Write  Scrape  Log    │Confirm
└────────┘└──────┘└──────┘└─────────┘
    │         │       │        │
    └─────┬───┴───────┴────────┘
         ↓
    System (OS/Network)
         │
         ↓
┌──────────────────────────────┐
│  Session Manager             │
│  • Store messages            │
│  • Save to disk (.md, .json) │
│  • Resume / resume from ID   │
└──────────────────────────────┘
```

---

## 🎯 Recommended Implementation Order

1. **Tool Executor** (fixes critical issue with tool routing)
2. **Message Protocol Upgrade** (foundation for everything)
3. **Context Builder Improvements** (handle large conversations)
4. **Error Handling & Recovery** (stability)
5. **Plugin System** (extensibility)
6. **Memory/RAG** (smarter responses)
7. **Web UI** (accessibility)

---

## 📝 Development Checklist for Architecture

- [ ] Create `ToolExecutor` class to handle async tool calls
- [ ] Define unified `Message` protocol with metadata
- [ ] Implement `ContextBuilder` with token budgeting
- [ ] Add `ToolResult` with error handling
- [ ] Create abstract `LLMClient` base class
- [ ] Add observability with `ExecutionMetrics`
- [ ] Update session format to v2
- [ ] Add comprehensive error messages with suggestions
- [ ] Create plugin interface definition
- [ ] Add integration tests for tool execution loop

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
