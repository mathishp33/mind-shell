"""
nexus/tools/web.py — Web search and page fetch tools.

WebSearchTool: Search the web via Brave Search API (or DuckDuckGo fallback).
WebFetchTool: Fetch a URL and convert HTML to clean Markdown.

Set BRAVE_API_KEY or SERPER_API_KEY in your environment.
"""

from __future__ import annotations

import os
from urllib.parse import quote_plus

import httpx

from mind_shell.tools.base_tool import BaseTool, ToolResult


class WebSearchTool(BaseTool):
    name = "web_search"
    description = (
        "Search the web for current information. Returns titles, URLs, and snippets. "
        "Use for research, finding documentation, news, or any up-to-date information."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query.",
            },
            "num_results": {
                "type": "integer",
                "description": "Number of results to return (default: 5, max: 10).",
                "default": 5,
            },
            "site": {
                "type": "string",
                "description": "Restrict search to a specific site (e.g. 'github.com').",
            },
        },
        "required": ["query"],
    }

    async def execute(self, tool_input: dict) -> ToolResult:
        query = tool_input.get("query", "")
        num_results = min(tool_input.get("num_results", 5), 10)
        site = tool_input.get("site", "")

        if site:
            query = f"site:{site} {query}"

        brave_key = os.getenv("BRAVE_API_KEY")
        serper_key = os.getenv("SERPER_API_KEY")

        try:
            if brave_key:
                return await self._search_brave(query, num_results, brave_key)
            elif serper_key:
                return await self._search_serper(query, num_results, serper_key)
            else:
                return await self._search_duckduckgo(query, num_results)
        except Exception as e:
            return ToolResult(output="", success=False, error=f"Search failed: {e}")

    async def _search_brave(self, query: str, num: int, api_key: str) -> ToolResult:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": num},
                headers={"Accept": "application/json", "X-Subscription-Token": api_key},
            )
            resp.raise_for_status()
            data = resp.json()

        results = data.get("web", {}).get("results", [])
        return self._format_results(query, results, "title", "url", "description")

    async def _search_serper(self, query: str, num: int, api_key: str) -> ToolResult:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://google.serper.dev/search",
                json={"q": query, "num": num},
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()

        results = data.get("organic", [])
        return self._format_results(query, results, "title", "link", "snippet")

    async def _search_duckduckgo(self, query: str, num: int) -> ToolResult:
        """Fallback: DuckDuckGo Instant Answer API (limited but free)."""
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": 1},
            )
            resp.raise_for_status()
            data = resp.json()

        lines = [f"## Search results for: {query}\n"]
        if data.get("AbstractText"):
            lines.append(f"**Summary:** {data['AbstractText']}")
            lines.append(f"**Source:** {data.get('AbstractURL', '')}\n")

        related = data.get("RelatedTopics", [])[:num]
        for item in related:
            if "Text" in item and "FirstURL" in item:
                lines.append(f"- [{item['Text'][:80]}]({item['FirstURL']})")

        if len(lines) == 1:
            return ToolResult(
                output="",
                success=False,
                error="No results found. Set BRAVE_API_KEY for better search results.",
            )

        return ToolResult(output="\n".join(lines))

    def _format_results(self, query: str, results: list,
                        title_key: str, url_key: str, snippet_key: str) -> ToolResult:
        if not results:
            return ToolResult(output=f"No results found for: {query}")

        lines = [f"## Search results for: {query}\n"]
        for i, r in enumerate(results, 1):
            title = r.get(title_key, "No title")
            url = r.get(url_key, "")
            snippet = r.get(snippet_key, "")
            lines.append(f"### {i}. {title}")
            lines.append(f"URL: {url}")
            if snippet:
                lines.append(f"{snippet}\n")

        return ToolResult(output="\n".join(lines))


class WebFetchTool(BaseTool):
    name = "web_fetch"
    description = (
        "Fetch the content of a URL and convert it to readable Markdown. "
        "Use to read documentation, articles, GitHub READMEs, or any web page."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to fetch.",
            },
            "selector": {
                "type": "string",
                "description": "CSS selector to extract specific content (e.g. 'article', 'main').",
            },
            "max_length": {
                "type": "integer",
                "description": "Maximum characters to return (default: 8000).",
                "default": 8000,
            },
        },
        "required": ["url"],
    }

    async def execute(self, tool_input: dict) -> ToolResult:
        url = tool_input.get("url", "")
        selector = tool_input.get("selector", "")
        max_length = tool_input.get("max_length", 8000)

        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        try:
            async with httpx.AsyncClient(
                timeout=20,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (Nexus CLI; +https://github.com/nexus-cli)"},
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                content_type = resp.headers.get("content-type", "")

                if "text/html" not in content_type and "text/plain" not in content_type:
                    return ToolResult(
                        output=f"URL returned non-text content: {content_type}",
                        success=False,
                        error="Cannot parse non-HTML content. Use pdf_reader for PDFs.",
                    )

                html = resp.text

            return self._html_to_markdown(url, html, selector, max_length)

        except httpx.HTTPStatusError as e:
            return ToolResult(output="", success=False, error=f"HTTP {e.response.status_code}: {url}")
        except Exception as e:
            return ToolResult(output="", success=False, error=f"Fetch failed: {e}")

    def _html_to_markdown(self, url: str, html: str, selector: str, max_length: int) -> ToolResult:
        try:
            from bs4 import BeautifulSoup
            from markdownify import markdownify
        except ImportError:
            return ToolResult(
                output="",
                success=False,
                error="beautifulsoup4 or markdownify not installed."
            )

        soup = BeautifulSoup(html, "html.parser")

        # Remove script and style tags
        for tag in soup(["script", "style"]):
            tag.decompose()

        # Select content
        if selector:
            content = soup.select_one(selector) or soup.body or soup
        else:
            content = soup.body or soup

        markdown = markdownify(str(content), heading_style="atx")
        lines = markdown.split("\n")
        lines = [l for l in lines if l.strip()]
        text = "\n".join(lines)

        if len(text) > max_length:
            text = text[:max_length] + f"\n\n… [truncated at {max_length} chars]"

        header = f"# Content from {url}\n\n"
        return ToolResult(output=header + text)
