"""
nexus/config/settings.py — Configuration management.

Priority: local nexus.toml > ~/.config/nexus/nexus.toml > defaults
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import toml


@dataclass
class LLMSettings:
    provider: str = "anthropic"
    model: str = "claude-opus-4-5"
    base_url: str = "https://api.anthropic.com"
    fast_model: str = "claude-haiku-4-5"
    max_tokens: int = 8096
    temperature: float = 0.7
    stream: bool = True


@dataclass
class SessionSettings:
    auto_save: bool = True
    save_dir: str = "~/.mind_shell/sessions"
    max_history: int = 50

    @property
    def save_path(self) -> Path:
        return Path(self.save_dir).expanduser()


@dataclass
class ToolSettings:
    enabled: List[str] = field(default_factory=lambda: [
        "filesystem", "web_search", "web_fetch", "git",
        "shell", "pdf", "image", "code"
    ])
    shell_confirm: bool = True
    shell_timeout: int = 30
    web_search_provider: str = "brave"
    max_search_results: int = 5
    max_file_size_kb: int = 512


@dataclass
class AgentSettings:
    mode: str = "confirm"        # confirm | yolo
    max_iterations: int = 20
    plan_before_act: bool = True


@dataclass
class UISettings:
    theme: str = "dark"
    markdown_render: bool = True
    show_tool_calls: bool = True
    show_token_count: bool = True


@dataclass
class Settings:
    llm: LLMSettings = field(default_factory=LLMSettings)
    session: SessionSettings = field(default_factory=SessionSettings)
    tools: ToolSettings = field(default_factory=ToolSettings)
    agent: AgentSettings = field(default_factory=AgentSettings)
    ui: UISettings = field(default_factory=UISettings)

    @classmethod
    def from_file(cls, path: Path) -> "Settings":
        data = toml.loads(path.read_text())
        settings = cls()
        if "llm" in data:
            for k, v in data["llm"].items():
                if hasattr(settings.llm, k):
                    setattr(settings.llm, k, v)
        if "session" in data:
            for k, v in data["session"].items():
                if hasattr(settings.session, k):
                    setattr(settings.session, k, v)
        if "tools" in data:
            for k, v in data["tools"].items():
                if hasattr(settings.tools, k):
                    setattr(settings.tools, k, v)
        if "agent" in data:
            for k, v in data["agent"].items():
                if hasattr(settings.agent, k):
                    setattr(settings.agent, k, v)
        if "ui" in data:
            for k, v in data["ui"].items():
                if hasattr(settings.ui, k):
                    setattr(settings.ui, k, v)
        return settings
