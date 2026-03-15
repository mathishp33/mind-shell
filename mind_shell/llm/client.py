"""
mind_shell/llm/client.py — Unified LLM client.

Supports multiple providers:
  - Anthropic Claude (default)
  - OpenAI GPT-4
  - Ollama (local models)

Features:
  - Streaming support
  - Tool use (function calling) loop
  - Usage tracking
  - Provider-agnostic response handling
"""

from __future__ import annotations

import os
import json
import asyncio
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
    id: Optional[str] = None  # For OpenAI compatibility


@dataclass
class LLMResponse:
    text: str
    model: str
    usage: UsageStats = field(default_factory=UsageStats)
    tool_calls: List[ToolCall] = field(default_factory=list)
    stop_reason: str = "end_turn"


class LLMClient:
    """Unified client for multiple LLM providers."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.provider = settings.llm.provider.lower()
        self._client = self._init_client()
        self.ctx_mgr = ContextManager(settings)

    def _init_client(self):
        """Initialize the appropriate LLM client based on provider."""
        if self.provider == "anthropic":
            return self._init_anthropic()
        elif self.provider == "openai":
            return self._init_openai()
        elif self.provider == "ollama":
            return self._init_ollama()
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def _init_anthropic(self):
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

    def _init_openai(self):
        try:
            from openai import OpenAI
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError(
                    "OPENAI_API_KEY environment variable not set.\n"
                    "Get your key at https://platform.openai.com/api-keys"
                )
            return OpenAI(api_key=api_key)
        except ImportError:
            raise ImportError("openai package not installed. Run: pip install openai")

    def _init_ollama(self):
        try:
            import httpx
            base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            # Just return the base URL, we'll use httpx for requests
            return base_url
        except ImportError:
            raise ImportError("httpx package is required for Ollama. Run: pip install httpx")

    def _convert_tools_to_openai(self, tools: List[BaseTool]) -> List[dict]:
        """Convert BaseTool instances to OpenAI function calling format."""
        openai_tools = []
        for tool in tools:
            schema = tool.to_api_schema()
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": schema["name"],
                    "description": schema["description"],
                    "parameters": schema.get("input_schema", {})
                }
            })
        return openai_tools

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
        tool_map = {t.name: t for t in tools}

        if system is None:
            system = self.ctx_mgr.build_system()

        all_tool_calls: List[ToolCall] = []
        total_usage = UsageStats()
        current_messages = list(messages)
        final_text = ""

        while True:
            # Prepare provider-specific parameters and get response
            if self.provider == "anthropic":
                text, stop_reason, usage, raw_tool_calls = await self._chat_anthropic(
                    current_messages, tools, system, stream, on_text
                )
            elif self.provider == "openai":
                text, stop_reason, usage, raw_tool_calls = await self._chat_openai(
                    current_messages, tools, system, stream, on_text
                )
            elif self.provider == "ollama":
                text, stop_reason, usage, raw_tool_calls = await self._chat_ollama(
                    current_messages, tools, system, stream, on_text
                )

            total_usage.input_tokens += usage.input_tokens
            total_usage.output_tokens += usage.output_tokens
            final_text = text if text else final_text

            # Check if we should continue tool loop
            if stop_reason != "tool_use" or not raw_tool_calls:
                break

            # Execute tool calls
            tool_results = []
            for tool_call_data in raw_tool_calls:
                tool_name = tool_call_data["name"]
                tool_input = tool_call_data["input"]
                tool_id = tool_call_data.get("id")

                tc = ToolCall(name=tool_name, input=tool_input, id=tool_id)

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
                    "tool_name": tool_name,
                    "tool_id": tool_id,
                    "result": tc.result,
                })

            # Add tool results to message history (provider-specific format)
            current_messages = self._add_tool_results(
                current_messages, text, raw_tool_calls, tool_results
            )

        return LLMResponse(
            text=final_text,
            model=self.settings.llm.model,
            usage=total_usage,
            tool_calls=all_tool_calls,
            stop_reason=stop_reason,
        )

    async def _chat_anthropic(
        self,
        messages: List[dict],
        tools: List[BaseTool],
        system: str,
        stream: bool,
        on_text: Optional[callable],
    ) -> tuple:
        """Anthropic-specific chat implementation."""
        tool_schemas = [t.to_api_schema() for t in tools]

        kwargs = dict(
            model=self.settings.llm.model,
            max_tokens=self.settings.llm.max_tokens,
            system=system,
            messages=messages,
        )
        if tool_schemas:
            kwargs["tools"] = tool_schemas

        if stream and on_text:
            text, stop_reason, usage, raw_tool_uses = await self._stream_anthropic(
                kwargs, on_text
            )
        else:
            text, stop_reason, usage, raw_tool_uses = await self._complete_anthropic(kwargs)

        # Convert Anthropic tool use format to unified format
        tool_calls = [
            {"name": tu.name, "input": tu.input, "id": tu.id}
            for tu in raw_tool_uses
        ]

        return text, stop_reason, usage, tool_calls

    async def _complete_anthropic(self, kwargs: dict):
        """Non-streaming Anthropic completion."""
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

    async def _stream_anthropic(self, kwargs: dict, on_text: callable):
        """Streaming Anthropic completion."""
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
                                    asyncio.run_coroutine_threadsafe(
                                        on_text(chunk),
                                        asyncio.get_event_loop()
                                    )
                                elif event.delta.type == "input_json_delta":
                                    current_tool_json += event.delta.partial_json
                        elif event.type == "content_block_stop":
                            if current_tool is not None:
                                try:
                                    current_tool.input = json.loads(current_tool_json)
                                except Exception:
                                    current_tool.input = {}
                                tool_uses.append(current_tool)
                                current_tool = None
                        elif event.type == "message_delta":
                            if hasattr(event, "delta") and hasattr(event.delta, "stop_reason"):
                                stop_reason = event.delta.stop_reason or "end_turn"

            final = stream.get_final_message()
            output_tokens = final.usage.output_tokens
            stop_reason = final.stop_reason

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _do_stream)

        usage = UsageStats(input_tokens=input_tokens, output_tokens=output_tokens)
        return "".join(text_parts), stop_reason, usage, tool_uses

    # ═════════════════════════════════════════════════════════════════════════
    # OpenAI implementations
    # ═════════════════════════════════════════════════════════════════════════

    async def _chat_openai(
        self,
        messages: List[dict],
        tools: List[BaseTool],
        system: str,
        stream: bool,
        on_text: Optional[callable],
    ) -> tuple:
        """OpenAI-specific chat implementation."""
        tools_openai = self._convert_tools_to_openai(tools) if tools else None

        # Prepend system message to messages
        all_messages = messages.copy()
        if system:
            all_messages.insert(0, {"role": "system", "content": system})

        kwargs = dict(
            model=self.settings.llm.model,
            messages=all_messages,
            temperature=self.settings.llm.temperature,
            max_tokens=self.settings.llm.max_tokens,
        )
        if tools_openai:
            kwargs["tools"] = tools_openai
            kwargs["tool_choice"] = "auto"

        if stream and on_text:
            text, stop_reason, usage, tool_calls = await self._stream_openai(
                kwargs, on_text
            )
        else:
            text, stop_reason, usage, tool_calls = await self._complete_openai(kwargs)

        return text, stop_reason, usage, tool_calls

    async def _complete_openai(self, kwargs: dict):
        """Non-streaming OpenAI completion."""
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self._client.chat.completions.create(**kwargs)
        )

        text = ""
        tool_calls = []

        for choice in response.choices:
            if choice.message.content:
                text += choice.message.content

            if choice.message.tool_calls:
                for tc in choice.message.tool_calls:
                    tool_input = json.loads(tc.function.arguments)
                    tool_calls.append({
                        "name": tc.function.name,
                        "input": tool_input,
                        "id": tc.id
                    })

        usage = UsageStats(
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
        )

        stop_reason = "tool_use" if tool_calls else "end_turn"
        return text, stop_reason, usage, tool_calls

    async def _stream_openai(self, kwargs: dict, on_text: callable):
        """Streaming OpenAI completion."""
        text_parts = []
        tool_calls = []
        stop_reason = "end_turn"
        input_tokens = 0
        output_tokens = 0

        def _do_stream():
            nonlocal stop_reason, input_tokens, output_tokens
            with self._client.chat.completions.create(stream=True, **kwargs) as stream:
                for chunk in stream:
                    if chunk.choices:
                        choice = chunk.choices[0]

                        if choice.delta.content:
                            text_parts.append(choice.delta.content)
                            asyncio.run_coroutine_threadsafe(
                                on_text(choice.delta.content),
                                asyncio.get_event_loop()
                            )

                        if choice.delta.tool_calls:
                            for tc in choice.delta.tool_calls:
                                tool_calls.append(tc)

                        if choice.finish_reason:
                            stop_reason = "tool_use" if tool_calls else choice.finish_reason

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _do_stream)

        usage = UsageStats(input_tokens=input_tokens, output_tokens=output_tokens)
        return "".join(text_parts), stop_reason, usage, tool_calls

    # ═════════════════════════════════════════════════════════════════════════
    # Ollama implementations
    # ═════════════════════════════════════════════════════════════════════════

    async def _chat_ollama(
        self,
        messages: List[dict],
        tools: List[BaseTool],
        system: str,
        stream: bool,
        on_text: Optional[callable],
    ) -> tuple:
        """Ollama-specific chat implementation (local models)."""
        # Ollama doesn't have native tool support, so we encode tools in system prompt
        enhanced_system = self._build_ollama_system(system, tools)

        if stream and on_text:
            text, stop_reason, usage = await self._stream_ollama(
                messages, enhanced_system, on_text
            )
        else:
            text, stop_reason, usage = await self._complete_ollama(
                messages, enhanced_system
            )

        # Ollama doesn't support tool calling
        return text, stop_reason, usage, []

    async def _complete_ollama(self, messages: List[dict], system: str):
        """Non-streaming Ollama completion."""
        import httpx

        base_url = self._client
        all_messages = messages.copy()
        if system:
            all_messages.insert(0, {"role": "system", "content": system})

        payload = {
            "model": self.settings.llm.model,
            "messages": all_messages,
            "stream": False,
        }

        loop = asyncio.get_event_loop()

        def _do_request():
            with httpx.Client(timeout=None) as client:
                response = client.post(
                    f"{base_url}/api/chat",
                    json=payload
                )
                response.raise_for_status()
                return response.json()

        response = await loop.run_in_executor(None, _do_request)

        text = response.get("message", {}).get("content", "")
        usage = UsageStats()  # Ollama doesn't return token counts

        return text, "end_turn", usage

    async def _stream_ollama(
        self,
        messages: List[dict],
        system: str,
        on_text: callable
    ):
        """Streaming Ollama completion."""
        import httpx

        base_url = self._client
        all_messages = messages.copy()
        if system:
            all_messages.insert(0, {"role": "system", "content": system})

        payload = {
            "model": self.settings.llm.model,
            "messages": all_messages,
            "stream": True,
        }

        text_parts = []

        def _do_stream():
            with httpx.Client(timeout=None) as client:
                with client.stream("POST", f"{base_url}/api/chat", json=payload) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if line:
                            chunk = json.loads(line)
                            if "message" in chunk and "content" in chunk["message"]:
                                content = chunk["message"]["content"]
                                text_parts.append(content)
                                asyncio.run_coroutine_threadsafe(
                                    on_text(content),
                                    asyncio.get_event_loop()
                                )

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _do_stream)

        usage = UsageStats()  # Ollama doesn't return token counts
        return "".join(text_parts), "end_turn", usage

    def _build_ollama_system(self, system: str, tools: List[BaseTool]) -> str:
        """Build enhanced system prompt that includes tool descriptions for Ollama."""
        if not tools:
            return system

        tool_descriptions = "\n\n".join([
            f"Tool: {tool.name}\nDescription: {tool.description}"
            for tool in tools
        ])

        return f"""{system}

## Available Tools

{tool_descriptions}

Note: You cannot execute these tools directly. Instead, describe what action you would take."""

    def _add_tool_results(
        self,
        messages: List[dict],
        assistant_text: str,
        raw_tool_calls: List[dict],
        tool_results: List[dict],
    ) -> List[dict]:
        """Add tool results to message history in provider-specific format."""
        if self.provider == "anthropic":
            return self._add_tool_results_anthropic(
                messages, assistant_text, raw_tool_calls, tool_results
            )
        elif self.provider == "openai":
            return self._add_tool_results_openai(
                messages, assistant_text, raw_tool_calls, tool_results
            )
        else:
            return messages

    def _add_tool_results_anthropic(
        self,
        messages: List[dict],
        assistant_text: str,
        raw_tool_calls: List[dict],
        tool_results: List[dict],
    ) -> List[dict]:
        """Add tool results in Anthropic format."""
        content = []
        if assistant_text:
            content.append({"type": "text", "text": assistant_text})

        for tc in raw_tool_calls:
            content.append({
                "type": "tool_use",
                "id": tc["id"],
                "name": tc["name"],
                "input": tc["input"],
            })

        messages.append({"role": "assistant", "content": content})

        tool_results_content = [
            {
                "type": "tool_result",
                "tool_use_id": tr["tool_id"],
                "content": tr["result"],
            }
            for tr in tool_results
        ]

        messages.append({"role": "user", "content": tool_results_content})
        return messages

    def _add_tool_results_openai(
        self,
        messages: List[dict],
        assistant_text: str,
        raw_tool_calls: List[dict],
        tool_results: List[dict],
    ) -> List[dict]:
        """Add tool results in OpenAI format."""
        # Add assistant message with tool calls
        tool_calls = [
            {
                "id": tc["id"],
                "type": "function",
                "function": {
                    "name": tc["name"],
                    "arguments": json.dumps(tc["input"])
                }
            }
            for tc in raw_tool_calls
        ]

        assistant_msg = {"role": "assistant", "content": assistant_text or ""}
        if tool_calls:
            assistant_msg["tool_calls"] = tool_calls

        messages.append(assistant_msg)

        # Add tool results
        for tr in tool_results:
            messages.append({
                "role": "tool",
                "tool_call_id": tr["tool_id"],
                "content": tr["result"],
            })

        return messages
