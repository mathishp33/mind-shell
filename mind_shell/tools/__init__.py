"""
mind_shell/tools/__init__.py — Tool registry.

Returns the list of enabled tools based on settings.
"""

from __future__ import annotations

from typing import List

from mind_shell.config.settings import Settings
from mind_shell.tools.base_tool import BaseTool


def get_all_tools(settings: Settings) -> List[BaseTool]:
    """Instantiate and return all enabled tools."""
    enabled = set(settings.tools.enabled)
    tools: List[BaseTool] = []

    if "filesystem" in enabled:
        from mind_shell.tools.file_system import FilesystemTool
        tools.append(FilesystemTool(
            max_file_size=settings.tools.max_file_size_kb * 1024
        ))

    if "web_search" in enabled:
        from mind_shell.tools.web import WebSearchTool
        tools.append(WebSearchTool())

    if "web_fetch" in enabled:
        from mind_shell.tools.web import WebFetchTool
        tools.append(WebFetchTool())

    if "git" in enabled:
        from mind_shell.tools.git_tool import GitTool
        tools.append(GitTool())

    if "shell" in enabled:
        from mind_shell.tools.shell_tool import ShellTool
        tools.append(ShellTool(
            confirm=settings.tools.shell_confirm,
            timeout=settings.tools.shell_timeout,
            yolo=(settings.agent.mode == "yolo"),
        ))

    if "pdf" in enabled:
        from mind_shell.tools.media import PdfTool
        tools.append(PdfTool())

    if "image" in enabled:
        from mind_shell.tools.media import ImageTool
        tools.append(ImageTool())

    return tools


__all__ = ["get_all_tools", "BaseTool"]
