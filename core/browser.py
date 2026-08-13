"""Playwright browser helpers with geo proxy and locale fingerprint."""

from __future__ import annotations

import os
from pathlib import Path

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

PROFILE_DATA_ROOT = Path(__file__).resolve().parent.parent / "data" / "playwright_profiles"

# Headless shell on some Windows setups crashes (V8 snapshot / GPU).
# Force full Chromium unless user overrides.
os.environ.setdefault("PLAYWRIGHT_CHROMIUM_USE_HEADLESS_SHELL", "0")

_LAUNCH_ARGS = [
    "--disable-gpu",
    "--disable-dev-shm-usage",
    "--no-sandbox",
    "--disable-software-rasterizer",
    # Reduce "automation" fingerprints a bit
    "--disable-blink-features=AutomationControlled",
]


def _env_bool(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def navigation_timeout_ms() -> int:
    try:
        return int(os.getenv("NAVIGATION_TIMEOUT_MS", "45000"))
    except ValueError:
        return 45000


def launch_browser(
    proxy: dict | None = None,
    *,
    profile_key: str = "default",
    headless: bool | None = None,
    persistent: bool = False,
    context_options: dict | None = None,
) -> tuple[Playwright, BrowserContext, Browser | None]:
    """
    Launch Chromium with optional proxy and geo-specific context options
    (locale, Accept-Language, timezone, geolocation).

    Returns (playwright, context, browser).
    browser is None when using persistent context.
    """
    if headless is None:
        headless = _env_bool("HEADLESS", True)

    ctx = dict(context_options or {})
    # Sensible defaults if caller didn't pass geo options
    ctx.setdefault("locale", "en-US")
    ctx.setdefault("ignore_https_errors", True)
    ctx.setdefault("viewport", {"width": 1366, "height": 768})

    pw = sync_playwright().start()

    if persistent:
        path = PROFILE_DATA_ROOT / profile_key
        path.mkdir(parents=True, exist_ok=True)
        kwargs: dict = {
            "headless": headless,
            "args": list(_LAUNCH_ARGS),
            **ctx,
        }
        if proxy:
            kwargs["proxy"] = proxy
        context = pw.chromium.launch_persistent_context(str(path), **kwargs)
        return pw, context, None

    browser = pw.chromium.launch(headless=headless, args=list(_LAUNCH_ARGS))
    new_ctx_kwargs = dict(ctx)
    if proxy:
        new_ctx_kwargs["proxy"] = proxy
    context = browser.new_context(**new_ctx_kwargs)
    return pw, context, browser


def close_browser(
    pw: Playwright | None,
    context: BrowserContext | None,
    browser: Browser | None = None,
) -> None:
    try:
        if context:
            context.close()
    except Exception:
        pass
    try:
        if browser:
            browser.close()
    except Exception:
        pass
    try:
        if pw:
            pw.stop()
    except Exception:
        pass


def new_page(context: BrowserContext) -> Page:
    page = context.new_page()
    page.set_default_timeout(navigation_timeout_ms())
    page.set_default_navigation_timeout(navigation_timeout_ms())
    return page
