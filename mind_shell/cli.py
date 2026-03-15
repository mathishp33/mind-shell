"""
nexus/cli.py — Main entry point for Nexus CLI.

Usage:
    nexus chat                         # Interactive chat mode
    nexus --prompt "your question"     # Script / CI mode (non-interactive)
    nexus agent "do something complex" # Autonomous agent mode
    nexus session list                 # Manage sessions
    nexus session resume <id>          # Resume a previous session
    nexus export --format md           # Export current chat
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from mind_shell.core.session import SessionManager
from mind_shell.core.context import ContextManager
from mind_shell.core.agent import AgentMode
from mind_shell.llm.client import LLMClient
from mind_shell.tools import get_all_tools
from mind_shell.ui.chat import ChatUI
from mind_shell.config.settings import Settings

app = typer.Typer(
    name="nexus",
    help="🧠 Nexus — Your AI assistant for the terminal",
    rich_markup_mode="rich",
    no_args_is_help=True,
)

session_app = typer.Typer(help="Manage chat sessions")
app.add_typer(session_app, name="session")

console = Console()


def _load_settings() -> Settings:
    """Load settings from nexus.toml (local > ~/.config/nexus/)."""
    local = Path("nexus.toml")
    global_cfg = Path.home() / ".config" / "nexus" / "nexus.toml"
    if local.exists():
        return Settings.from_file(local)
    if global_cfg.exists():
        return Settings.from_file(global_cfg)
    return Settings()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    prompt: Optional[str] = typer.Option(
        None, "--prompt", "-p",
        help="Run a single prompt (non-interactive, for scripts/CI)"
    ),
    session_id: Optional[str] = typer.Option(
        None, "--session", "-s",
        help="Resume an existing session by ID"
    ),
    model: Optional[str] = typer.Option(
        None, "--model", "-m",
        help="Override the LLM model for this run"
    ),
    json_output: bool = typer.Option(
        False, "--json",
        help="Output response as JSON (useful for CI pipelines)"
    ),
    no_tools: bool = typer.Option(
        False, "--no-tools",
        help="Disable all tools (pure conversation)"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v",
        help="Show tool calls and internal steps"
    ),
):
    """
    [bold cyan]Nexus CLI[/bold cyan] — AI assistant for the terminal.

    Run [green]nexus chat[/green] for an interactive session.
    Run [green]nexus --prompt "question"[/green] for one-shot script usage.
    """
    if ctx.invoked_subcommand is not None:
        return

    settings = _load_settings()
    if model:
        settings.llm.model = model

    llm = LLMClient(settings)
    tools = [] if no_tools else get_all_tools(settings)
    session_mgr = SessionManager(settings)
    ctx_mgr = ContextManager(settings)

    # ── Script / CI mode ─────────────────────────────────────────────────────
    if prompt:
        _run_prompt_mode(
            prompt=prompt,
            settings=settings,
            llm=llm,
            tools=tools,
            session_mgr=session_mgr,
            ctx_mgr=ctx_mgr,
            session_id=session_id,
            json_output=json_output,
            verbose=verbose,
        )
        return

    # ── Interactive chat mode ─────────────────────────────────────────────────
    chat_ui = ChatUI(
        settings=settings,
        llm=llm,
        tools=tools,
        session_mgr=session_mgr,
        ctx_mgr=ctx_mgr,
        verbose=verbose,
    )
    if session_id:
        chat_ui.resume_session(session_id)
    chat_ui.run()


def _run_prompt_mode(
    prompt: str,
    settings: Settings,
    llm: LLMClient,
    tools: list,
    session_mgr: SessionManager,
    ctx_mgr: ContextManager,
    session_id: Optional[str],
    json_output: bool,
    verbose: bool,
) -> None:
    """Non-interactive single-shot mode for scripts and CI pipelines."""
    import asyncio
    import json as _json

    session = session_mgr.load(session_id) if session_id else session_mgr.new()

    async def _run():
        response = await llm.chat(
            messages=ctx_mgr.build(session, prompt),
            tools=tools,
            stream=not json_output,
        )
        session.add_turn("user", prompt)
        session.add_turn("assistant", response.text)
        session_mgr.save(session)
        return response

    response = asyncio.run(_run())

    if json_output:
        out = {
            "session_id": session.id,
            "response": response.text,
            "model": response.model,
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "tools_used": [t.name for t in response.tool_calls],
        }
        console.print_json(_json.dumps(out))
    else:
        from rich.markdown import Markdown
        console.print(Markdown(response.text))

    sys.exit(0)


# ── chat subcommand ───────────────────────────────────────────────────────────

@app.command()
def chat(
    session_id: Optional[str] = typer.Argument(None, help="Session ID to resume"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Start an interactive chat session."""
    settings = _load_settings()
    llm = LLMClient(settings)
    tools = get_all_tools(settings)
    session_mgr = SessionManager(settings)
    ctx_mgr = ContextManager(settings)

    chat_ui = ChatUI(
        settings=settings,
        llm=llm,
        tools=tools,
        session_mgr=session_mgr,
        ctx_mgr=ctx_mgr,
        verbose=verbose,
    )
    if session_id:
        chat_ui.resume_session(session_id)
    chat_ui.run()
