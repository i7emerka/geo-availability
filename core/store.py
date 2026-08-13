"""CSV storage for geo-check results."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"
CSV_FILE = REPORTS_DIR / "geo_checks.csv"

COLUMNS = [
    "datetime",
    "geo",
    "geo_name",
    "status",
    "opened",
    "http_status",
    "start_url",
    "final_url",
    "registration_url",
    "redirect_ok",
    "redirect_count",
    "redirect_detail",
    "language_ok",
    "language_matched",
    "language_detail",
    "currency_ok",
    "currency_expected",
    "currency_observed",
    "currency_observed_label",
    "currency_detail",
    "proxy",
    "duration_ms",
    "error",
]


def _ensure_dir() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def append_results(rows: list[dict[str, Any]]) -> Path:
    _ensure_dir()
    frame = pd.DataFrame(rows)
    for col in COLUMNS:
        if col not in frame.columns:
            frame[col] = ""
    frame = frame[COLUMNS]

    if CSV_FILE.exists():
        existing = pd.read_csv(CSV_FILE)
        frame = pd.concat([existing, frame], ignore_index=True)

    frame.to_csv(CSV_FILE, index=False)
    return CSV_FILE


def load_results() -> pd.DataFrame:
    if not CSV_FILE.exists():
        return pd.DataFrame(columns=COLUMNS)
    return pd.read_csv(CSV_FILE)
