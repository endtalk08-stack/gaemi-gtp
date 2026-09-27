"""Marketaux HTTP provider.

This module only retrieves raw Marketaux data. It intentionally has no UI or
news classification rules, so the provider can be replaced after the test.
"""

import json
import os
import urllib.parse
import urllib.request


MARKETAUX_NEWS_URL = "https://api.marketaux.com/v1/news/all"


class MarketauxConfigurationError(RuntimeError):
    """Raised when the server-side Marketaux token has not been configured."""


class MarketauxRequestError(RuntimeError):
    """Raised when Marketaux does not return a usable response."""


def fetch_news(*, search="", countries="", industries="", limit=3):
    """Return the raw Marketaux news payload without exposing the API token."""
    api_token = os.environ.get("MARKETAUX_API_TOKEN", "").strip()
    if not api_token:
        raise MarketauxConfigurationError("MARKETAUX_API_TOKEN is not configured")

    params = {
        "api_token": api_token,
        "language": "en",
        "filter_entities": "true",
        "group_similar": "true",
        "sort": "published_at",
        "limit": max(1, min(int(limit or 3), 3)),
    }
    if str(search or "").strip():
        params["search"] = str(search).strip()
    if str(countries or "").strip():
        params["countries"] = str(countries).strip()
    if str(industries or "").strip():
        params["industries"] = str(industries).strip()

    request_url = f"{MARKETAUX_NEWS_URL}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(
        request_url,
        headers={"Accept": "application/json", "User-Agent": "gaemiGTP-news-test/1.0"},
    )

    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise MarketauxRequestError("Marketaux request failed") from exc

    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise MarketauxRequestError("Marketaux returned an invalid payload")
    return payload
