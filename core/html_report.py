"""HTML report for geo-availability results."""

from __future__ import annotations

import html
from pathlib import Path

import pandas as pd

from core.store import CSV_FILE, load_results

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"
HTML_FILE = REPORTS_DIR / "report.html"


def _esc(val) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    return html.escape(str(val), quote=True)


def _status_class(status: str) -> str:
    s = (status or "").upper()
    if s == "PASS":
        return "pass"
    if s == "PARTIAL":
        return "partial"
    if s == "SKIP":
        return "skip"
    return "fail"


def _as_bool(val) -> bool | None:
    if val is True or str(val).lower() in {"true", "1", "yes"}:
        return True
    if val is False or str(val).lower() in {"false", "0", "no"}:
        return False
    if val is None or (isinstance(val, float) and pd.isna(val)) or str(val).strip() == "":
        return None
    return None


def _check_badge(val, *, ok_label: str = "OK", bad_label: str = "NO") -> str:
    b = _as_bool(val)
    if b is True:
        return f'<span class="badge badge-ok"><span class="dot"></span>{ok_label}</span>'
    if b is False:
        return f'<span class="badge badge-bad"><span class="dot"></span>{bad_label}</span>'
    return '<span class="badge badge-muted">—</span>'


def _status_badge(status: str) -> str:
    s = (status or "—").upper()
    cls = _status_class(s)
    return f'<span class="status status-{cls}">{_esc(s)}</span>'


def _short_url(url: str, max_len: int = 42) -> str:
    u = (url or "").strip()
    if not u:
        return "—"
    if len(u) <= max_len:
        return u
    return u[: max_len - 1] + "…"


def _url_cell(url, *, label: str | None = None) -> str:
    u = "" if url is None or (isinstance(url, float) and pd.isna(url)) else str(url).strip()
    if not u:
        return '<span class="muted">—</span>'
    text = label or _short_url(u)
    return (
        f'<a class="link" href="{_esc(u)}" target="_blank" rel="noopener" title="{_esc(u)}">'
        f"{_esc(text)}</a>"
    )


def _currency_cell(r: pd.Series) -> str:
    ok = _as_bool(r.get("currency_ok"))
    exp = str(r.get("currency_expected") or "").strip()
    got = str(r.get("currency_observed") or "").strip()
    label = str(r.get("currency_observed_label") or "").strip()

    # legacy column fallback
    if not got and r.get("currency_matched"):
        got = str(r.get("currency_matched") or "").strip()

    if ok is True:
        pill = f'<span class="curr-pill curr-ok">{_esc(got or exp or "OK")}</span>'
    elif ok is False:
        pill = (
            f'<span class="curr-pill curr-bad">'
            f'<span class="curr-exp">{_esc(exp or "—")}</span>'
            f'<span class="curr-arrow">→</span>'
            f'<span class="curr-got">{_esc(got or "—")}</span>'
            f"</span>"
        )
    else:
        pill = f'<span class="curr-pill curr-muted">{_esc(got or exp or "—")}</span>'

    sub = f'<div class="cell-sub" title="{_esc(label)}">{_esc(label)}</div>' if label else ""
    return f'{pill}{sub}'


def _network_cell(proxy) -> str:
    p = "" if proxy is None or (isinstance(proxy, float) and pd.isna(proxy)) else str(proxy)
    if not p:
        return '<span class="muted">—</span>'
    if "local_ip" in p.lower() or "direct" in p.lower():
        return f'<span class="net net-local" title="{_esc(p)}">Local IP</span>'
    # shorten proxy host
    short = p
    if "://" in p:
        short = p.split("://", 1)[-1]
    if " " in short:
        short = short.split(" ", 1)[0]
    if len(short) > 28:
        short = short[:27] + "…"
    return f'<span class="net net-proxy" title="{_esc(p)}">{_esc(short)}</span>'


def _summary_cards(view: pd.DataFrame) -> str:
    total = len(view)
    statuses = view["status"].astype(str).str.upper() if "status" in view.columns else pd.Series(dtype=str)
    passes = int((statuses == "PASS").sum())
    partials = int((statuses == "PARTIAL").sum())
    fails = int((statuses == "FAIL").sum())
    skips = int((statuses == "SKIP").sum())

    rate = f"{(passes / total * 100):.0f}%" if total else "—"

    return f"""
    <div class="kpis">
      <div class="kpi">
        <div class="kpi-label">Всего проверок</div>
        <div class="kpi-value">{total}</div>
      </div>
      <div class="kpi kpi-pass">
        <div class="kpi-label">PASS</div>
        <div class="kpi-value">{passes}</div>
      </div>
      <div class="kpi kpi-partial">
        <div class="kpi-label">PARTIAL</div>
        <div class="kpi-value">{partials}</div>
      </div>
      <div class="kpi kpi-fail">
        <div class="kpi-label">FAIL</div>
        <div class="kpi-value">{fails}</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">SKIP</div>
        <div class="kpi-value">{skips}</div>
      </div>
      <div class="kpi kpi-rate">
        <div class="kpi-label">Pass rate</div>
        <div class="kpi-value">{rate}</div>
      </div>
    </div>
    """


def generate_html_report(df: pd.DataFrame | None = None) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    if df is None:
        df = load_results()

    if df.empty:
        body_main = """
        <div class="empty">
          <div class="empty-title">Пока нет данных</div>
          <div class="empty-text">Запустите: <code>python check_geo.py</code></div>
        </div>
        """
        kpis = ""
        meta = "0 checks"
    else:
        view = df.iloc[::-1].copy()
        kpis = _summary_cards(view)
        total = len(view)
        passes = int((view["status"].astype(str).str.upper() == "PASS").sum())
        meta = f"{total} записей · {passes} PASS · источник: {_esc(CSV_FILE.name)}"

        rows = []
        for _, r in view.iterrows():
            st = str(r.get("status", "") or "")
            geo = str(r.get("geo", "") or "")
            geo_name = str(r.get("geo_name", "") or "")
            notes = str(r.get("error") or "").strip()
            if not notes:
                notes = str(r.get("currency_detail") or r.get("redirect_detail") or "").strip()
            if len(notes) > 120:
                notes_short = notes[:117] + "…"
            else:
                notes_short = notes

            http = r.get("http_status", "")
            if pd.isna(http) if not isinstance(http, str) else False:
                http_s = "—"
            else:
                http_s = str(int(http)) if str(http).replace(".0", "").isdigit() else str(http or "—")

            lang_sub = str(r.get("language_matched") or "").strip()
            lang_html = _check_badge(r.get("language_ok"))
            if lang_sub:
                lang_html += f'<div class="cell-sub">{_esc(lang_sub)}</div>'

            rows.append(
                f"""
                <tr class="row-{_status_class(st)}" data-status="{_esc(st.upper())}" data-geo="{_esc(geo)}">
                  <td class="col-time">
                    <div class="time-main">{_esc(r.get('datetime',''))}</div>
                  </td>
                  <td class="col-geo">
                    <span class="geo-code">{_esc(geo)}</span>
                    <div class="cell-sub">{_esc(geo_name)}</div>
                  </td>
                  <td class="col-status">{_status_badge(st)}</td>
                  <td class="col-check center">{_check_badge(r.get('opened'))}</td>
                  <td class="col-http center"><span class="http">{_esc(http_s)}</span></td>
                  <td class="col-check center">{_check_badge(r.get('redirect_ok'))}</td>
                  <td class="col-check center">{lang_html}</td>
                  <td class="col-currency">{_currency_cell(r)}</td>
                  <td class="col-url">{_url_cell(r.get('final_url'))}</td>
                  <td class="col-url muted-col">{_url_cell(r.get('registration_url') or r.get('start_url'))}</td>
                  <td class="col-net">{_network_cell(r.get('proxy'))}</td>
                  <td class="col-notes" title="{_esc(notes)}">{_esc(notes_short) if notes_short else '<span class="muted">—</span>'}</td>
                </tr>
                """
            )
        body_main = f"""
        <div class="table-wrap">
          <table class="report-table">
            <thead>
              <tr>
                <th>Время</th>
                <th>Geo</th>
                <th>Статус</th>
                <th class="center">Open</th>
                <th class="center">HTTP</th>
                <th class="center">Redirect</th>
                <th class="center">Lang</th>
                <th>Currency</th>
                <th>Final URL</th>
                <th>Registration</th>
                <th>Network</th>
                <th>Notes</th>
              </tr>
            </thead>
            <tbody>
              {''.join(rows)}
            </tbody>
          </table>
        </div>
        """

    html_doc = f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Geo Availability Report</title>
  <style>
    :root {{
      --bg0: #0b1020;
      --bg1: #121a2b;
      --card: rgba(22, 32, 52, 0.92);
      --card-border: rgba(120, 150, 200, 0.12);
      --text: #eef3ff;
      --muted: #8fa0bd;
      --line: rgba(140, 160, 200, 0.12);
      --pass: #2fe3a1;
      --pass-bg: rgba(47, 227, 161, 0.12);
      --partial: #f5c542;
      --partial-bg: rgba(245, 197, 66, 0.12);
      --fail: #ff6b7a;
      --fail-bg: rgba(255, 107, 122, 0.12);
      --skip: #9aa8c0;
      --skip-bg: rgba(154, 168, 192, 0.12);
      --accent: #6ea8ff;
      --shadow: 0 18px 50px rgba(0, 0, 0, 0.35);
      --radius: 16px;
    }}

    * {{ box-sizing: border-box; }}
    html, body {{ margin: 0; padding: 0; }}
    body {{
      min-height: 100vh;
      font-family: "Segoe UI", ui-sans-serif, system-ui, -apple-system, Roboto, Arial, sans-serif;
      color: var(--text);
      background:
        radial-gradient(1200px 600px at 10% -10%, rgba(80, 120, 255, 0.18), transparent 55%),
        radial-gradient(900px 500px at 100% 0%, rgba(47, 227, 161, 0.10), transparent 50%),
        linear-gradient(180deg, var(--bg0), var(--bg1) 40%, #0d1424);
    }}

    .page {{
      max-width: 1400px;
      margin: 0 auto;
      padding: 28px 20px 48px;
    }}

    .header {{
      display: flex;
      flex-wrap: wrap;
      align-items: flex-end;
      justify-content: space-between;
      gap: 12px 24px;
      margin-bottom: 22px;
    }}
    .header h1 {{
      margin: 0;
      font-size: 1.65rem;
      font-weight: 700;
      letter-spacing: -0.02em;
    }}
    .header .subtitle {{
      margin-top: 6px;
      color: var(--muted);
      font-size: 0.95rem;
    }}
    .legend {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }}
    .legend-item {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 6px 10px;
      border-radius: 999px;
      background: rgba(255,255,255,0.03);
      border: 1px solid var(--line);
      color: var(--muted);
      font-size: 0.78rem;
    }}
    .legend-swatch {{
      width: 8px; height: 8px; border-radius: 50%;
    }}
    .sw-pass {{ background: var(--pass); box-shadow: 0 0 10px var(--pass); }}
    .sw-partial {{ background: var(--partial); }}
    .sw-fail {{ background: var(--fail); }}
    .sw-skip {{ background: var(--skip); }}

    .kpis {{
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 18px;
    }}
    @media (max-width: 1000px) {{
      .kpis {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
    }}
    @media (max-width: 560px) {{
      .kpis {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
    .kpi {{
      background: var(--card);
      border: 1px solid var(--card-border);
      border-radius: 14px;
      padding: 14px 16px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(8px);
    }}
    .kpi-label {{
      color: var(--muted);
      font-size: 0.75rem;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      margin-bottom: 6px;
    }}
    .kpi-value {{
      font-size: 1.55rem;
      font-weight: 700;
      letter-spacing: -0.02em;
    }}
    .kpi-pass .kpi-value {{ color: var(--pass); }}
    .kpi-partial .kpi-value {{ color: var(--partial); }}
    .kpi-fail .kpi-value {{ color: var(--fail); }}
    .kpi-rate .kpi-value {{ color: var(--accent); }}

    .panel {{
      background: var(--card);
      border: 1px solid var(--card-border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      overflow: hidden;
    }}

    .table-wrap {{
      overflow: auto;
      max-height: calc(100vh - 280px);
    }}

    .report-table {{
      width: 100%;
      border-collapse: separate;
      border-spacing: 0;
      font-size: 0.875rem;
      min-width: 1100px;
    }}
    .report-table thead th {{
      position: sticky;
      top: 0;
      z-index: 2;
      text-align: left;
      padding: 12px 14px;
      font-size: 0.72rem;
      font-weight: 700;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      color: var(--muted);
      background: linear-gradient(180deg, #18233a 0%, #152033 100%);
      border-bottom: 1px solid var(--line);
      white-space: nowrap;
    }}
    .report-table th.center,
    .report-table td.center {{ text-align: center; }}

    .report-table tbody td {{
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      vertical-align: middle;
    }}
    .report-table tbody tr {{
      transition: background 0.15s ease;
    }}
    .report-table tbody tr:hover td {{
      background: rgba(110, 168, 255, 0.05);
    }}
    .report-table tbody tr.row-pass {{
      box-shadow: inset 3px 0 0 var(--pass);
    }}
    .report-table tbody tr.row-partial {{
      box-shadow: inset 3px 0 0 var(--partial);
    }}
    .report-table tbody tr.row-fail {{
      box-shadow: inset 3px 0 0 var(--fail);
    }}
    .report-table tbody tr.row-skip {{
      box-shadow: inset 3px 0 0 var(--skip);
    }}

    .time-main {{
      font-variant-numeric: tabular-nums;
      white-space: nowrap;
      font-size: 0.84rem;
    }}
    .geo-code {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 42px;
      padding: 4px 10px;
      border-radius: 8px;
      font-weight: 700;
      font-size: 0.8rem;
      letter-spacing: 0.04em;
      background: rgba(110, 168, 255, 0.12);
      color: #b7d3ff;
      border: 1px solid rgba(110, 168, 255, 0.22);
    }}
    .cell-sub {{
      margin-top: 4px;
      color: var(--muted);
      font-size: 0.75rem;
      max-width: 180px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}

    .status {{
      display: inline-flex;
      align-items: center;
      padding: 5px 10px;
      border-radius: 999px;
      font-size: 0.72rem;
      font-weight: 800;
      letter-spacing: 0.04em;
    }}
    .status-pass {{ color: var(--pass); background: var(--pass-bg); border: 1px solid rgba(47,227,161,0.25); }}
    .status-partial {{ color: var(--partial); background: var(--partial-bg); border: 1px solid rgba(245,197,66,0.25); }}
    .status-fail {{ color: var(--fail); background: var(--fail-bg); border: 1px solid rgba(255,107,122,0.25); }}
    .status-skip {{ color: var(--skip); background: var(--skip-bg); border: 1px solid rgba(154,168,192,0.25); }}

    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 9px;
      border-radius: 999px;
      font-size: 0.72rem;
      font-weight: 700;
      border: 1px solid transparent;
    }}
    .badge .dot {{
      width: 6px; height: 6px; border-radius: 50%;
      background: currentColor;
    }}
    .badge-ok {{ color: var(--pass); background: var(--pass-bg); border-color: rgba(47,227,161,0.2); }}
    .badge-bad {{ color: var(--fail); background: var(--fail-bg); border-color: rgba(255,107,122,0.2); }}
    .badge-muted {{ color: var(--muted); background: rgba(255,255,255,0.03); border-color: var(--line); }}

    .http {{
      font-variant-numeric: tabular-nums;
      font-weight: 600;
      color: #c9d7f2;
    }}

    .curr-pill {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 5px 10px;
      border-radius: 10px;
      font-weight: 700;
      font-size: 0.78rem;
      letter-spacing: 0.02em;
      border: 1px solid transparent;
      white-space: nowrap;
    }}
    .curr-ok {{
      color: var(--pass);
      background: var(--pass-bg);
      border-color: rgba(47,227,161,0.22);
    }}
    .curr-bad {{
      color: var(--fail);
      background: var(--fail-bg);
      border-color: rgba(255,107,122,0.22);
    }}
    .curr-muted {{
      color: var(--muted);
      background: rgba(255,255,255,0.03);
      border-color: var(--line);
    }}
    .curr-arrow {{ opacity: 0.7; }}
    .curr-exp {{ text-decoration: line-through; opacity: 0.75; }}

    .link {{
      color: #8fbeff;
      text-decoration: none;
      word-break: break-all;
    }}
    .link:hover {{ text-decoration: underline; color: #b6d4ff; }}

    .net {{
      display: inline-flex;
      padding: 4px 9px;
      border-radius: 8px;
      font-size: 0.74rem;
      font-weight: 600;
      max-width: 160px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}
    .net-local {{
      color: #9be7ff;
      background: rgba(100, 200, 255, 0.12);
      border: 1px solid rgba(100, 200, 255, 0.22);
    }}
    .net-proxy {{
      color: #d7c4ff;
      background: rgba(160, 120, 255, 0.12);
      border: 1px solid rgba(160, 120, 255, 0.22);
    }}

    .col-notes {{
      max-width: 200px;
      color: var(--muted);
      font-size: 0.78rem;
      word-break: break-word;
    }}
    .muted {{ color: var(--muted); }}
    .muted-col .link {{ color: #7a93b8; }}

    .empty {{
      padding: 56px 24px;
      text-align: center;
    }}
    .empty-title {{ font-size: 1.2rem; font-weight: 700; margin-bottom: 8px; }}
    .empty-text {{ color: var(--muted); }}
    code {{
      background: rgba(255,255,255,0.06);
      padding: 2px 8px;
      border-radius: 6px;
      color: #cfe0ff;
    }}

    .footer {{
      margin-top: 14px;
      color: var(--muted);
      font-size: 0.8rem;
      display: flex;
      justify-content: space-between;
      gap: 12px;
      flex-wrap: wrap;
    }}
  </style>
</head>
<body>
  <div class="page">
    <header class="header">
      <div>
        <h1>Geo Availability</h1>
        <div class="subtitle">{meta}</div>
      </div>
      <div class="legend">
        <span class="legend-item"><span class="legend-swatch sw-pass"></span>PASS</span>
        <span class="legend-item"><span class="legend-swatch sw-partial"></span>PARTIAL</span>
        <span class="legend-item"><span class="legend-swatch sw-fail"></span>FAIL</span>
        <span class="legend-item"><span class="legend-swatch sw-skip"></span>SKIP</span>
      </div>
    </header>

    {kpis}

    <section class="panel">
      {body_main}
    </section>

    <div class="footer">
      <span>Автотест: open → redirect → language → currency на /registration</span>
      <span>Обновляется после <code>python check_geo.py</code></span>
    </div>
  </div>
</body>
</html>
"""
    HTML_FILE.write_text(html_doc, encoding="utf-8")
    return HTML_FILE
