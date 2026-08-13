"""Run geo-availability checks through proxy."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from config.geos import browser_context_options, get_geo
from config.proxies import get_geo_proxy, proxy_label
from config.sites import get_start_urls
from core.browser import close_browser, launch_browser, navigation_timeout_ms, new_page
from core.detectors import (
    check_currency,
    detect_language,
    detect_redirect,
    extract_page_signals,
    overall_status,
    registration_url_from,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")


def _collect_redirects(page) -> list[str]:
    chain: list[str] = []

    def on_response(response) -> None:
        try:
            status = response.status
            # redirect responses
            if 300 <= status < 400:
                loc = response.headers.get("location") or ""
                chain.append(f"{status} {response.url} -> {loc}")
        except Exception:
            pass

    page.on("response", on_response)
    return chain


def check_geo(
    geo_code: str,
    *,
    headless: bool | None = None,
    keep_open_on_fail: bool = False,
) -> dict[str, Any]:
    """
    Full geo-availability check for one geo via cloud/local proxy.

    Returns a flat result dict suitable for CSV/report.
    """
    geo_code = geo_code.strip().upper()
    geo = get_geo(geo_code)
    use_local_ip = bool(geo.get("use_local_ip"))
    proxy = None if use_local_ip else get_geo_proxy(geo_code)
    start_urls = get_start_urls(geo_code)
    network_label = "local_ip (direct)" if use_local_ip else proxy_label(proxy)

    result: dict[str, Any] = {
        "datetime": _now_iso(),
        "geo": geo_code,
        "geo_name": geo["name"],
        "proxy": network_label,
        "status": "FAIL",
        "opened": False,
        "http_status": None,
        "start_url": start_urls[0] if start_urls else "",
        "final_url": "",
        "redirect_ok": False,
        "redirect_detail": "",
        "language_ok": False,
        "language_detail": "",
        "currency_ok": False,
        "currency_expected": geo.get("expected_currency") or "",
        "currency_observed": "",
        "currency_observed_label": "",
        "currency_detail": "",
        "error": "",
        "duration_ms": 0,
    }

    if not use_local_ip and not proxy:
        result["error"] = (
            f"Proxy not configured for {geo_code}. "
            f"Set {geo_code}_PROXY_SERVER in .env "
            f"(or set use_local_ip=True in config/geos.py)"
        )
        result["status"] = "SKIP"
        return result

    ctx_opts = browser_context_options(geo)
    if use_local_ip:
        print(f"  [{geo_code}] network: local IP (no proxy)")
    else:
        print(f"  [{geo_code}] network: {network_label}")
    print(
        f"  [{geo_code}] browser: locale={ctx_opts.get('locale')} "
        f"tz={ctx_opts.get('timezone_id')} "
        f"lang={ctx_opts.get('extra_http_headers', {}).get('Accept-Language', '')[:40]}…"
    )

    pw = None
    context = None
    browser = None
    t0 = datetime.now(timezone.utc)

    try:
        pw, context, browser = launch_browser(
            proxy,
            profile_key=f"geo_{geo_code}",
            headless=headless,
            persistent=False,
            context_options=ctx_opts,
        )

        last_error = ""
        for start_url in start_urls:
            page = new_page(context)
            redirect_log = _collect_redirects(page)
            try:
                print(f"  [{geo_code}] open: {start_url}")
                response = page.goto(
                    start_url,
                    wait_until="domcontentloaded",
                    timeout=navigation_timeout_ms(),
                )
                # allow soft client redirects / SPA settle
                try:
                    page.wait_for_load_state("networkidle", timeout=15000)
                except PlaywrightTimeoutError:
                    pass
                page.wait_for_timeout(1500)

                final_url = page.url
                http_status = response.status if response else None
                signals = extract_page_signals(page)

                redir = detect_redirect(
                    start_url,
                    final_url,
                    redirect_log,
                    geo.get("url_hints") or [],
                )
                lang = detect_language(signals, geo.get("languages") or [])

                opened = http_status is not None and http_status < 400
                # some mirrors return 203 etc — still treat as open if body exists
                if not opened and signals.get("body_sample"):
                    opened = True

                # Currency: exact value selected on registration form (not synonym search).
                expected_cur = (geo.get("expected_currency") or "").strip().upper()
                cur = {
                    "ok": False,
                    "expected": expected_cur,
                    "observed": "",
                    "observed_label": "",
                    "detail": "registration page not opened",
                }
                reg_url = ""
                if opened:
                    reg_url = registration_url_from(final_url, "/registration")
                    print(f"  [{geo_code}] registration: {reg_url}")
                    try:
                        reg_resp = page.goto(
                            reg_url,
                            wait_until="domcontentloaded",
                            timeout=navigation_timeout_ms(),
                        )
                        try:
                            page.wait_for_load_state("networkidle", timeout=25000)
                        except PlaywrightTimeoutError:
                            pass

                        # Registration is a micro-frontend: wait for preloader to go away.
                        try:
                            page.wait_for_function(
                                """() => {
                                  const plugs = document.querySelectorAll(
                                    '.ui-preloader-default, .ui-plug .ui-preloader-default'
                                  );
                                  const visible = Array.from(plugs).some(el => {
                                    const st = window.getComputedStyle(el);
                                    return st && st.display !== 'none' && st.visibility !== 'hidden'
                                      && el.offsetParent !== null;
                                  });
                                  return !visible;
                                }""",
                                timeout=35000,
                            )
                        except PlaywrightTimeoutError:
                            pass

                        # Wait until currency field text like "… (RUB)" is visible
                        try:
                            page.wait_for_function(
                                """() => {
                                  const t = (document.body && document.body.innerText) || '';
                                  return /\\([A-Z]{3}\\)/.test(t)
                                    || /выберите валюту|select currency|sélectionnez la devise|currency|devise|валют|عملة/i.test(t);
                                }""",
                                timeout=35000,
                            )
                        except PlaywrightTimeoutError:
                            page.wait_for_timeout(5000)

                        locator = (geo.get("currency_locator") or "").strip()
                        cur = check_currency(
                            page,
                            expected_cur,
                            currency_locator=locator,
                        )
                        for _ in range(3):
                            if cur.get("observed"):
                                break
                            page.wait_for_timeout(4000)
                            cur = check_currency(
                                page,
                                expected_cur,
                                currency_locator=locator,
                            )

                        reg_status = reg_resp.status if reg_resp else None
                        cur["detail"] = (
                            f"{cur['detail']} | reg_http={reg_status} | "
                            f"reg_url={page.url}"
                        )
                        reg_url = page.url
                    except Exception as reg_exc:
                        cur = {
                            "ok": False,
                            "expected": expected_cur,
                            "observed": "",
                            "observed_label": "",
                            "detail": f"registration failed: {reg_exc}",
                        }
                        print(f"  [{geo_code}] registration fail: {reg_exc}")

                status = overall_status(
                    opened,
                    redir["ok"],
                    lang["ok"],
                    cur["ok"],
                )

                result.update(
                    {
                        "status": status,
                        "opened": opened,
                        "http_status": http_status,
                        "start_url": start_url,
                        "final_url": final_url,
                        "registration_url": reg_url,
                        "redirect_ok": redir["ok"],
                        "redirect_detail": redir["detail"],
                        "redirect_count": redir.get("redirect_count", 0),
                        "language_ok": lang["ok"],
                        "language_detail": lang["detail"],
                        "language_matched": ",".join(lang.get("matched") or []),
                        "currency_ok": cur["ok"],
                        "currency_expected": cur.get("expected") or expected_cur,
                        "currency_observed": cur.get("observed") or "",
                        "currency_observed_label": cur.get("observed_label") or "",
                        "currency_detail": cur["detail"],
                        "error": "" if opened else f"HTTP {http_status}",
                    }
                )

                print(
                    f"  [{geo_code}] {status} | HTTP {http_status} | "
                    f"redirect={'OK' if redir['ok'] else 'NO'} | "
                    f"lang={'OK' if lang['ok'] else 'NO'} | "
                    f"currency={'OK' if cur['ok'] else 'NO'} "
                    f"(expected={cur.get('expected') or expected_cur} "
                    f"observed={cur.get('observed') or '—'})"
                )
                print(f"  [{geo_code}] final: {final_url}")
                if reg_url:
                    print(f"  [{geo_code}] currency: {cur.get('detail', '')}")

                # Success path: primary URL worked enough (opened)
                if opened:
                    page.close()
                    break

                last_error = f"HTTP {http_status} on {start_url}"
            except Exception as exc:
                last_error = str(exc)
                print(f"  [{geo_code}] fail on {start_url}: {exc}")
                result["error"] = last_error
            finally:
                try:
                    page.close()
                except Exception:
                    pass
        else:
            if result["status"] == "FAIL" and last_error:
                result["error"] = last_error

    except Exception as exc:
        result["error"] = str(exc)
        result["status"] = "FAIL"
        print(f"  [{geo_code}] browser error: {exc}")
    finally:
        elapsed = (datetime.now(timezone.utc) - t0).total_seconds() * 1000
        result["duration_ms"] = int(elapsed)
        if not keep_open_on_fail:
            close_browser(pw, context, browser)
        elif result["status"] == "PASS":
            close_browser(pw, context, browser)

    return result


def check_many(geo_codes: list[str], **kwargs) -> list[dict[str, Any]]:
    results = []
    for code in geo_codes:
        print(f"\n=== GEO {code} ===")
        results.append(check_geo(code, **kwargs))
    return results
