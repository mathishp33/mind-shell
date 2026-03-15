"""
nexus/ui/chat.py — Interactive chat interface.

Features:
  - Streaming response with Rich Markdown rendering
  - Multi-line input via prompt-toolkit
  - Session auto-save
  - Slash commands (/help, /exit, /export, /clear, /session, /tools)
  - Tool call visualization
"""

from __future__ import annotations

import asyncio
from typing import List, Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from mind_shell.config.settings import Settings
from mind_shell.core.context import ContextManager
from mind_shell.core.session import Session, SessionManager
from mind_shell.llm.client import LLMClient, LLMResponse
from mind_shell.tools.base_tool import BaseTool

console = Console()


WELCOME_BANNER = """
[bold cyan]╔═══════════════════════════════════╗[/bold cyan]
[bold cyan]║      NEXUS CLI  ·  v0.1.0         ║[/bold cyan]
[bold cyan]╚═══════════════════════════════════╝[/bold cyan]

Type your message to start chatting.
[dim]Commands: /help · /export · /session · /tools · /clear · /exit[/dim]
"""

HELP_TEXT = """
## Nexus Commands

| Command | Description |
|---------|-------------|
| `/help` | Show this help message |
| `/exit` or `/quit` | Exit Nexus |
| `/clear` | Clear the screen |
| `/export [md\|json]` | Export this session |
| `/session` | Show session info |
| `/tools` | List enabled tools |
| `/model <name>` | Switch model |

**Tips:**
- Use `@filename` to include a file in your message
- Paste multi-line code — just press Enter twice to send
- Sessions auto-save after each message
"""


class ChatUI:
    """Interactive terminal chat interface for Nexus."""

    def __init__(
        self,
        settings: Settings,
        llm: LLMClient,
        tools: List[BaseTool],
        session_mgr: SessionManager,
        ctx_mgr: ContextManager,
        verbose: bool = False,
    ):
        self.settings = settings
        self.llm = llm
        self.tools = tools
        self.session_mgr = session_mgr
        self.ctx_mgr = ctx_mgr
        self.verbose = verbose
        self.session: Optional[Session] = None

        # Set up prompt-toolkit with history
        history_path = settings.session.save_path / ".prompt_history"
        self.prompt_session = PromptSession(
            history=FileHistory(str(history_path)),
            auto_suggest=AutoSuggestFromHistory(),
            multiline=False,
        )

    def resume_session(self, session_id: str) -> None:
        self.session = self.session_mgr.load(session_id)
        if self.session:
            console.print(f"[green]Resumed session {session_id[:8]}[/green]")
        else:
            console.print(f"[yellow]Session {session_id} not found. Starting new session.[/yellow]")

    def run(self) -> None:
        """Main loop for interactive chat."""
        if self.session is None:
            self.session = self.session_mgr.new()

        console.print(WELCOME_BANNER)
        console.print(
            f"[dim]Session: {self.session.id[:8]} · "
            f"Model: {self.settings.llm.model} · "
            f"Tools: {len(self.tools)} enabled[/dim]\n"
        )

        while True:
            try:
                user_input = self._get_input()
                if not user_input:
                    continue
                if user_input.startswith("/"):
                    should_exit = self._handle_command(user_input)
                    if should_exit:
                        break
                    continue
                asyncio.run(self._handle_message(user_input))
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Interrupted. Use /exit to quit.[/dim]")
                break

        if self.session and self.settings.session.auto_save:
            path = self.session_mgr.save(self.session)
            console.print(f"\n[dim]Session saved: {path}[/dim]")

    def _get_input(self) -> str:
        """Prompt for user input with styled prompt."""
        try:
            return self.prompt_session.prompt(
                HTML("<ansigreen><b>you</b></ansigreen> › "),
                default="",
            ).strip()
        except (KeyboardInterrupt, EOFError):
            raise

    async def _handle_message(self, user_input: str) -> None:
        """Process a user message: expand @files, send to LLM, render response."""
        # Expand @file references
        expanded = self._expand_file_refs(user_input)

        self.session.add_turn("user", user_input)

        # Build context and call LLM
        messages = self.ctx_mgr.build(self.session, expanded)

        console.print()
        console.print("[bold cyan]nexus[/bold cyan] › ", end="")

        response_parts: List[str] = []

        async def on_text(chunk: str):
            print(chunk, end="", flush=True)
            response_parts.append(chunk)

        async def on_tool_call(tc):
            if self.settings.ui.show_tool_calls or self.verbose:
                console.print(
                    f"\n\n[yellow]🔧 {tc.name}[/yellow] [dim]{str(tc.input)[:100]}[/dim]"
                )

        response: LLMResponse = await self.llm.chat(
            messages=messages,
            tools=self.tools,
            stream=True,
            on_text=on_text,
            on_tool_call=on_tool_call,
        )

        full_text = "".join(response_parts)
        print()  # newline after streaming

        # Re-render as Markdown if enabled
        if self.settings.ui.markdown_render and full_text:
            console.print()
            console.print(Markdown(full_text))

        # Show token count if enabled
        if self.settings.ui.show_token_count:
            console.print(
                f"[dim]↑{response.usage.input_tokens} ↓{response.usage.output_tokens} tokens[/dim]"
            )

        # Save to session
        self.session.add_turn("assistant", full_text)
        for tc in response.tool_calls:
            self.session.add_turn("tool", tc.result or "", tool_name=tc.name,
                                   tool_input=str(tc.input))

        # Auto-save
        if self.settings.session.auto_save:
            self.session_mgr.save(self.session)

        console.print()

    def _expand_file_refs(self, text: str) -> str:
        """Replace @filename references with file contents."""
        import re
        from pathlib import Path

        def replace_ref(match):
            filepath = Path(match.group(1))
            if filepath.exists() and filepath.is_file():
                try:
                    content = filepath.read_text(encoding="utf-8", errors="replace")
                    return f"\n\n[File: {filepath}]\n```\n{content[:4000]}\n```"
                except Exception:
                    return match.group(0)
            return match.group(0)

        return re.sub(r"@([\w./\-]+)", replace_ref, text)

    def _handle_command(self, cmd: str) -> bool:
        """Handle slash commands. Returns True if should exit."""
        parts = cmd.split()
        command = parts[0].lower()

        if command in ("/exit", "/quit", "/q"):
            return True

        elif command == "/help":
            console.print(Markdown(HELP_TEXT))

        elif command == "/clear":
            console.clear()

        elif command == "/tools":
            if not self.tools:
                console.print("[yellow]No tools enabled.[/yellow]")
            else:
                console.print("[bold]Enabled tools:[/bold]")
                for t in self.tools:
                    console.print(f"  [cyan]{t.name}[/cyan] — {t.description[:60]}…")

        elif command == "/session":
            if self.session:
                console.print(
                    Panel(
                        f"ID: [cyan]{self.session.id}[/cyan]\n"
                        f"Created: {self.session.created_at_str}\n"
                        f"Messages: {self.session.message_count}\n"
                        f"Model: {self.session.model}",
                        title="Session Info",
                        border_style="dim",
                    )
                )

        elif command == "/export":
            fmt = parts[1] if len(parts) > 1 else "md"
            if self.session:
                from pathlib import Path
                if fmt == "json":
                    content = self.session.to_json()
                    suffix = ".json"
                else:
                    content = self.session.to_markdown()
                    suffix = ".md"
                dest = Path(f"nexus-export-{self.session.id[:8]}{suffix}")
                dest.write_text(content, encoding="utf-8")
                console.print(f"[green]✅ Exported to {dest}[/green]")

        elif command == "/model":
            if len(parts) > 1:
                self.settings.llm.model = parts[1]
                console.print(f"[green]Model set to: {parts[1]}[/green]")
            else:
                console.print(f"Current model: [cyan]{self.settings.llm.model}[/cyan]")

        else:
            console.print(f"[yellow]Unknown command: {command}. Type /help for help.[/yellow]")

        return False
