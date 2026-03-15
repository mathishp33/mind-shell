# MindShell Development Roadmap

## Overview

This roadmap is organized by **phases** and **priority**, based on the architecture diagram and identified gaps. Each phase builds on the previous, with clear dependencies.

**Current Architecture State:**
- ✅ Entry points (Chat, Script, Agent modes)
- ✅ Core Engine (Session Manager, Context Builder, Tool Router) — **Partial**
- ✅ LLM Gateway (Anthropic, OpenAI, Ollama support)
- ⚠️ Tool Layer (Implemented but lacks proper orchestration)
- ⚠️ Session Store (Basic, needs upgrade)

---

## Known Limitations & Workarounds

### Issue: Ollama Lacks Native Tool Calling
**Problem:** Ollama (Mistral, Llama2, etc.) doesn't support native function/tool calling like Claude or GPT-4. Instead of making actual tool calls, it just describes them in text.

**Result:** When asking "What files are in this directory?", Ollama responds with:
```
To list files, I would use the filesystem tool like this:
filesystem list .
```
Instead of actually executing the tool.

---

### Workaround Option 1: Parse Text-Based Tool Calls (For Ollama) ⚡ MEDIUM EFFORT

**Concept:** Force the LLM to output tool calls in a parseable format, then extract and execute them.

#### How It Works

1. **Modify system prompt** to teach Ollama a specific format:
```
When you need to use a tool, output it in this format ONLY:
[TOOL_CALL]
name: filesystem
action: list
path: .
[/TOOL_CALL]

Then continue with your response explaining what you did.
```

2. **Parse LLM response** for `[TOOL_CALL]...[/TOOL_CALL]` blocks
3. **Extract tool name and arguments**
4. **Execute tool in main.py**
5. **Feed results back to LLM** for follow-up

#### Implementation Steps

**File:** `mind_shell/llm/client.py` (update `_chat_ollama`)

```python
def _parse_tool_calls_from_text(text: str) -> List[ToolCall]:
    """Extract [TOOL_CALL]...[/TOOL_CALL] blocks from response."""
    import re
    pattern = r'\[TOOL_CALL\](.*?)\[/TOOL_CALL\]'
    matches = re.findall(pattern, text, re.DOTALL)
    
    tool_calls = []
    for match in matches:
        lines = match.strip().split('\n')
        tool_data = {}
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                tool_data[key.strip().lower()] = value.strip()
        
        if 'name' in tool_data:
            tool_calls.append(ToolCall(
                name=tool_data['name'],
                input=tool_data,  # All key-value pairs as input
                id=str(len(tool_calls))
            ))
    
    return tool_calls
```

**Benefits:**
- ✅ Works with any Ollama model
- ✅ Relatively simple to implement
- ✅ Can be added without changing core architecture
- ✅ Fallback: If parsing fails, user still gets text response

**Drawbacks:**
- ❌ Requires careful prompt engineering
- ❌ LLM might not follow format perfectly
- ❌ Need to strip tool calls from final response
- ❌ Less reliable than native tool calling
- ❌ Harder to handle complex multi-step reasoning

**Status:** `NOT STARTED` | **Difficulty:** Medium | **Timeline:** 1-2 days

---

### Workaround Option 2: Switch to Claude or OpenAI (Recommended) ✅ EASIEST

**Concept:** Just use a different LLM provider that has native tool support.

**Pros:**
- ✅ Native tool calling (guaranteed to work)
- ✅ No prompt engineering needed
- ✅ More reliable for complex tasks
- ✅ Better reasoning capabilities
- ✅ Free tier available (Anthropic, OpenAI)

**Cons:**
- ❌ Requires API key
- ❌ API costs (though small)
- ❌ Not local/offline

**How to Switch:**

```python
# In main.py, line ~40:
llm_settings.provider = "anthropic"  # instead of "ollama"
llm_settings.model = "claude-3-5-haiku"  # fast & cheap
```

Then install Anthropic SDK:
```bash
pip install anthropic
export ANTHROPIC_API_KEY="sk-ant-..." # Get from https://console.anthropic.com
```

**Status:** `READY TO USE` | **Difficulty:** Trivial | **Timeline:** 5 minutes

---

## Phase 1: Foundation (Weeks 1-3) 🔴 CRITICAL

### Core Issue: Tool Execution Gap
The architecture shows a **Tool Router** in the Core Engine, but there's no proper **Tool Executor** to handle:
- Parsing LLM tool calls correctly
- Executing tools async/sync
- Formatting results back to context
- Error handling & recovery

#### 1.1 Create Tool Execution Engine
**File:** `mind_shell/core/tool_executor.py`
**Status:** `NOT STARTED`

```python
class ToolExecutor:
    """Orchestrates tool execution and error handling."""
    
    async def execute(self, tool_call: ToolCall) -> ToolResult:
        """Execute a single tool call."""
        
    def validate(self, tool_call: ToolCall) -> bool:
        """Validate input before execution."""
        
    async def execute_many(self, tool_calls: List[ToolCall]) -> List[ToolResult]:
        """Execute multiple tool calls (with dependency resolution)."""
```

**Subtasks:**
- [ ] Define `ToolCall` protocol (name, input, id)
- [ ] Define `ToolResult` protocol (success, data, error, retry_args)
- [ ] Implement execution dispatch to `get_all_tools()`
- [ ] Add error handling with helpful suggestions
- [ ] Add timeout handling per tool
- [ ] Add execution logging/metrics
- [ ] Write unit tests

**Files to modify:**
- `mind_shell/core/agent.py` — use ToolExecutor in plan_and_act loop
- `mind_shell/ui/chat.py` — handle tool results in chat loop
- `mind_shell/tools/base_tool.py` — ensure all tools have consistent interface

---

#### 1.2 Standardize Message Protocol
**File:** `mind_shell/core/message.py` (new)
**Status:** `NOT STARTED`

```python
class Message(BaseModel):
    """Unified message format for all components."""
    role: Literal["user", "assistant", "tool"]
    content: str
    tool_name: Optional[str] = None  # For tool messages
    tool_call_id: Optional[str] = None  # Link result to call
    metadata: Dict[str, Any] = {}  # timing, tokens, etc.
    timestamp: datetime
```

**Benefits:**
- All components use same message format
- Easier to log, export, debug
- Track metadata (execution time, token cost, etc.)

**Subtasks:**
- [ ] Define `Message` dataclass
- [ ] Update `Session.add_message()` to use Message
- [ ] Update all components to import from `core.message`
- [ ] Update session file format to include message metadata
- [ ] Add type hints throughout codebase

---

#### 1.3 Improve Context Builder (Smart Window Management)
**File:** `mind_shell/core/context.py` (update existing)
**Status:** `IN PROGRESS`

**Current:** Just concatenates all messages
**Needed:**
- Token counting (estimate context size)
- Message pruning (summarize old conversations)
- Priority ranking (recent + tool results are important)
- Better error messages when context overflows

**Subtasks:**
- [ ] Add `estimate_tokens(message)` function
- [ ] Implement message summarization (use LLM to compress old messages)
- [ ] Add `build_messages_smart()` with token budget
- [ ] Test with long conversations (50+ messages)
- [ ] Add logs for context optimization decisions

---

#### 1.4 Fix Agent Loop (plan_and_act cycle)
**File:** `mind_shell/core/agent.py` (update existing)
**Status:** `NEEDS WORK`

**Current:** Basic structure exists but untested
**Needed:**
- Proper observation → planning → action → feedback loop
- Integration with new ToolExecutor
- Iteration limits and max depth checks
- Fallback strategies (if plan fails, retry or explain to user)

**Subtasks:**
- [ ] Refactor `plan_and_act()` to use ToolExecutor
- [ ] Add iteration counter + max_iterations limit
- [ ] Implement fallback on tool failure (ask user for help)
- [ ] Add proper logging at each step
- [ ] Test with complex tasks (refactoring code, git workflows, etc.)
- [ ] Add timeout protection (don't run forever)

---

#### 1.5 Update Session File Format to v2
**File:** `mind_shell/core/session.py` (update existing)
**Status:** `NOT STARTED`

**Current format (v1):**
```markdown
---
session_id: abc123
created_at: 2026-03-15T14:30:00
model: claude-opus-4-5
message_count: 12
---

# Session Title
```

**New format (v2) — includes tool calls:**
```markdown
---
session_id: abc123
version: 2
created_at: 2026-03-15T14:30:00
model: claude-opus-4-5
total_tokens: 5234
tool_calls: 3
---

# Session Title

## Message 1 [USER] · 2026-03-15 14:30:00
content...

## Message 2 [ASSISTANT] · 2026-03-15 14:30:05
content...
tokens_used: 234

## Tool Call 3 [SYSTEM] · 2026-03-15 14:30:06
**Tool:** filesystem
**Input:** {"path": "."}
**Output:** [file1, file2]
**Duration:** 145ms
**Status:** ✅ success
---
```

**Subtasks:**
- [ ] Add version field to session metadata
- [ ] Add tool calls as separate message entries
- [ ] Add execution metadata (duration, tokens, status)
- [ ] Update parser to handle v2 format
- [ ] Keep backward compatibility with v1
- [ ] Migration script for old sessions

**Priority Impact:** HIGH — Need this before tool results are properly logged

---

### Phase 1 Completion Checklist
- [ ] ToolExecutor working and integrated
- [ ] Message protocol standardized
- [ ] Context builder handles large conversations
- [ ] Agent loop properly orchestrates tools
- [ ] Session v2 format stores tool calls

**Expected Timeline:** 2-3 weeks
**Deliverable:** Fully functional tool orchestration + autonomous agent mode works

---

## Phase 2: Experience & Reliability (Weeks 4-6) 🟠 HIGH PRIORITY

### 2.1 Enhanced Error Handling
**File:** `mind_shell/core/errors.py` (new), update all tools
**Status:** `NOT STARTED`

**Goal:** When tools fail, help user recover

```python
class ToolError(Exception):
    success: bool = False
    error_message: str
    suggestion: str  # "Did you mean...?"
    retry_args: Optional[Dict] = None  # Auto-retry config
    error_code: str  # For programmatic handling
```

**Example:**
```
Tool: shell | Command: "rm -rf /"
Error: "Cannot execute destructive commands without --force"
Suggestion: "Did you mean 'rm -rf ./tmpdir'?"
Retry Args: {"force": True}
```

**Subtasks:**
- [ ] Define standard error types (validation, permission, timeout, etc.)
- [ ] Update all tools to return structured errors
- [ ] Add error recovery logic in ToolExecutor
- [ ] Implement auto-retry with backoff where safe
- [ ] Add user-friendly error messages to chat
- [ ] Test error paths in all tools

---

### 2.2 Observable Execution (Metrics & Logging)
**File:** `mind_shell/core/metrics.py` (new)
**Status:** `NOT STARTED`

Track:
- Token usage (input/output per call)
- Tool execution time
- Error rates
- Cost estimate (for paid APIs)

**Subtasks:**
- [ ] Add `ExecutionMetrics` dataclass
- [ ] Track tokens in LLMClient responses
- [ ] Track timing in ToolExecutor
- [ ] Add cost calculation (optional Anthropic/OpenAI pricing)
- [ ] Display metrics in chat (`↑450 ↓380 tokens`)
- [ ] Log metrics to file for analysis

---

### 2.3 Streaming Improvements
**File:** `mind_shell/ui/chat.py` (update)
**Status:** `PARTIAL`

**Needed:**
- Real-time token streaming with pretty format
- Tool call notifications (show which tool is running)
- Progress for long operations
- Better spinner/loading indicators

**Subtasks:**
- [ ] Implement streaming token display
- [ ] Add tool execution UI ("🔧 Running filesystem...")
- [ ] Add progress bars for long operations
- [ ] Test with slow connections

---

### 2.4 Plugin System (Extensibility)
**File:** `mind_shell/plugins/` (new directory structure)
**Status:** `NOT STARTED`

Allow users to add custom tools without modifying core code

**Structure:**
```
~/.mind-shell/plugins/
  ├── my_custom_tool/
  │   ├── __init__.py
  │   ├── tool.py
  │   └── config.toml
```

**Subtasks:**
- [ ] Define plugin interface (inherit from BaseTool)
- [ ] Create plugin loader in `get_all_tools()`
- [ ] Document plugin creation guide
- [ ] Add example plugin (e.g., Slack notification)
- [ ] Plugin hot-reload (optional)
- [ ] Plugin marketplace/registry (future)

---

### 2.5 Session Resume & Management
**File:** `mind_shell/core/session.py` + CLI improvements
**Status:** `PARTIAL`

**Needed:**
- List all sessions with summaries
- Delete old sessions
- Rename sessions
- Merge sessions
- Search session history

**Subtasks:**
- [ ] Add `SessionManager.list()` with filtering
- [ ] Add `SessionManager.summarize()` (quick overview)
- [ ] Add `SessionManager.delete()`
- [ ] Add `SessionManager.merge()` (combine two sessions)
- [ ] CLI commands for session management
- [ ] Session search by content/date/model

---

### Phase 2 Completion Checklist
- [ ] Error handling is user-friendly with recovery suggestions
- [ ] Metrics tracking (tokens, timing, cost)
- [ ] Streaming UI improvements
- [ ] Basic plugin system working
- [ ] Session management commands exist

**Expected Timeline:** 2-3 weeks
**Deliverable:** Robust, observable, extensible assistant

---

## Phase 3: Knowledge & Memory (Weeks 7-9) 🟡 NICE-TO-HAVE

### 3.1 Memory System (Context-Aware)
**File:** `mind_shell/core/memory.py` (new)
**Status:** `NOT STARTED`

**Goal:** Remember and retrieve relevant past context

**Approach:**
1. Store session summaries + embeddings
2. On new chat, find similar past sessions
3. Include relevant context in system prompt

**Subtasks:**
- [ ] Add embedding model (sentence-transformers)
- [ ] Implement summary extraction (LLM-based)
- [ ] Build vector index of past sessions
- [ ] Implement semantic search
- [ ] Auto-load relevant context on resume
- [ ] Add memory management (keep recent, archive old)

**Optional:** Use external vector DB (Milvus, Weaviate, Pinecone)

---

### 3.2 RAG (Retrieval Augmented Generation)
**File:** `mind_shell/tools/rag.py` (new)
**Status:** `NOT STARTED`

Let user upload documents and ask questions about them

**Subtasks:**
- [ ] Implement document chunking
- [ ] Add embeddings for chunks
- [ ] Implement semantic search over docs
- [ ] Integration with chat (retrieve relevant docs automatically)
- [ ] Support: PDF, TXT, Markdown
- [ ] Optional: Web scraper + indexing

---

### 3.3 Knowledge Base Integration
**File:** `mind_shell/core/knowledge.py` (new)
**Status:** `NOT STARTED`

Indexed store of:
- Project documentation
- Code snippets
- Common patterns
- Solutions to problems

**Subtasks:**
- [ ] Design KB schema
- [ ] Implement indexing
- [ ] Add search UI
- [ ] Integration with context builder

---

### Phase 3 Completion Checklist
- [ ] Memory system working (recalls relevant past sessions)
- [ ] RAG system working (can answer questions about documents)
- [ ] Knowledge base set up

**Expected Timeline:** 2-3 weeks
**Deliverable:** Smarter, context-aware assistant that learns from past

---

## Phase 4: Scale & Optimize (Weeks 10+) 🟢 FUTURE

### 4.1 Async Tool Execution
**File:** `mind_shell/core/tool_executor.py` (enhance)
**Status:** `NOT STARTED`

Support parallel tool execution (e.g., run 3 web searches simultaneously)

**Subtasks:**
- [ ] Implement `execute_many_async()`
- [ ] Add dependency resolution between tools
- [ ] Implement timeout per tool
- [ ] Add concurrency limits

---

### 4.2 Model Auto-Selection
**File:** `mind_shell/llm/client.py` (enhance)
**Status:** `NOT STARTED`

Automatically choose best model for task:
- Quick questions → fast_model (claude-haiku)
- Complex reasoning → claude-opus
- Vision tasks → Claude Vision
- Cost optimization → cheapest sufficient model

**Subtasks:**
- [ ] Implement model router logic
- [ ] Add capability detection
- [ ] Add cost/latency tradeoffs
- [ ] Test with different model combinations

---

### 4.3 Web UI (Optional)
**File:** `mind_shell/web/` (new)
**Status:** `NOT STARTED`

Browser-based interface (Flask/FastAPI + React/Vue)

**Features:**
- Chat interface (similar to CLI)
- Session browser
- Settings management
- Real-time collaboration (optional)

---

### 4.4 Monitoring & Observability
**File:** `mind_shell/monitoring/` (new)
**Status:** `NOT STARTED`

**Integrate:**
- OpenTelemetry for tracing
- Prometheus metrics export
- Performance dashboard
- Cost tracking per user/project

---

### 4.5 Testing & CI/CD
**File:** `tests/` (expand)
**Status:** `MINIMAL`

**Add:**
- Integration tests (end-to-end flows)
- Mock LLM responses for testing
- Tool mock implementations
- Performance benchmarks
- GitHub Actions CI pipeline

---

### Phase 4 Completion Checklist
- [ ] Async tool execution working
- [ ] Model auto-selection functional
- [ ] Web UI available (optional)
- [ ] Monitoring & observability in place
- [ ] Full test coverage

**Expected Timeline:** 3-4 weeks
**Deliverable:** Production-ready system

---

## Architecture Enhancements Map

Based on `mind_shell_architecture.svg`:

### Current State
```
Entry → Core Engine → LLM → Tools → System
            ↓
       Session Store
```

### Phase 1 Improvements
```
Entry → Core Engine (improved) → LLM → Tool Executor (NEW) → Tools → System
                ↓                                                   ↓
        Context Builder (v2)                              Error Recovery (NEW)
        Tool Router (enhanced)
        Message Protocol (NEW)
                ↓
           Session Store (v2)
```

### Phase 2 Additions
```
Same as Phase 1 + Metrics + Error Handlers + Plugin System
```

### Phase 3 Additions
```
Same as Phase 2 + Memory System + RAG + Knowledge Base
```

---

## Priority Matrix

| Component | Phase | Difficulty | Impact | Dependencies |
|-----------|-------|------------|--------|--------------|
| ToolExecutor | 1 | High | 🔴 CRITICAL | None |
| Message Protocol | 1 | Medium | 🔴 CRITICAL | ToolExecutor |
| Agent Loop Fix | 1 | Medium | 🔴 CRITICAL | ToolExecutor |
| Context Builder v2 | 1 | Medium | 🟠 HIGH | None |
| Session v2 Format | 1 | Medium | 🟠 HIGH | Message Protocol |
| Error Handling | 2 | Medium | 🔴 CRITICAL | ToolExecutor |
| Metrics | 2 | Low | 🟠 HIGH | Message Protocol |
| Streaming UI | 2 | Low | 🟢 NICE | None |
| Plugin System | 2 | Medium | 🟢 NICE | ToolExecutor |
| Memory System | 3 | High | 🟢 NICE | None |
| RAG | 3 | High | 🟢 NICE | Memory? |
| Web UI | 4 | High | 🟢 NICE | All of above |
| Async Tools | 4 | Medium | 🟠 HIGH | ToolExecutor |

---

## Getting Started (Next Steps)

### This Week
1. **Start Phase 1.1** — Create `ToolExecutor` class
   - Define protocols (ToolCall, ToolResult)
   - Implement basic dispatch logic
   - Add to agent loop

2. **Start Phase 1.2** — Create `Message` protocol
   - Move to `core/message.py`
   - Update session to use it

### Next Week
1. **Complete Phase 1.1-1.3** — Tool orchestration working
2. **Start testing** — Create test cases for tool execution

### By End of Month
- [ ] Phase 1 complete
- [ ] Tool-based agent mode functional
- [ ] Session v2 storing tool results
- [ ] Basic tests passing

---

## File References

### New Files to Create
- `mind_shell/core/tool_executor.py` — Tool orchestration engine
- `mind_shell/core/message.py` — Unified message protocol
- `mind_shell/core/errors.py` — Error handling
- `mind_shell/core/metrics.py` — Execution metrics
- `mind_shell/core/memory.py` — Session memory & context
- `mind_shell/plugins/` — Plugin system infrastructure

### Existing Files to Enhance
- `mind_shell/core/session.py` — Update to v2 format
- `mind_shell/core/agent.py` — Integrate ToolExecutor
- `mind_shell/core/context.py` — Smart context management
- `mind_shell/ui/chat.py` — Streaming improvements, error display
- `mind_shell/llm/client.py` — Token tracking, model selection
- `mind_shell/tools/base_tool.py` — Consistent error handling

### Testing
- `tests/test_tool_executor.py` — Tool execution tests
- `tests/test_agent.py` — Agent loop tests
- `tests/test_context.py` — Context management tests
- `tests/fixtures/` — Mock tools and LLM responses

---

## Success Criteria

**Phase 1 (Week 3):** ✅ When this is true:
- Tools execute reliably with proper error handling
- Agent mode can handle multi-step tasks
- Tool results are logged in sessions
- All tests passing

**Phase 2 (Week 6):** ✅ When this is true:
- Users understand what's happening (metrics, logging)
- Errors provide helpful recovery suggestions
- Plugin system allows easy extensions
- Session management is user-friendly

**Phase 3 (Week 9):** ✅ When this is true:
- Assistant remembers relevant past context
- Can analyze uploaded documents
- RAG system works

**Phase 4 (Week 13):** ✅ When this is true:
- Tool calls execute in parallel where possible
- Cost and performance are optimized
- Optional: Web UI available
- Full observability & monitoring

---

## Notes

- **Architecture diagrams** saved: `mind_shell_architecture.svg`
- **Main entry point** for testing: `main.py` (uses Ollama)
- **Python version required:** 3.11+
- **Windows-compatible** — testing on Windows PowerShell

---

📝 **Last Updated:** March 15, 2026
🔄 **Review Frequency:** Weekly or after completing each phase
