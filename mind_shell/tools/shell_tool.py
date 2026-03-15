"""
nexus/tools/shell_tool.py — Shell command execution tool.

Executes arbitrary shell commands with a configurable confirmation step.
In YOLO mode, commands execute without confirmation.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
from typing import Optional

from mind_shell.tools.base_tool import BaseTool, ToolResult


BLOCKED_PATTERNS = [
    "rm -rf /",
    "mkfs",
    "dd if=",
    "> /dev/",
    ":(){ :|:& };:",  # fork bomb
]


class ShellTool(BaseTool):
    name = "shell"
    description = (
        "Execute shell commands (bash). Use to run scripts, tests, linters, "
        "build tools, package managers, or any CLI command."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to execute.",
            },
            "cwd": {
                "type": "string",
                "description": "Working directory for the command (default: current directory).",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds (default: 30).",
                "default": 30,
            },
            "env": {
                "type": "object",
                "description": "Extra environment variables to set.",
                "additionalProperties": {"type": "string"},
            },
        },
        "required": ["command"],
    }

    def __init__(self, confirm: bool = True, timeout: int = 30, yolo: bool = False):
        self.confirm = confirm and not yolo
        self.default_timeout = timeout

    async def execute(self, tool_input: dict) -> ToolResult:
        command = tool_input.get("command", "").strip()
        cwd = tool_input.get("cwd", None)
        timeout = tool_input.get("timeout", self.default_timeout)
        extra_env = tool_input.get("env", {})

        if not command:
            return ToolResult(output="", success=False, error="Command is empty.")

        # Safety check
        for blocked in BLOCKED_PATTERNS:
            if blocked in command:
                return ToolResult(
                    output="",
                    success=False,
                    error=f"Command contains blocked pattern: '{blocked}'",
                )

        # Confirmation prompt (when not in YOLO mode)
        if self.confirm:
            confirmed = await self._confirm(command)
            if not confirmed:
                return ToolResult(output="Command cancelled by user.", success=True)

        # Build env
        env = os.environ.copy()
        env.update(extra_env)

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

            out = stdout.decode("utf-8", errors="replace")
            err = stderr.decode("utf-8", errors="replace")

            lines = [f"$ {command}", f"Exit code: {proc.returncode}"]
            if out:
                lines.append(f"\n**stdout:**\n```\n{out[:4000]}\n```")
            if err:
                lines.append(f"\n**stderr:**\n```\n{err[:2000]}\n```")

            success = proc.returncode == 0
            return ToolResult(output="\n".join(lines), success=success)

        except asyncio.TimeoutError:
            return ToolResult(
                output=f"$ {command}\n\nCommand timed out after {timeout}s",
                success=False,
                error="Timeout",
            )
        except Exception as e:
            return ToolResult(output="", success=False, error=str(e))

    async def _confirm(self, command: str) -> bool:
        """
        Prompt the user to confirm a shell command.
        In a non-interactive/CI context, defaults to True.
        """
        import sys
        if not sys.stdin.isatty():
            return True  # Non-interactive: allow

        from rich.console import Console
        from rich.prompt import Confirm
        console = Console()
        console.print(f"\n[yellow]⚡ Shell command:[/yellow] [bold]{command}[/bold]")
        return Confirm.ask("Execute?", default=False)
