#!/usr/bin/env python3
"""CLI: daily geo-availability checks via cloud proxies."""

from __future__ import annotations

import argparse
import os
import sys

# Windows consoles often use cp1251 — avoid crash on ৳ / ₽ / сум
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from dotenv import load_dotenv

load_dotenv()

from config.geos import GEOS, list_geo_codes
from core.checker import check_many
from core.html_report import generate_html_report
from core.publish_report import publish_report
from core.store import append_results


def _env_bool(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Geo-availability checks (open / redirect / language / currency)",
    )
    parser.add_argument(
        "--geos",
        help=f"Geo codes comma-separated. Default: all ({','.join(list_geo_codes())})",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Show browser window (HEADLESS=0)",
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Do not write HTML report",
    )
    parser.add_argument(
        "--no-publish",
        action="store_true",
        help="Do not publish report to GitHub Pages",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List configured geos and exit",
    )
    args = parser.parse_args(argv)

    if args.list:
        for code, meta in GEOS.items():
            print(
                f"{code}: {meta['name']} | lang={meta['languages']} | "
                f"expected_currency={meta.get('expected_currency')} | "
                f"hints={meta['url_hints']}"
            )
        return 0

    if args.geos:
        codes = [c.strip().upper() for c in args.geos.split(",") if c.strip()]
        unknown = [c for c in codes if c not in GEOS]
        if unknown:
            print(f"Unknown geos: {', '.join(unknown)}")
            print(f"Known: {', '.join(list_geo_codes())}")
            return 1
    else:
        codes = list_geo_codes()

    headless = False if args.headed else None
    print(f"Geo-availability run: {', '.join(codes)}")

    results = check_many(codes, headless=headless)
    path = append_results(results)
    print(f"\nSaved: {path}")

    if not args.no_report and _env_bool("WRITE_HTML_REPORT", True):
        html = generate_html_report()
        print(f"Report: {html}")
        if not args.no_publish and _env_bool("GITHUB_PAGES_PUBLISH", True):
            publish_report(html)

    # exit code: fail if any FAIL (SKIP is ok / config issue)
    hard_fails = [r for r in results if r.get("status") == "FAIL"]
    if hard_fails:
        print(f"\nFailed geos: {', '.join(r['geo'] for r in hard_fails)}")
        return 2

    skips = [r for r in results if r.get("status") == "SKIP"]
    if skips and len(skips) == len(results):
        print("\nAll geos skipped (configure proxies in .env)")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
