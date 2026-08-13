"""Proxy config from .env (same formats as playwrightmonitoring)."""

from __future__ import annotations

import os
import re

from dotenv import load_dotenv

load_dotenv()

# Dolphin / MangoProxy: socks5://host:port:username:password
_EMBEDDED_PROXY_RE = re.compile(
    r"^(?P<scheme>https?|socks5)://(?P<host>[^:]+):(?P<port>\d+):(?P<username>[^:]+):(?P<password>.+)$"
)
# Standard URL: socks5://username:password@host:port
_AT_PROXY_RE = re.compile(
    r"^(?P<scheme>https?|socks5)://(?P<username>[^:]+):(?P<password>[^@]+)@(?P<host>[^:]+):(?P<port>\d+)$"
)


def parse_proxy_config(
    server: str,
    username: str = "",
    password: str = "",
) -> dict | None:
    """Parse proxy for Playwright. Supports Dolphin/Mango one-line format."""
    server = (server or "").strip()
    if not server:
        return None

    match = _EMBEDDED_PROXY_RE.match(server) or _AT_PROXY_RE.match(server)
    if match:
        parts = match.groupdict()
        # Chromium does not support SOCKS5 auth; Mango usually accepts HTTP on same port.
        scheme = "http" if parts["scheme"] == "socks5" else parts["scheme"]
        return {
            "server": f"{scheme}://{parts['host']}:{parts['port']}",
            "username": parts["username"],
            "password": parts["password"],
        }

    proxy: dict = {"server": server}
    if username.strip():
        proxy["username"] = username.strip()
    if password.strip():
        proxy["password"] = password.strip()
    return proxy


def get_geo_proxy(geo_code: str) -> dict | None:
    """Load proxy for geo from env: {GEO}_PROXY_SERVER / USERNAME / PASSWORD."""
    prefix = geo_code.strip().upper()
    server = os.getenv(f"{prefix}_PROXY_SERVER", "").strip()
    username = os.getenv(f"{prefix}_PROXY_USERNAME", "").strip()
    password = os.getenv(f"{prefix}_PROXY_PASSWORD", "").strip()
    return parse_proxy_config(server, username, password)


def proxy_label(proxy: dict | None) -> str:
    if not proxy:
        return "direct (no proxy)"
    server = proxy.get("server", "?")
    user = proxy.get("username") or ""
    if user:
        return f"{server} (user={user[:8]}…)" if len(user) > 8 else f"{server} (user={user})"
    return server
