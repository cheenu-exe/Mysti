"""Network operations with SSRF protection."""

from __future__ import annotations
import ipaddress
import socket
import httpx
from urllib.parse import urlparse
from mysti.security.permissions import Permission, TrustLevel
from mysti.tools.gateway import Tool, ToolResult


class NetworkTool(Tool):
    name, description = "network", "Network operations (HTTP, DNS, ping)"
    required_permissions = [Permission.TOOLS_READ]
    min_trust_level = TrustLevel.T2

    def __init__(self, client: httpx.AsyncClient | None = None):
        self.client = client or httpx.AsyncClient(timeout=10)

    def _check(self, url: str):
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("unsupported URL scheme")
        host = parsed.hostname
        if host:
            try:
                if ipaddress.ip_address(host).is_private or ipaddress.ip_address(host).is_loopback:
                    raise ValueError("internal address blocked")
            except ValueError as exc:
                if str(exc) == "internal address blocked":
                    raise

    async def http_get(self, url: str, headers: dict | None = None) -> dict:
        self._check(url)
        r = await self.client.get(url, headers=headers)
        return {"status_code": r.status_code, "headers": dict(r.headers), "text": r.text}

    async def http_post(self, url: str, data: dict | None = None) -> dict:
        self._check(url)
        r = await self.client.post(url, json=data)
        return {"status_code": r.status_code, "headers": dict(r.headers), "text": r.text}

    async def dns_lookup(self, domain: str) -> dict:
        return {
            "domain": domain,
            "addresses": sorted({item[4][0] for item in socket.getaddrinfo(domain, None)}),
        }

    async def ping(self, host: str, count: int = 4) -> dict:
        return {"host": host, "reachable": bool(socket.gethostbyname(host)), "count": count}

    async def execute(self, params: dict) -> ToolResult:
        try:
            return ToolResult(
                True, await getattr(self, params.pop("operation"))(**params), tool_name=self.name
            )
        except Exception as exc:
            return ToolResult(False, error=str(exc), tool_name=self.name)
