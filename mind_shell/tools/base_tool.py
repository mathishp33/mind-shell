"""
nexus/tools/base_tool.py — Abstract base class for all Nexus tools.

Every tool must implement:
  - name: str
  - description: str
  - input_schema: dict   (JSON Schema for the tool's parameters)
  - execute(input: dict) -> str

Tools are automatically converted to Anthropic's tool format via .to_api_schema().
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class ToolResult:
    """Structured result from a tool execution."""
    output: str
    success: bool = True
    error: Optional[str] = None

    def __str__(self) -> str:
        if not self.success:
            return f"Error: {self.error}"
        return self.output


class BaseTool(ABC):
    """Base class for all Nexus tools."""

    # Override in subclasses
    name: str = ""
    description: str = ""
    input_schema: Dict[str, Any] = {}

    def to_api_schema(self) -> dict:
        """Convert to Anthropic tool definition format."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }

    @abstractmethod
    async def execute(self, tool_input: dict) -> ToolResult:
        """Execute the tool with the given input dict."""
        ...

    def __repr__(self) -> str:
        return f"<Tool: {self.name}>"
