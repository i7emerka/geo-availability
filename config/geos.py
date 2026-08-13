"""Geo profiles: expected locale, currency, URL hints, browser fingerprint."""

from __future__ import annotations

# code → human label and expectations for geo-availability checks
#
# expected_currency — один ISO-код, который ДОЛЖЕН быть выбран на /registration.
# Наблюдаемое значение читается с UI (поле валюты), не «подбирается» по тексту.
# Опционально: currency_locator — CSS-селектор поля выбранной валюты (если дадите точный).

GEOS: dict[str, dict] = {
    "UZ": {
        "name": "Uzbekistan",
        "browser_locale": "uz-UZ",
        "accept_language": "uz-UZ,uz;q=0.9,ru;q=0.8,en;q=0.5",
        "timezone_id": "Asia/Tashkent",
        "geolocation": {"latitude": 41.2995, "longitude": 69.2401},
        "languages": ["uz", "ru"],
        "expected_currency": "UZS",
        # Selected value in registration multiselect (same structure on all geos)
        "currency_locator": ".registration-field-select .multiselect__single .select-value__content",
        "url_hints": ["/uz", "uz.", ".uz/", "fastpari-92371.bar"],
        "start_urls": [],
        "preferred_urls": [
            "https://fastpari-92371.bar/uz",
            "https://fastpari.com/uz",
        ],
    },
    "BD": {
        "name": "Bangladesh",
        "browser_locale": "bn-BD",
        "accept_language": "bn-BD,bn;q=0.9,en;q=0.7",
        "timezone_id": "Asia/Dhaka",
        "geolocation": {"latitude": 23.8103, "longitude": 90.4125},
        "languages": ["bn", "en"],
        "expected_currency": "BDT",
        "currency_locator": ".registration-field-select .multiselect__single .select-value__content",
        "url_hints": ["/bn", "bn.", "/bd", "bangladesh"],
        "start_urls": [],
        "preferred_urls": [
            "https://fastpari.com/bn",
            "https://fastpari.com/en",
        ],
    },
    "RU": {
        "name": "Russia",
        "use_local_ip": True,
        "browser_locale": "ru-RU",
        "accept_language": "ru-RU,ru;q=0.9,en-US;q=0.5,en;q=0.4",
        "timezone_id": "Europe/Moscow",
        "geolocation": {"latitude": 55.7558, "longitude": 37.6173},
        "languages": ["ru"],
        "expected_currency": "RUB",
        "currency_locator": ".registration-field-select .multiselect__single .select-value__content",
        "url_hints": ["/ru", "ru.", "fastpari-5041.pro"],
        "start_urls": ["https://fastpari.com"],
        "preferred_urls": [],
    },
    "EG": {
        "name": "Egypt",
        "browser_locale": "ar-EG",
        "accept_language": "ar-EG,ar;q=0.9,en;q=0.7",
        "timezone_id": "Africa/Cairo",
        "geolocation": {"latitude": 30.0444, "longitude": 31.2357},
        "languages": ["ar", "en"],
        "expected_currency": "EGP",
        "currency_locator": ".registration-field-select .multiselect__single .select-value__content",
        "url_hints": ["/ar", "/eg", "eg.", "egypt", "/en"],
        "start_urls": [],
        "preferred_urls": [
            "https://fastpari.com/ar",
            "https://fastpari.com/eg",
            "https://fastpari.com/en",
        ],
    },
    "CI": {
        "name": "Cote d'Ivoire",
        "browser_locale": "fr-CI",
        "accept_language": "fr-CI,fr;q=0.9,en;q=0.6",
        "timezone_id": "Africa/Abidjan",
        "geolocation": {"latitude": 5.3600, "longitude": -4.0083},
        "languages": ["fr", "en"],
        "expected_currency": "XOF",
        "currency_locator": ".registration-field-select .multiselect__single .select-value__content",
        "url_hints": ["/fr", "/ci", "ci.", "ivoire", "ivory", "fastpari-87359.pro", "/en"],
        "start_urls": [],
        "preferred_urls": [
            "https://fastpari-87359.pro/fr",
            "https://fastpari.com/fr",
            "https://fastpari.com/ci",
            "https://fastpari.com/en",
        ],
    },
}


def get_geo(code: str) -> dict:
    key = code.strip().upper()
    if key not in GEOS:
        raise KeyError(f"Unknown geo: {code}. Known: {', '.join(GEOS)}")
    return GEOS[key]


def list_geo_codes() -> list[str]:
    return list(GEOS.keys())


def browser_context_options(geo: dict) -> dict:
    """Playwright new_context / persistent kwargs for a geo profile."""
    locale = geo.get("browser_locale") or "en-US"
    options: dict = {
        "locale": locale,
        "timezone_id": geo.get("timezone_id") or "UTC",
        "ignore_https_errors": True,
        "viewport": {"width": 1366, "height": 768},
        "extra_http_headers": {
            "Accept-Language": geo.get("accept_language")
            or f"{locale},{locale.split('-')[0]};q=0.9,en;q=0.5",
        },
    }
    geo_loc = geo.get("geolocation")
    if geo_loc:
        options["geolocation"] = geo_loc
        options["permissions"] = ["geolocation"]
    return options
