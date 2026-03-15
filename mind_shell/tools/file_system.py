"""
mind_shell/tools/file_system.py — File system read/write tool.

Supports:
  - read_file: Read a text or binary file
  - write_file: Write content to a file
  - list_dir: List directory contents (with optional glob)
  - search_files: Search for text in files
  - file_info: Get file metadata
"""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import Optional

from mind_shell.tools.base_tool import BaseTool, ToolResult


MAX_FILE_SIZE = 512 * 1024  # 512 KB default


class FilesystemTool(BaseTool):
    name = "filesystem"
    description = (
        "Read, write, list, and search files and directories on the local machine. "
        "Use this to inspect code, edit files, read configs, or explore the project structure."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["read_file", "write_file", "list_dir", "search_files", "file_info"],
                "description": "The filesystem operation to perform.",
            },
            "path": {
                "type": "string",
                "description": "File or directory path (relative to cwd or absolute).",
            },
            "content": {
                "type": "string",
                "description": "Content to write (required for write_file).",
            },
            "pattern": {
                "type": "string",
                "description": "Glob pattern for list_dir or search pattern for search_files.",
            },
            "recursive": {
                "type": "boolean",
                "description": "Whether to recurse into subdirectories (default: false).",
                "default": False,
            },
            "encoding": {
                "type": "string",
                "description": "File encoding for read/write (default: utf-8).",
                "default": "utf-8",
            },
        },
        "required": ["action", "path"],
    }

    def __init__(self, max_file_size: int = MAX_FILE_SIZE):
        self.max_file_size = max_file_size

    async def execute(self, tool_input: dict) -> ToolResult:
        action = tool_input.get("action")
        path_str = tool_input.get("path", "")
        path = Path(path_str).expanduser()

        try:
            if action == "read_file":
                return await self._read_file(path, tool_input.get("encoding", "utf-8"))
            elif action == "write_file":
                return await self._write_file(path, tool_input.get("content", ""),
                                               tool_input.get("encoding", "utf-8"))
            elif action == "list_dir":
                return await self._list_dir(path, tool_input.get("pattern", "*"),
                                             tool_input.get("recursive", False))
            elif action == "search_files":
                return await self._search_files(path, tool_input.get("pattern", ""),
                                                 tool_input.get("recursive", True))
            elif action == "file_info":
                return await self._file_info(path)
            else:
                return ToolResult(output="", success=False, error=f"Unknown action: {action}")
        except PermissionError:
            return ToolResult(output="", success=False, error=f"Permission denied: {path}")
        except Exception as e:
            return ToolResult(output="", success=False, error=str(e))

    async def _read_file(self, path: Path, encoding: str) -> ToolResult:
        if not path.exists():
            return ToolResult(output="", success=False, error=f"File not found: {path}")
        if not path.is_file():
            return ToolResult(output="", success=False, error=f"Not a file: {path}")

        size = path.stat().st_size
        if size > self.max_file_size:
            return ToolResult(
                output="",
                success=False,
                error=f"File too large ({size // 1024}KB > {self.max_file_size // 1024}KB). "
                      f"Use search_files to find specific content.",
            )

        try:
            content = path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            # Try to read as binary and show hex summary
            data = path.read_bytes()
            return ToolResult(
                output=f"[Binary file — {len(data)} bytes]\nFirst 64 bytes: {data[:64].hex()}",
                success=True,
            )

        lines = content.splitlines()
        header = f"# {path} ({len(lines)} lines, {size} bytes)\n\n"
        return ToolResult(output=header + content)

    async def _write_file(self, path: Path, content: str, encoding: str) -> ToolResult:
        path.parent.mkdir(parents=True, exist_ok=True)
        existed = path.exists()
        path.write_text(content, encoding=encoding)
        lines = content.count("\n") + 1
        verb = "Updated" if existed else "Created"
        return ToolResult(output=f"{verb} {path} ({lines} lines, {len(content)} bytes)")

    async def _list_dir(self, path: Path, pattern: str, recursive: bool) -> ToolResult:
        if not path.exists():
            return ToolResult(output="", success=False, error=f"Directory not found: {path}")
        if not path.is_dir():
            return ToolResult(output="", success=False, error=f"Not a directory: {path}")

        if recursive:
            entries = sorted(path.rglob(pattern))
        else:
            entries = sorted(path.glob(pattern))

        if not entries:
            return ToolResult(output=f"No entries matching '{pattern}' in {path}")

        lines = [f"# Contents of {path}/\n"]
        for entry in entries:
            rel = entry.relative_to(path)
            if entry.is_dir():
                lines.append(f"📁 {rel}/")
            else:
                size = entry.stat().st_size
                size_str = f"{size:,}B" if size < 1024 else f"{size // 1024}KB"
                lines.append(f"📄 {rel}  [{size_str}]")

        return ToolResult(output="\n".join(lines))

    async def _search_files(self, path: Path, pattern: str, recursive: bool) -> ToolResult:
        if not pattern:
            return ToolResult(output="", success=False, error="Search pattern is required.")

        glob = "**/*" if recursive else "*"
        results = []
        try:
            for file_path in path.glob(glob):
                if not file_path.is_file():
                    continue
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    for i, line in enumerate(content.splitlines(), 1):
                        if pattern.lower() in line.lower():
                            rel = file_path.relative_to(path)
                            results.append(f"{rel}:{i}: {line.strip()}")
                except Exception:
                    continue
        except Exception as e:
            return ToolResult(output="", success=False, error=str(e))

        if not results:
            return ToolResult(output=f"No results for '{pattern}' in {path}")

        header = f"Found {len(results)} matches for '{pattern}':\n\n"
        return ToolResult(output=header + "\n".join(results[:200]))

    async def _file_info(self, path: Path) -> ToolResult:
        if not path.exists():
            return ToolResult(output="", success=False, error=f"Not found: {path}")

        stat = path.stat()
        from datetime import datetime
        info = [
            f"Path: {path.absolute()}",
            f"Type: {'directory' if path.is_dir() else 'file'}",
            f"Size: {stat.st_size:,} bytes",
            f"Modified: {datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')}",
            f"Permissions: {oct(stat.st_mode)[-3:]}",
        ]
        if path.is_file():
            info.append(f"Extension: {path.suffix or '(none)'}")
        return ToolResult(output="\n".join(info))
