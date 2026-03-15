"""
nexus/core/session.py — Session persistence.

Sessions are stored as human-readable .md files that also contain
TOML front-matter for structured metadata. They can be:
  - Resumed by Nexus (full fidelity)
  - Read by a human as a log
  - Shared, version-controlled, or committed to a repo

File format:
    ---
    session_id: abc12345
    created_at: 2026-03-15T14:30:00
    model: claude-opus-4-5
    ...
    ---

    # Nexus Session — <first user message preview>

    ## [2026-03-15 14:30] 👤 User
    ...

    ## [2026-03-15 14:30] 🤖 Nexus
    ...

    ## [2026-03-15 14:30] 🔧 Tool: filesystem
    **Input:** ...
    **Output:** ...
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from mind_shell.config.settings import Settings


class Message:
    """A single message in the conversation."""

    def __init__(self, role: str, content: str, timestamp: Optional[datetime] = None,
                 tool_name: Optional[str] = None, tool_input: Optional[str] = None):
        self.role = role                 # user | assistant | tool
        self.content = content
        self.timestamp = timestamp or datetime.now()
        self.tool_name = tool_name       # set when role == "tool"
        self.tool_input = tool_input

    def to_api_format(self) -> dict:
        """Convert to Anthropic API message format."""
        if self.role == "tool":
            return {"role": "user", "content": f"[Tool result from {self.tool_name}]\n{self.content}"}
        return {"role": self.role, "content": self.content}

    def to_markdown(self) -> str:
        ts = self.timestamp.strftime("%Y-%m-%d %H:%M")
        if self.role == "user":
            return f"## [{ts}] 👤 User\n\n{self.content}\n"
        elif self.role == "assistant":
            return f"## [{ts}] 🤖 Nexus\n\n{self.content}\n"
        elif self.role == "tool":
            lines = [f"## [{ts}] 🔧 Tool: {self.tool_name}"]
            if self.tool_input:
                lines.append(f"\n**Input:** `{self.tool_input}`")
            lines.append(f"\n**Output:**\n```\n{self.content[:2000]}\n```")
            return "\n".join(lines) + "\n"
        return f"## [{ts}] {self.role}\n\n{self.content}\n"


class Session:
    """A conversation session with full history and metadata."""

    def __init__(self, session_id: str, created_at: datetime, model: str,
                 messages: Optional[List[Message]] = None, metadata: Optional[dict] = None):
        self.id = session_id
        self.created_at = created_at
        self.model = model
        self.messages: List[Message] = messages or []
        self.metadata: dict = metadata or {}

    @property
    def created_at_str(self) -> str:
        return self.created_at.strftime("%Y-%m-%d %H:%M")

    @property
    def message_count(self) -> int:
        return len([m for m in self.messages if m.role in ("user", "assistant")])

    @property
    def preview(self) -> str:
        for m in self.messages:
            if m.role == "user":
                return m.content[:60].replace("\n", " ") + ("…" if len(m.content) > 60 else "")
        return "(empty)"

    def add_turn(self, role: str, content: str, **kwargs) -> None:
        self.messages.append(Message(role=role, content=content, **kwargs))

    def get_api_messages(self, max_history: int = 50) -> List[dict]:
        """Return messages in Anthropic API format, trimmed to max_history."""
        relevant = [m for m in self.messages if m.role in ("user", "assistant", "tool")]
        trimmed = relevant[-max_history:]
        return [m.to_api_format() for m in trimmed]

    def to_markdown(self) -> str:
        """Serialize to a human-readable + machine-loadable Markdown file."""
        front_matter_lines = [
            "---",
            f"session_id: {self.id}",
            f"created_at: {self.created_at.isoformat()}",
            f"model: {self.model}",
            f"message_count: {self.message_count}",
        ]
        if self.metadata:
            for k, v in self.metadata.items():
                front_matter_lines.append(f"{k}: {v!r}")
        front_matter_lines.append("---")
        front_matter = "\n".join(front_matter_lines)

        title = f"# Nexus Session — {self.preview}"
        body = "\n\n".join(m.to_markdown() for m in self.messages)

        return f"{front_matter}\n\n{title}\n\n{body}\n"

    def to_json(self) -> str:
        return json.dumps({
            "session_id": self.id,
            "created_at": self.created_at.isoformat(),
            "model": self.model,
            "message_count": self.message_count,
            "metadata": self.metadata,
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "timestamp": m.timestamp.isoformat(),
                    "tool_name": m.tool_name,
                    "tool_input": m.tool_input,
                }
                for m in self.messages
            ],
        }, indent=2, ensure_ascii=False)


class SessionManager:
    """Manages session persistence (save, load, list, delete)."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.save_dir = settings.session.save_path
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self._current: Optional[Session] = None

    # ── Factories ─────────────────────────────────────────────────────────────

    def new(self) -> Session:
        session = Session(
            session_id=uuid.uuid4().hex[:12],
            created_at=datetime.now(),
            model=self.settings.llm.model,
        )
        self._current = session
        return session

    def load(self, session_id: str) -> Optional[Session]:
        """Load a session by ID prefix (at least 4 chars)."""
        matches = list(self.save_dir.glob(f"{session_id}*.md"))
        if not matches:
            return None
        path = matches[0]
        session = self._parse_md(path)
        self._current = session
        return session

    def load_latest(self) -> Optional[Session]:
        files = sorted(self.save_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            return None
        return self._parse_md(files[0])

    def list_all(self) -> List[Session]:
        sessions = []
        for path in sorted(self.save_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                sessions.append(self._parse_md(path))
            except Exception:
                continue
        return sessions

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self, session: Session) -> Path:
        path = self.save_dir / f"{session.id}.md"
        path.write_text(session.to_markdown(), encoding="utf-8")
        return path

    def _parse_md(self, path: Path) -> Session:
        """Parse a session .md file back into a Session object."""
        text = path.read_text(encoding="utf-8")

        # Extract front matter
        fm_match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
        meta: dict = {}
        if fm_match:
            for line in fm_match.group(1).splitlines():
                if ": " in line:
                    k, _, v = line.partition(": ")
                    meta[k.strip()] = v.strip()

        session_id = meta.get("session_id", path.stem)
        model = meta.get("model", self.settings.llm.model)
        created_at_str = meta.get("created_at", "")
        try:
            created_at = datetime.fromisoformat(created_at_str)
        except ValueError:
            created_at = datetime.fromtimestamp(path.stat().st_mtime)

        # Parse messages from sections
        messages: List[Message] = []
        pattern = re.compile(
            r"## \[(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\] (👤 User|🤖 Nexus|🔧 Tool: (\S+))\n\n(.*?)(?=\n## |\Z)",
            re.DOTALL,
        )
        for match in pattern.finditer(text):
            ts_str, role_raw, tool_name_raw, content = match.groups()
            try:
                ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M")
            except ValueError:
                ts = created_at

            if role_raw == "👤 User":
                role = "user"
            elif role_raw == "🤖 Nexus":
                role = "assistant"
            else:
                role = "tool"

            messages.append(Message(
                role=role,
                content=content.strip(),
                timestamp=ts,
                tool_name=tool_name_raw,
            ))

        return Session(
            session_id=session_id,
            created_at=created_at,
            model=model,
            messages=messages,
        )
