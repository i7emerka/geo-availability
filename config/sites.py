"""Site under test."""

from __future__ import annotations

import os

from dotenv import load_dotenv

from config.geos import get_geo

load_dotenv()

DEFAULT_SITE_URL = "https://fastpari.com"


def get_site_url() -> str:
    return (os.getenv("SITE_URL") or DEFAULT_SITE_URL).strip().rstrip("/")


def get_start_urls(geo_code: str) -> list[str]:
    """
    URLs to open for a geo check.

    Order:
      1) geo start_urls (if set) — e.g. RU: only https://fastpari.com
      2) SITE_URL
      3) preferred_urls (mirrors / locale shortcuts)
    """
    primary = get_site_url()
    geo = get_geo(geo_code)
    urls: list[str] = []

    explicit = list(geo.get("start_urls") or [])
    preferred = list(geo.get("preferred_urls") or [])

    # If geo defines start_urls only (no preferred), stick to those — real redirect test.
    if explicit and not preferred:
        ordered = explicit
    else:
        ordered = [*explicit, primary, *preferred]

    for u in ordered:
        u = (u or "").strip()
        if u and u not in urls:
            urls.append(u)
    return urls
