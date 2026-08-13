"""Detect language, currency, and geo-redirect correctness on a loaded page."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from playwright.sync_api import Page


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def extract_page_signals(page: Page) -> dict:
    """Collect language / currency / form signals from the live page."""
    return page.evaluate(
        """() => {
          const htmlLang = (document.documentElement.getAttribute('lang') || '').trim();
          const title = document.title || '';
          const bodyText = (document.body && document.body.innerText)
            ? document.body.innerText.slice(0, 12000)
            : '';

          // Common meta / i18n hooks
          const metaLang = document.querySelector('meta[http-equiv="content-language"]')
            ?.getAttribute('content') || '';
          const ogLocale = document.querySelector('meta[property="og:locale"]')
            ?.getAttribute('content') || '';

          // Currency-ish attributes / data hooks
          const currencyAttrs = [];
          document.querySelectorAll(
            '[data-currency], [currency], [data-currency-code], [name*="currency" i], [id*="currency" i]'
          ).forEach(el => {
            const v = el.getAttribute('data-currency')
              || el.getAttribute('currency')
              || el.getAttribute('data-currency-code')
              || el.getAttribute('value')
              || (el.value !== undefined ? String(el.value) : '');
            if (v) currencyAttrs.push(String(v));
          });

          // <select> / <option> values and labels (registration form)
          const formOptions = [];
          document.querySelectorAll('select option, [role="option"], [role="listbox"] *').forEach(el => {
            const text = (el.innerText || el.textContent || '').trim();
            const val = el.getAttribute('value') || '';
            if (text) formOptions.push(text);
            if (val) formOptions.push(val);
          });
          // selected / visible control text
          document.querySelectorAll('select').forEach(sel => {
            const opt = sel.options && sel.options[sel.selectedIndex];
            if (opt) {
              formOptions.push((opt.text || '').trim());
              formOptions.push((opt.value || '').trim());
            }
          });

          // Visible money-like snippets
          const moneySnippets = [];
          const re = /(?:UZS|BDT|RUB|RUR|EGP|XOF|USD|EUR|CFA|FCFA|₸|৳|₽|E£|£E|сум|руб\\.?|so['’ʻ]?m|taka|Tk\\b|ج\\.م|جنيه)[^\\n]{0,24}/gi;
          let m;
          const sample = (bodyText + ' ' + formOptions.join(' ')).slice(0, 10000);
          while ((m = re.exec(sample)) !== null && moneySnippets.length < 30) {
            moneySnippets.push(m[0].trim());
          }

          // URL query often carries ?currency=RUB
          const params = new URLSearchParams(location.search || '');
          const urlCurrency = params.get('currency') || params.get('Currency') || '';
          if (urlCurrency) currencyAttrs.push(urlCurrency);

          // Input placeholders / aria labels around currency
          const fieldHints = [];
          document.querySelectorAll('input, button, label, span, div, p, li').forEach(el => {
            const name = (el.getAttribute('name') || '') + ' ' + (el.getAttribute('id') || '')
              + ' ' + (el.getAttribute('placeholder') || '') + ' ' + (el.getAttribute('aria-label') || '');
            if (/currenc|валют|сум|rub|uzs|bdt/i.test(name) || /currenc|валют/i.test(el.className || '')) {
              const t = (el.innerText || el.textContent || el.value || '').trim();
              if (t && t.length < 80) fieldHints.push(t);
            }
          });

          return {
            html_lang: htmlLang,
            meta_lang: metaLang,
            og_locale: ogLocale,
            title,
            body_sample: bodyText.slice(0, 6000),
            currency_attrs: Array.from(new Set(currencyAttrs)).slice(0, 30),
            form_options: Array.from(new Set(formOptions.filter(Boolean))).slice(0, 40),
            field_hints: Array.from(new Set(fieldHints.filter(Boolean))).slice(0, 30),
            money_snippets: moneySnippets,
            url_currency: urlCurrency,
            final_url: location.href,
            pathname: location.pathname || '',
            search: location.search || '',
          };
        }"""
    )


def registration_url_from(final_url: str, path: str = "/registration") -> str:
    """Build locale-aware registration URL from landing final URL."""
    from urllib.parse import urlparse, urlunparse

    parsed = urlparse((final_url or "").strip())
    if not parsed.scheme or not parsed.netloc:
        return ""

    base_path = (parsed.path or "/").rstrip("/")
    reg = path if path.startswith("/") else f"/{path}"
    # already on registration
    if base_path.lower().endswith(reg.lower()):
        new_path = base_path
    else:
        new_path = f"{base_path}{reg}" if base_path else reg

    return urlunparse((parsed.scheme, parsed.netloc, new_path, "", "", ""))


def detect_language(signals: dict, expected_languages: list[str]) -> dict:
    """Check if page language matches any expected code."""
    expected = [e.lower() for e in expected_languages]
    candidates: list[str] = []

    for key in ("html_lang", "meta_lang", "og_locale"):
        raw = (signals.get(key) or "").strip().lower()
        if raw:
            candidates.append(raw)
            # og:locale often ru_RU
            candidates.append(raw.split("-")[0].split("_")[0])

    path = _norm(signals.get("pathname") or "")
    path_bits = [b for b in path.split("/") if b]
    candidates.extend(path_bits[:2])

    # URL host/path already handled via path; also scan short body markers
    body = _norm(signals.get("body_sample") or "")

    matched: list[str] = []
    for exp in expected:
        for c in candidates:
            if c == exp or c.startswith(exp + "-") or c.startswith(exp + "_"):
                matched.append(exp)
                break
        else:
            # path segment /uz /ru /bn
            if f"/{exp}" in path or path.endswith(exp):
                matched.append(exp)
            # weak content fallback for locale words is avoided to reduce false positives

    matched = list(dict.fromkeys(matched))
    ok = bool(matched)
    return {
        "ok": ok,
        "expected": expected_languages,
        "matched": matched,
        "observed": {
            "html_lang": signals.get("html_lang"),
            "meta_lang": signals.get("meta_lang"),
            "og_locale": signals.get("og_locale"),
            "pathname": signals.get("pathname"),
        },
        "detail": (
            f"matched={matched}" if ok else f"no expected language in {expected}; saw {candidates[:8]}"
        ),
        # body kept only for debugging size control in store
        "_body_len": len(body),
    }


_ISO_IN_PARENS = re.compile(r"\(([A-Z]{3})\)\s*$")
_ISO_CODE = re.compile(r"\b([A-Z]{3})\b")

# Registration multiselect (user HTML): selected value under .select-value__content
DEFAULT_CURRENCY_LOCATORS = [
    ".registration-field-select .multiselect__single .select-value__content",
    ".registration-fields__item.registration-field-select .select-value__content",
    ".ui-field-select.registration-field-select .multiselect__single",
    ".registration-field-select .select-value__content .ui-caption",
    ".ui-field-select .multiselect__single .select-value__content",
]


def extract_registration_currency(
    page: Page,
    *,
    currency_locator: str = "",
) -> dict:
    """
    Read the currency currently selected on registration form.

    Primary source (your DOM):
      .registration-field-select .multiselect__single .select-value__content
      → text like \"Российский рубль (RUB)\"

    Optional: currency_locator in config overrides / goes first.
    """
    locators: list[str] = []
    if currency_locator:
        locators.append(currency_locator)
    locators.extend(DEFAULT_CURRENCY_LOCATORS)

    raw = page.evaluate(
        """(locators) => {
          const clean = (s) => (s || '').replace(/\\s+/g, ' ').trim();
          const pickIso = (text) => {
            const t = clean(text);
            if (!t) return null;
            let m = t.match(/\\(([A-Z]{3})\\)\\s*$/);
            if (m) return { code: m[1], label: t };
            m = t.match(/^([A-Z]{3})$/);
            if (m) return { code: m[1], label: t };
            return null;
          };

          // 1) CSS locators: config first, then known multiselect selectors
          for (const sel of locators) {
            if (!sel) continue;
            const el = document.querySelector(sel);
            if (!el) continue;
            const text = clean(el.innerText || el.textContent || el.value || '');
            const parsed = pickIso(text);
            if (parsed) {
              return {
                code: parsed.code,
                label: parsed.label || text,
                source: 'locator:' + sel,
              };
            }
            if (text) {
              return { code: '', label: text, source: 'locator_raw:' + sel };
            }
          }

          // 2) registration field block with label + multiselect value
          const blocks = document.querySelectorAll(
            '.registration-field-select, .field-base.ui-field-select, .ui-field-select.registration-fields__item'
          );
          for (const block of blocks) {
            const valueEl = block.querySelector(
              '.multiselect__single .select-value__content, .select-value__content, .multiselect__single'
            );
            const valueText = clean(valueEl && (valueEl.innerText || valueEl.textContent) || '');
            const parsed = pickIso(valueText);
            if (parsed) {
              const lab = clean(
                (block.querySelector('.field-base-label-text__caption') || {}).innerText || ''
              );
              return {
                code: parsed.code,
                label: parsed.label,
                source: 'registration_field_select' + (lab ? '|' + lab : ''),
              };
            }
          }

          // 3) fallback near currency labels
          const labelRe = /выберите валюту|select(?:\\s+your)?\\s+currency|sélectionnez la devise|currency|devise|валют|عملة/i;
          for (const lab of document.querySelectorAll(
            '.field-base-label-text__caption, .field-base__label, span, div'
          )) {
            const lt = clean(lab.innerText || '');
            if (!lt || lt.length > 80 || !labelRe.test(lt)) continue;
            const root = lab.closest('.field-base, .registration-field-select, .ui-field-select');
            if (!root) continue;
            const valueEl = root.querySelector(
              '.multiselect__single .select-value__content, .select-value__content, .multiselect__single'
            );
            const text = clean(valueEl && (valueEl.innerText || valueEl.textContent) || '');
            const parsed = pickIso(text);
            if (parsed) {
              return { code: parsed.code, label: parsed.label, source: 'near_label' };
            }
          }

          return { code: '', label: '', source: 'not_found' };
        }""",
        locators,
    )

    code = (raw.get("code") or "").strip().upper()
    label = (raw.get("label") or "").strip()
    source = raw.get("source") or "not_found"

    if not code and label:
        m = _ISO_IN_PARENS.search(label) or _ISO_CODE.search(label)
        if m:
            code = m.group(1).upper()

    return {
        "code": code,
        "label": label,
        "source": source,
        "found": bool(code),
    }


def check_currency(
    page: Page,
    expected_currency: str,
    *,
    currency_locator: str = "",
) -> dict:
    """
    Assert registration form shows exactly expected_currency (ISO-4217).

    observed — what UI currently displays; expected — one code from config.
    """
    expected = (expected_currency or "").strip().upper()
    observed = extract_registration_currency(page, currency_locator=currency_locator)
    code = observed.get("code") or ""
    label = observed.get("label") or ""
    ok = bool(expected) and code == expected

    if not expected:
        detail = "expected_currency not configured"
        ok = False
    elif not code:
        detail = f"currency field not found on registration (expected {expected})"
    elif ok:
        detail = f"observed={code} ({label}) via {observed.get('source')}"
    else:
        detail = (
            f"expected={expected}, observed={code or '—'} "
            f"label={label!r} via {observed.get('source')}"
        )

    return {
        "ok": ok,
        "expected": expected,
        "observed": code,
        "observed_label": label,
        "source": observed.get("source"),
        "detail": detail,
        # keep key for older report fields
        "matched": [code] if code else [],
    }


def detect_redirect(
    start_url: str,
    final_url: str,
    redirect_chain: list[str],
    url_hints: list[str],
) -> dict:
    """
    Redirect / final-URL correctness.

    Pass if:
      - final URL contains any geo url_hint, OR
      - path/host looks like expected locale
    Also records whether a redirect happened at all.
    """
    final = (final_url or "").strip()
    start = (start_url or "").strip()
    chain = redirect_chain or []
    final_l = final.lower()
    start_l = start.lower()

    redirected = bool(chain) or (final_l.rstrip("/") != start_l.rstrip("/"))

    hint_hits = [h for h in url_hints if h and h.lower() in final_l]
    ok = bool(hint_hits)

    # If no hints configured, treat "page opened" as enough for redirect section
    if not url_hints:
        ok = True

    parsed = urlparse(final)
    return {
        "ok": ok,
        "redirected": redirected,
        "start_url": start,
        "final_url": final,
        "redirect_count": max(len(chain), 1 if redirected else 0),
        "redirect_chain": chain[:12],
        "hint_hits": hint_hits,
        "host": parsed.netloc,
        "path": parsed.path,
        "detail": (
            f"hints matched: {hint_hits}"
            if ok
            else f"final URL does not match expected geo hints {url_hints}: {final}"
        ),
    }


def overall_status(
    opened: bool,
    redirect_ok: bool,
    language_ok: bool,
    currency_ok: bool,
) -> str:
    if not opened:
        return "FAIL"
    checks = [redirect_ok, language_ok, currency_ok]
    if all(checks):
        return "PASS"
    if any(checks):
        return "PARTIAL"
    return "FAIL"
