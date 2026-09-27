"""Minimal DeepL translation provider used only by the overseas-news test."""

import json
import os
import urllib.parse
import urllib.request


DEEPL_FREE_URL = "https://api-free.deepl.com/v2/translate"
DEEPL_PRO_URL = "https://api.deepl.com/v2/translate"


def translate_to_korean(text):
    text = str(text or "").strip()
    api_key = os.environ.get("DEEPL_API_KEY", "").strip().strip("'\"")
    if not text or not api_key:
        return ""

    # DeepL Free keys conventionally end in :fx. Pro keys use the regular host.
    url = DEEPL_FREE_URL if api_key.endswith(":fx") else DEEPL_PRO_URL
    body = urllib.parse.urlencode({"text": text, "target_lang": "KO"}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"DeepL-Auth-Key {api_key}",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "gaemiGTP-news-translation-test/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
        translations = payload.get("translations") or []
        return str(translations[0].get("text") or "").strip() if translations else ""
    except Exception as exc:
        print(f"[provider:deepl] translation failed: {type(exc).__name__}: {exc}")
        return ""
