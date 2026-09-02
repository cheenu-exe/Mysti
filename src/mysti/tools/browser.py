"""Safe HTTP page fetching and lightweight HTML extraction."""

from __future__ import annotations
import time
from urllib.parse import urlparse
import httpx
from mysti.security.permissions import Permission, TrustLevel
from mysti.tools.gateway import Tool, ToolResult


class BrowserTool(Tool):
    name, description = "browser", "Browse and extract web content"
    required_permissions = [Permission.TOOLS_READ]
    min_trust_level = TrustLevel.T2

    def __init__(self, client: httpx.AsyncClient | None = None):
        self.client = client or httpx.AsyncClient(timeout=10, follow_redirects=False)
        self._cache: dict[str, tuple[float, dict]] = {}

    def _url(self, url: str) -> None:
        if urlparse(url).scheme not in ("http", "https"):
            raise ValueError("unsupported URL scheme")

    async def fetch_page(self, url: str) -> dict:
        self._url(url)
        cached = self._cache.get(url)
        if cached and time.monotonic() - cached[0] < 3600:
            return cached[1]
        response = await self.client.get(url)
        response.raise_for_status()
        if len(response.content) > 5 * 1024 * 1024:
            raise ValueError("response exceeds maximum size")
        from html.parser import HTMLParser

        class Parser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.title, self.text, self.links, self.in_title = "", [], [], False

            def handle_starttag(self, tag, attrs):
                if tag == "title":
                    self.in_title = True
                if tag == "a":
                    href = dict(attrs).get("href")
                    if href:
                        self.links.append(href)

            def handle_endtag(self, tag):
                if tag == "title":
                    self.in_title = False

            def handle_data(self, data):
                if self.in_title:
                    self.title += data
                self.text.append(data)

        parser = Parser()
        parser.feed(response.text)
        result = {
            "title": parser.title.strip(),
            "content": " ".join(" ".join(parser.text).split()),
            "links": parser.links,
        }
        self._cache[url] = (time.monotonic(), result)
        return result

    async def extract_text(self, url: str) -> str:
        return (await self.fetch_page(url))["content"]

    async def extract_links(self, url: str) -> list[str]:
        return (await self.fetch_page(url))["links"]

    async def search(self, query: str) -> list[dict]:
        return []

    async def execute(self, params: dict) -> ToolResult:
        try:
            return ToolResult(
                True, await getattr(self, params.pop("operation"))(**params), tool_name=self.name
            )
        except Exception as exc:
            return ToolResult(False, error=str(exc), tool_name=self.name)
