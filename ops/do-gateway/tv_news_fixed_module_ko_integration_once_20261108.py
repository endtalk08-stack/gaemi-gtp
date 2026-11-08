"""Run exact fixed TradingView detail module in memory, one real API call.

No operating-module import, no on-disk cache, no service restart, no R2/DB writes.
The candidate module source is embedded from the review branch, not installed.
"""
import hashlib
import io
import json
import os
import re
import subprocess
import types
import urllib.error
import urllib.request

UNITS = ("gaemigtp-news.service", "gaemigtp-tradingview-news.service")
def inactive(unit):
    p = subprocess.run(("systemctl", "is-active", unit), capture_output=True,
                       text=True, timeout=6, check=False)
    return p.stdout.strip() == "inactive"
if any(not inactive(unit) for unit in UNITS):
    raise SystemExit("KO_DETAIL_INTEGRATION_ABORT_WORKER_RUNNING")
key = os.environ.get("TRADINGVIEW_API_KEY", "").strip()
if not key:
    raise SystemExit("KO_DETAIL_INTEGRATION_ABORT_MISSING_KEY")

candidate_source = "\"\"\"TradingView Data API article-detail enrichment.\n\nUses the IDs already returned by the US news bundle (no additional list request).\nNo network call unless enrich_articles() is explicitly given a positive max_requests.\nThe API's detail response fields can differ by provider; never fabricate text.\n\"\"\"\nfrom __future__ import annotations\n\nimport json\nimport os\nimport re\nimport urllib.error\nimport urllib.parse\nimport urllib.request\n\nDETAIL_BASE_URL = \"https://api.tradingviewapi.com/api/news/\"\nMAX_DETAIL_CHARS = 100_000\nMAX_FIELD_CHARS = 10_000\n\n\ndef _text(value):\n    return \" \".join(value.split()).strip() if isinstance(value, str) else \"\"\n\n\ndef _detail_id(article):\n    value = article.get(\"id\") or article.get(\"newsId\")\n    if value is None:\n        return \"\"\n    value = str(value).strip()\n    return value if value and len(value) <= 300 else \"\"\n\n\ndef _get_detail(news_id, key, opener):\n    url = DETAIL_BASE_URL + urllib.parse.quote(news_id, safe=\"\") + \"?lang=ko\"\n    request = urllib.request.Request(url, headers={\n        \"Authorization\": \"Bearer \" + key,\n        \"Accept\": \"application/json\",\n        \"User-Agent\": \"gaemiGTP-news-worker/1.0\",\n    })\n    with opener(request, timeout=10) as response:\n        payload = json.loads(response.read(2_000_000).decode(\"utf-8\"))\n    if not isinstance(payload, dict) or payload.get(\"success\") is not True:\n        raise ValueError(\"invalid_news_detail_response\")\n    data = payload.get(\"data\")\n    if not isinstance(data, dict):\n        raise ValueError(\"missing_news_detail_data\")\n    return data\n\n\ndef _candidate_objects(data):\n    \"\"\"Find known wrappers without assuming one fixed provider response shape.\"\"\"\n    yield data\n    for key in (\"item\", \"news\", \"story\", \"article\"):\n        value = data.get(key)\n        if isinstance(value, dict):\n            yield value\n\n\ndef _read_string(value):\n    if isinstance(value, str):\n        return value.strip()\n    if isinstance(value, dict):\n        for key in (\"text\", \"plainText\", \"html\", \"content\", \"value\"):\n            if isinstance(value.get(key), str):\n                return value[key].strip()\n    if isinstance(value, list):\n        parts = [_read_string(item) for item in value]\n        return \"\\n\".join(part for part in parts if part).strip()\n    return \"\"\n\n\ndef _first_field(data, fields, limit):\n    for obj in _candidate_objects(data):\n        for field in fields:\n            value = _read_string(obj.get(field))\n            if value:\n                return value[:limit]\n    return \"\"\n\n\ndef _ast_body(value):\n    \"\"\"Read TradingView astDescription text nodes in document order.\n\n    AST paragraphs commonly contain string children rather than text fields.\n    URL targets and structural node names are not part of article text.\n    \"\"\"\n    if isinstance(value, str):\n        return value\n    if isinstance(value, list):\n        return \"\".join(_ast_body(child) for child in value)\n    if not isinstance(value, dict):\n        return \"\"\n\n    children = value.get(\"children\")\n    if isinstance(children, list):\n        text = _ast_body(children)\n    else:\n        text = next((\n            value[field] for field in (\"text\", \"plainText\", \"value\", \"content\")\n            if isinstance(value.get(field), str)\n        ), \"\")\n        if not text and value.get(\"type\") == \"url\":\n            params = value.get(\"params\")\n            if isinstance(params, dict):\n                text = _text(params.get(\"linkText\"))\n\n    if value.get(\"type\") in (\"p\", \"li\", \"h1\", \"h2\", \"h3\", \"blockquote\"):\n        return text.strip() + \"\\n\\n\" if text.strip() else \"\"\n    return text\n\n\ndef _extract_detail(data):\n    body = _first_field(data, (\n        \"body\", \"articleBody\", \"article_body\", \"bodyText\",\n        \"fullText\", \"full_text\", \"content\", \"text\", \"storyText\",\n    ), MAX_DETAIL_CHARS)\n    if not body:\n        for obj in _candidate_objects(data):\n            ast_body = _ast_body(obj.get(\"astDescription\"))\n            if ast_body.strip():\n                body = re.sub(r\"\\n{3,}\", \"\\n\\n\", re.sub(r\"[ \\t]+\", \" \", ast_body)).strip()[:MAX_DETAIL_CHARS]\n                break\n    return {\n        \"detail_body\": body,\n        \"detail_summary\": _first_field(data, (\n            \"summary\", \"shortSummary\", \"short_summary\", \"abstract\",\n        ), MAX_FIELD_CHARS),\n    }\n\n\ndef enrich_articles(items, *, max_requests=0, opener=None, api_key=None):\n    \"\"\"Return (new_items, stats). Positive budget is required for API calls.\n\n    Details are fetched only once for IDs not previously checked.\n    A 429 stops the run instead of retrying, to prevent overspending.\n    Raw article bodies remain in the short-lived private worker cache; publication requires separate rights approval.\n    Headline-only rights are recorded separately from whether the detail endpoint contains text.\n    \"\"\"\n    budget = max(0, int(max_requests))\n    key = (api_key if api_key is not None else os.getenv(\"TRADINGVIEW_API_KEY\", \"\")).strip()\n    opener = opener or urllib.request.urlopen\n    rows = [{k: v for k, v in item.items() if k not in (\"shortDescription\", \"short_description\", \"description\", \"detail_description\", \"excerpt\")}\n            for item in items if isinstance(item, dict)]\n    stats = {\"requested\": 0, \"bodies\": 0, \"summarized\": 0, \"blocked\": 0, \"failed\": 0, \"skipped\": 0}\n    if not budget or not key:\n        stats[\"skipped\"] = len(rows)\n        return rows, stats\n    done = set()\n    halted = False\n    for row in rows:\n        article_id = _detail_id(row)\n        if (halted or stats[\"requested\"] >= budget or not article_id\n                or article_id in done or row.get(\"detail_checked\")):\n            stats[\"skipped\"] += 1\n            continue\n        # A headline-only listing does NOT tell us whether the separate\n        # detail endpoint has content. Query the detail endpoint, but do not\n        # expose its response publicly unless rights have been verified.\n        done.add(article_id)\n        stats[\"requested\"] += 1\n        try:\n            data = _get_detail(article_id, key, opener)\n            values = _extract_detail(data)\n            # A provider's detail-level restriction takes precedence.\n            detail_permission = next((\n                item.get(\"permission\") for item in _candidate_objects(data)\n                if item.get(\"permission\") is not None\n            ), None)\n            if detail_permission is not None:\n                row[\"detail_permission\"] = detail_permission\n            if detail_permission == \"headline\":\n                stats[\"blocked\"] += 1\n            # Keep retrieved material private. Publication is separate.\n            for field, metric in (\n                (\"detail_body\", \"bodies\"),\n                (\"detail_summary\", \"summarized\"),\n            ):\n                if values[field]:\n                    row[field] = values[field]\n                    stats[metric] += 1\n            row[\"detail_checked\"] = \"content\" if any(values.values()) else \"no_content\"\n        except urllib.error.HTTPError as exc:\n            stats[\"failed\"] += 1\n            if exc.code in (401, 402, 403, 429):\n                halted = True\n        except (ValueError, TypeError, UnicodeError, OSError):\n            stats[\"failed\"] += 1\n    return rows, stats\n"
assert "def _ast_body(value):" in candidate_source
assert ' + "'?lang=ko'" + ' in candidate_source
source_hash = hashlib.sha256(candidate_source.encode("utf-8")).hexdigest()
candidate = types.ModuleType("gaemi_candidate_tv_ko_detail")
exec(compile(candidate_source, "<fixed-branch-tradingview-news-detail>", "exec"),
     candidate.__dict__)

calls = []
observed = {}
def open_exactly_once(request, timeout):
    if calls:
        raise AssertionError("KO_DETAIL_ABORT_MORE_THAN_ONE_REQUEST")
    calls.append(request.full_url)
    if not request.full_url.endswith("?lang=ko"):
        raise AssertionError("KO_DETAIL_ABORT_WRONG_LANGUAGE")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        observed["http_status"] = response.status
        raw = response.read(2_000_000)
    payload = json.loads(raw.decode("utf-8"))
    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    observed.update({
        "response_language": str(data.get("language") or ""),
        "description_chars": len(str(data.get("shortDescription") or "")),
        "ast_present": isinstance(data.get("astDescription"), dict),
        "ast_child_count": len((data.get("astDescription") or {}).get("children") or [])
                           if isinstance(data.get("astDescription"), dict) else None,
        "provider": str((data.get("provider") or {}).get("name") or "")
                    if isinstance(data.get("provider"), dict) else "",
    })
    observed["description"] = str(data.get("shortDescription") or "")
    return io.BytesIO(raw)

print("KO_DETAIL_INTEGRATION_BUDGET=1;LANG=ko;RETRIES=0", flush=True)
nid = "tag:reuters.com,2026:newsml_L3N46N1G1:0"
try:
    rows, stats = candidate.enrich_articles(
        [{"id": nid, "title": "연준 정책입안자들, 호조인 고용 보고서 발표 후 금리 인상 검토",
          "permission": "headline"}],
        max_requests=1, api_key=key, opener=open_exactly_once,
    )
except Exception as exc:
    print("KO_DETAIL_INTEGRATION_STOP_EXCEPTION=" + type(exc).__name__, flush=True)
    raise SystemExit(2)

article = rows[0]
body = str(article.get("detail_body") or "")
description = observed.pop("description", "")
report = {
    "source": "exact-source-from-fix-branch",
    "candidate_sha256": source_hash,
    "calls": len(calls),
    "stats": stats,
    **observed,
    "body_chars": len(body),
    "body_hangul_chars": len(re.findall("[가-힣]", body)),
    "description_is_separate": description != body,
    "detail_status": article.get("detail_checked"),
    "permission": article.get("detail_permission"),
    "provider_summary_chars": len(str(article.get("detail_summary") or "")),
    "public_body_output": False,
    "operating_code_modified": False,
    "cache_writes": 0,
    "r2_writes": 0,
    "db_writes": 0,
}
print("KO_DETAIL_INTEGRATION_RESULT=" + json.dumps(report, ensure_ascii=False, separators=(",", ":")), flush=True)
if (len(calls) != 1 or stats.get("requested") != 1 or stats.get("bodies") != 1
    or not body or observed.get("response_language") != "ko"
    or len(re.findall("[가-힣]", body)) < 100
    or body == description or article.get("detail_checked") != "content"):
    raise SystemExit("KO_DETAIL_INTEGRATION_FAILED")
if any(not inactive(unit) for unit in UNITS):
    raise SystemExit("KO_DETAIL_INTEGRATION_ABORT_WORKER_STATE_CHANGED")
print("KO_DETAIL_INTEGRATION_PASS_WITH_WORKERS_STOPPED", flush=True)
