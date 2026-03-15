"""
nexus/tools/media.py — PDF reader and Image analyzer tools.

PdfTool: Extract text from PDF files using pypdf.
ImageTool: Send images to Claude Vision for analysis.
"""

from __future__ import annotations

import base64
from pathlib import Path

from mind_shell.tools.base_tool import BaseTool, ToolResult


class PdfTool(BaseTool):
    name = "pdf_reader"
    description = (
        "Extract and read text content from PDF files. "
        "Use to analyze documents, papers, reports, or any PDF."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the PDF file.",
            },
            "pages": {
                "type": "string",
                "description": "Page range to extract, e.g. '1-5' or '3' (default: all).",
                "default": "all",
            },
            "max_chars": {
                "type": "integer",
                "description": "Maximum characters to return (default: 10000).",
                "default": 10000,
            },
        },
        "required": ["path"],
    }

    async def execute(self, tool_input: dict) -> ToolResult:
        path = Path(tool_input.get("path", "")).expanduser()
        pages_str = tool_input.get("pages", "all")
        max_chars = tool_input.get("max_chars", 10000)

        if not path.exists():
            return ToolResult(output="", success=False, error=f"File not found: {path}")
        if path.suffix.lower() != ".pdf":
            return ToolResult(output="", success=False, error=f"Not a PDF file: {path}")

        try:
            from pypdf import PdfReader
        except ImportError:
            return ToolResult(output="", success=False,
                              error="pypdf not installed. Run: pip install pypdf")

        try:
            reader = PdfReader(str(path))
            total_pages = len(reader.pages)

            # Parse page range
            if pages_str == "all":
                page_indices = list(range(total_pages))
            elif "-" in pages_str:
                start, end = pages_str.split("-")
                page_indices = list(range(int(start) - 1, min(int(end), total_pages)))
            else:
                page_indices = [int(pages_str) - 1]

            texts = []
            for i in page_indices:
                if 0 <= i < total_pages:
                    text = reader.pages[i].extract_text() or ""
                    texts.append(f"--- Page {i + 1} ---\n{text}")

            full_text = "\n\n".join(texts)

            if len(full_text) > max_chars:
                full_text = full_text[:max_chars] + f"\n\n… [truncated at {max_chars} chars]"

            header = (
                f"# PDF: {path.name}\n"
                f"Pages: {total_pages} total, showing {len(page_indices)}\n\n"
            )
            return ToolResult(output=header + full_text)

        except Exception as e:
            return ToolResult(output="", success=False, error=f"PDF read error: {e}")


class ImageTool(BaseTool):
    name = "image_analyzer"
    description = (
        "Analyze, describe, or extract information from image files. "
        "Supports PNG, JPEG, GIF, WebP. "
        "Use to understand screenshots, diagrams, photos, or any visual content."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the image file.",
            },
            "question": {
                "type": "string",
                "description": "Specific question to answer about the image (optional).",
                "default": "Describe this image in detail.",
            },
        },
        "required": ["path"],
    }

    SUPPORTED_FORMATS = {".png": "image/png", ".jpg": "image/jpeg",
                         ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp"}

    async def execute(self, tool_input: dict) -> ToolResult:
        path = Path(tool_input.get("path", "")).expanduser()
        question = tool_input.get("question", "Describe this image in detail.")

        if not path.exists():
            return ToolResult(output="", success=False, error=f"File not found: {path}")

        media_type = self.SUPPORTED_FORMATS.get(path.suffix.lower())
        if not media_type:
            return ToolResult(
                output="",
                success=False,
                error=f"Unsupported image format: {path.suffix}. "
                      f"Supported: {', '.join(self.SUPPORTED_FORMATS.keys())}",
            )

        try:
            image_data = base64.standard_b64encode(path.read_bytes()).decode("utf-8")
        except Exception as e:
            return ToolResult(output="", success=False, error=f"Could not read image: {e}")

        # Return a structured response that the LLM client will handle specially
        # The client detects this marker and injects the image into the API call
        return ToolResult(
            output=f"[IMAGE_ANALYSIS_REQUEST]\n"
                   f"path={path}\n"
                   f"media_type={media_type}\n"
                   f"question={question}\n"
                   f"data_b64={image_data[:50]}...[truncated for display]",
            success=True,
        )

    @staticmethod
    def build_vision_message(path: Path, media_type: str, image_data: str, question: str) -> dict:
        """Build an Anthropic API message with image content."""
        return {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_data,
                    },
                },
                {"type": "text", "text": question},
            ],
        }
