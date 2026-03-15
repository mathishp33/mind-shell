"""
nexus/llm/client.py — Unified LLM client.

Wraps the Anthropic API with:
  - Streaming support
  - Tool use (function calling) loop
  - Usage tracking
  - Response dataclass
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional, Any

from mind_shell.config.settings import Settings
from mind_shell.tools.base_tool import BaseTool, ToolResult
from mind_shell.core.context import ContextManager


@dataclass
class UsageStats:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class ToolCall:
    name: str
    input: dict
    result: Optional[str] = None


@dataclass
class LLMResponse:
    text: str
    model: str
    usage: UsageStats = field(default_factory=UsageStats)
    tool_calls: List[ToolCall] = field(default_factory=list)
    stop_reason: str = "end_turn"


class LLMClient:
    """Client for Anthropic Claude with streaming and tool use."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = self._init_client()
        self.ctx_mgr = ContextManager(settings)

    def _init_client(self):
        try:
            import anthropic
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError(
                    "ANTHROPIC_API_KEY environment variable not set.\n"
                    "Get your key at https://console.anthropic.com/"
                )
            return anthropic.Anthropic(api_key=api_key)
        except ImportError:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")

    async def chat(
        self,
        messages: List[dict],
        tools: List[BaseTool] = None,
        stream: bool = True,
        system: Optional[str] = None,
        on_text: Optional[callable] = None,
        on_tool_call: Optional[callable] = None,
    ) -> LLMResponse:
        """
        Send messages to the LLM and return the full response.

        Handles multi-step tool use automatically:
        1. LLM requests a tool call
        2. We execute the tool
        3. Return the result to the LLM
        4. Repeat until stop_reason == "end_turn"
        """
        tools = tools or []
        tool_schemas = [t.to_api_schema() for t in tools]
        tool_map = {t.name: t for t in tools}

        if system is None:
            system = self.ctx_mgr.build_system()

        all_tool_calls: List[ToolCall] = []
        total_usage = UsageStats()
        current_messages = list(messages)
        final_text = ""

        while True:
            kwargs = dict(
                model=self.settings.llm.model,
                max_tokens=self.settings.llm.max_tokens,
                system=system,
                messages=current_messages,
            )
            if tool_schemas:
                kwargs["tools"] = tool_schemas

            if stream and on_text:
                text, stop_reason, usage, raw_tool_uses = await self._stream(
                    kwargs, on_text
                )
            else:
                text, stop_reason, usage, raw_tool_uses = await self._complete(kwargs)

            total_usage.input_tokens += usage.input_tokens
            total_usage.output_tokens += usage.output_tokens
            final_text = text if text else final_text

            if stop_reason != "tool_use" or not raw_tool_uses:
                break

            # Execute tool calls
            tool_results = []
            for tool_use in raw_tool_uses:
                tool_name = tool_use.name
                tool_input = tool_use.input

                tc = ToolCall(name=tool_name, input=tool_input)

                if on_tool_call:
                    await on_tool_call(tc)

                tool = tool_map.get(tool_name)
                if tool:
                    result: ToolResult = await tool.execute(tool_input)
                    tc.result = str(result)
                else:
                    tc.result = f"Error: Unknown tool '{tool_name}'"

                all_tool_calls.append(tc)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": tc.result,
                })

            # Add the assistant turn + tool results to messages
            current_messages.append({
                "role": "assistant",
                "content": self._build_assistant_content(text, raw_tool_uses),
            })
            current_messages.append({
                "role": "user",
                "content": tool_results,
            })

        return LLMResponse(
            text=final_text,
            model=self.settings.llm.model,
            usage=total_usage,
            tool_calls=all_tool_calls,
            stop_reason=stop_reason,
        )

    async def _complete(self, kwargs: dict):
        """Non-streaming completion."""
        import asyncio
        import anthropic

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self._client.messages.create(**kwargs)
        )

        text = ""
        tool_uses = []
        for block in response.content:
            if block.type == "text":
                text += block.text
            elif block.type == "tool_use":
                tool_uses.append(block)

        usage = UsageStats(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
        return text, response.stop_reason, usage, tool_uses

    async def _stream(self, kwargs: dict, on_text: callable):
        """Streaming completion — calls on_text for each text chunk."""
        import asyncio
        import anthropic

        text_parts = []
        tool_uses = []
        stop_reason = "end_turn"
        input_tokens = 0
        output_tokens = 0

        def _do_stream():
            nonlocal stop_reason, input_tokens, output_tokens
            with self._client.messages.stream(**kwargs) as stream:
                current_tool = None
                current_tool_json = ""

                for event in stream:
                    if hasattr(event, "type"):
                        if event.type == "content_block_start":
                            if hasattr(event.content_block, "type"):
                                if event.content_block.type == "tool_use":
                                    current_tool = event.content_block
                                    current_tool_json = ""
                        elif event.type == "content_block_delta":
                            if hasattr(event.delta, "type"):
                                if event.delta.type == "text_delta":
                                    chunk = event.delta.text
                                    text_parts.append(chunk)
                                    # Call on_text synchronously here; we handle async outside
                                    asyncio.run_coroutine_threadsafe(
                                        on_text(chunk),
                                        asyncio.get_event_loop()
                                    )
                                elif event.delta.type == "input_json_delta":
                                    current_tool_json += event.delta.partial_json
                        elif event.type == "content_block_stop":
                            if current_tool is not None:
                                import json
                                try:
                                    current_tool.input = json.loads(current_tool_json)
                                except Exception:
                                    current_tool.input = {}
                                tool_uses.append(current_tool)
                                current_tool = None
                        elif event.type == "message_delta":
                            if hasattr(event, "delta") and hasattr(event.delta, "stop_reason"):
                                stop_reason = event.delta.stop_reason or "end_turn"
                        elif event.type == "message_start":
                            if hasattr(event, "message") and hasattr(event.message, "usage"):
                                input_tokens = event.message.usage.input_tokens

            final = stream.get_final_message()
            output_tokens = final.usage.output_tokens
            stop_reason = final.stop_reason

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _do_stream)

        usage = UsageStats(input_tokens=input_tokens, output_tokens=output_tokens)
        return "".join(text_parts), stop_reason, usage, tool_uses

    def _build_assistant_content(self, text: str, tool_uses: list) -> list:
        content = []
        if text:
            content.append({"type": "text", "text": text})
        for tu in tool_uses:
            content.append({
                "type": "tool_use",
                "id": tu.id,
                "name": tu.name,
                "input": tu.input,
            })
        return content
