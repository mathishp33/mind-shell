"""
nexus/core/context.py — Context window management.

Builds the messages array sent to the LLM, ensuring we stay within
the model's context window while preserving important information.

Strategy:
  1. System prompt (always included)
  2. Session summary if history is too long
  3. Recent messages (last N turns)
  4. Current user message
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from mind_shell.config.settings import Settings
from mind_shell.core.session import Session


SYSTEM_PROMPT = """You are Nexus, a powerful AI assistant running in the terminal.

You have access to a set of tools to interact with the local filesystem, execute code, search the web, read PDFs, analyze images, interact with Git, and more.

## Guidelines

- Be concise and direct in your responses — the user is in a terminal.
- Use Markdown formatting freely — it will be rendered.
- When working with code, prefer showing diffs or targeted changes over rewriting entire files.
- Always confirm destructive operations (delete, overwrite) unless in YOLO mode.
- When using tools, explain briefly what you're doing and why.
- Prioritize correctness over speed. When unsure, ask.

## Capabilities

- Read and write files (.py, .md, .json, .txt, .toml, ...)
- Execute shell commands (with user confirmation by default)
- Search the web and fetch full page content
- Read and analyze PDFs
- Analyze images (pass the file path)
- Interact with Git (status, diff, log, commit, branch)
- Run tests, linters, formatters
- Perform deep research by combining multiple searches

## Context

Current directory: {cwd}
Git repository: {git_status}
"""


class ContextManager:
    """Builds the API messages array for each LLM call."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def build(self, session: Session, user_message: str) -> List[dict]:
        """
        Build the full messages list for an API call.

        Returns a list of dicts in Anthropic's messages format.
        """
        system = self._build_system_prompt()
        history = session.get_api_messages(self.settings.session.max_history)

        # Ensure conversation alternates correctly (user/assistant)
        # and add the new user message
        messages = self._sanitize_history(history)
        messages.append({"role": "user", "content": user_message})

        return messages

    def build_system(self) -> str:
        return self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        cwd = str(Path.cwd())
        git_status = self._get_git_status()
        return SYSTEM_PROMPT.format(cwd=cwd, git_status=git_status)

    def _get_git_status(self) -> str:
        try:
            import subprocess
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0:
                branch = result.stdout.strip()
                return f"Yes (branch: {branch})"
        except Exception:
            pass
        return "No"

    def _sanitize_history(self, history: List[dict]) -> List[dict]:
        """
        Ensure history starts with a user message and alternates correctly.
        Merge consecutive same-role messages if needed.
        """
        if not history:
            return []

        sanitized = []
        for msg in history:
            if sanitized and sanitized[-1]["role"] == msg["role"]:
                # Merge consecutive same-role messages
                sanitized[-1]["content"] += f"\n\n{msg['content']}"
            else:
                sanitized.append(dict(msg))

        # Must start with user
        while sanitized and sanitized[0]["role"] != "user":
            sanitized.pop(0)

        return sanitized
