"""
nexus/core/agent.py — Autonomous agent mode.

The agent receives a high-level task, breaks it down into steps,
executes tools in sequence, and iterates until the task is complete.

Two modes:
  - confirm: Each action requires user approval before execution
  - yolo: Full automation, no prompts
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

from mind_shell.config.settings import Settings
from mind_shell.core.session import SessionManager
from mind_shell.llm.client import LLMClient, LLMResponse
from mind_shell.tools.base_tool import BaseTool

console = Console()

AGENT_SYSTEM_PROMPT = """You are Nexus, an autonomous AI agent running in the terminal.

You have been given a high-level task. Your job is to:
1. Break the task into concrete, actionable steps
2. Execute each step using the available tools
3. Adapt your plan based on intermediate results
4. Report completion with a clear summary

## Working principles

- Think step-by-step before acting
- Prefer small, reversible actions over large, destructive ones
- If you encounter an unexpected result, reassess and adapt
- Always verify the result of each action before proceeding
- When the task is complete, say "TASK_COMPLETE: <summary>"

## Response format

For each iteration, respond in this structure:
1. **Observation**: What do you know so far?
2. **Plan**: What is the next concrete step?
3. **Action**: Use a tool OR explain why you cannot proceed

When done: "TASK_COMPLETE: <brief summary of what was accomplished>"
"""


@dataclass
class AgentStep:
    step_number: int
    observation: str = ""
    plan: str = ""
    tool_calls: List[dict] = field(default_factory=list)
    result: str = ""
    approved: bool = True


class AgentMode:
    """Runs Nexus as an autonomous task-completion agent."""

    def __init__(
        self,
        settings: Settings,
        llm: LLMClient,
        tools: List[BaseTool],
        session_mgr: SessionManager,
        verbose: bool = False,
    ):
        self.settings = settings
        self.llm = llm
        self.tools = tools
        self.session_mgr = session_mgr
        self.verbose = verbose
        self.yolo = settings.agent.mode == "yolo"
        self.max_iterations = settings.agent.max_iterations

    async def run(self, task: str) -> str:
        """Run the agent on a task and return the final result."""
        session = self.session_mgr.new()
        steps: List[AgentStep] = []

        messages = [{"role": "user", "content": f"Task: {task}"}]
        session.add_turn("user", f"[Agent Task] {task}")

        for iteration in range(self.max_iterations):
            console.print(f"\n[dim]Step {iteration + 1}/{self.max_iterations}[/dim]")

            step = AgentStep(step_number=iteration + 1)

            # Stream response with tool handling
            response_parts = []

            async def on_text(chunk: str):
                console.print(chunk, end="", markup=False)
                response_parts.append(chunk)

            async def on_tool_call(tc):
                if self.settings.ui.show_tool_calls:
                    console.print(
                        Panel(
                            f"[bold]{tc.name}[/bold]\n[dim]{str(tc.input)[:200]}[/dim]",
                            title="[yellow]🔧 Tool Call[/yellow]",
                            border_style="yellow",
                        )
                    )
                if not self.yolo:
                    if not Confirm.ask(f"Execute tool [bold]{tc.name}[/bold]?", default=True):
                        tc.result = "Cancelled by user."
                        step.approved = False

            response: LLMResponse = await self.llm.chat(
                messages=messages,
                tools=self.tools,
                stream=True,
                system=AGENT_SYSTEM_PROMPT,
                on_text=on_text,
                on_tool_call=on_tool_call,
            )

            full_response = "".join(response_parts)
            step.result = full_response

            # Add to message history
            messages.append({"role": "assistant", "content": full_response})
            session.add_turn("assistant", full_response)

            # Log tool calls
            for tc in response.tool_calls:
                step.tool_calls.append({"tool": tc.name, "result": tc.result})
                session.add_turn("tool", tc.result or "", tool_name=tc.name,
                                 tool_input=str(tc.input))

            steps.append(step)

            # Check for completion
            if "TASK_COMPLETE:" in full_response:
                summary = full_response.split("TASK_COMPLETE:")[-1].strip()
                self.session_mgr.save(session)
                console.print(f"\n\n[green]✅ Task completed in {iteration + 1} steps[/green]")
                return summary

            # Check for stuck/no progress
            if not response.tool_calls and iteration > 0:
                # No tools used and no completion — ask for continuation
                messages.append({
                    "role": "user",
                    "content": "Continue with the task. If it's complete, say TASK_COMPLETE: <summary>"
                })

        # Max iterations reached
        self.session_mgr.save(session)
        return (f"Reached maximum iterations ({self.max_iterations}). "
                f"Task may be incomplete. Session saved: {session.id}")
