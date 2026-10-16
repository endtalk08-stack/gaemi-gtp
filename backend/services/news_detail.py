"""Second-pass article detail reader for already-selected central news.

The first-pass feed/scoring pipeline remains unchanged.  This module reads only
the final storyboard candidates (normally <= 3), extracts a bounded amount of
article text, and returns it for fact re-extraction.  Raw article text is never
returned to the frontend.
"""

import html
import os
import json
import re
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser

from backend.analysis.news.catalog import STOCK_UNIVERSE


REQUEST_TIMEOUT = 1.6
NEWS_WORKER_REQUEST_TIMEOUT = 3.0  # Only the DigitalOcean worker; Render stays at 1.6s.


def _article_request_timeout():
    # Bounded increase for the dedicated news worker, without changing
    # HTTPS validation, retrying 403 responses, or slowing the Render frontend.
    return (NEWS_WORKER_REQUEST_TIMEOUT
            if os.environ.get("GAEMIGTP_NEWS_WORKER") == "1"
            else REQUEST_TIMEOUT)

MAX_RESPONSE_BYTES = 350_000
MAX_DETAIL_TEXT_CHARS = 5_000
_CACHE_TTL = 300
_CACHE = {}
_CACHE_LOCK = threading.Lock()


def _clean_text(value):
    text = html.unescape(str(value or ""))
    return re.sub(r"\s+", " ", text).strip()


def _bounded_text(value, limit=MAX_DETAIL_TEXT_CHARS):
    text = _clean_text(value)
    if len(text) <= limit:
        return text
    shortened = text[:limit].rsplit(" ", 1)[0].strip()
    return shortened or text[:limit].strip()


def _find_json_article_body(value):
    if isinstance(value, dict):
        body = value.get("articleBody")
        if isinstance(body, str) and body.strip():
            return body
        for nested in value.values():
            found = _find_json_article_body(nested)
            if found:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = _find_json_article_body(nested)
            if found:
                return found
    return ""


class _ArticleHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.article_depth = 0
        self.main_depth = 0
        self.current_paragraph = None
        self.current_preferred = False
        self.preferred_paragraphs = []
        self.all_paragraphs = []
        self.meta_description = ""
        self.in_jsonld = False
        self.jsonld_chunks = []
        self.json_article_body = ""

    def handle_starttag(self, tag, attrs):
        tag = str(tag or "").lower()
        attrs_dict = {str(key or "").lower(): value for key, value in attrs}
        if tag == "article":
            self.article_depth += 1
        elif tag == "main":
            self.main_depth += 1
        elif tag == "meta":
            name = str(attrs_dict.get("name") or attrs_dict.get("property") or "").lower()
            if name in {"description", "og:description", "twitter:description"} and not self.meta_description:
                self.meta_description = _clean_text(attrs_dict.get("content"))
        elif tag == "p":
            self.current_paragraph = []
            self.current_preferred = bool(self.article_depth or self.main_depth)
        elif tag == "script":
            script_type = str(attrs_dict.get("type") or "").lower()
            self.in_jsonld = script_type == "application/ld+json"
            if self.in_jsonld:
                self.jsonld_chunks = []

    def handle_data(self, data):
        if self.current_paragraph is not None:
            self.current_paragraph.append(str(data or ""))
        if self.in_jsonld:
            self.jsonld_chunks.append(str(data or ""))

    def handle_endtag(self, tag):
        tag = str(tag or "").lower()
        if tag == "p" and self.current_paragraph is not None:
            paragraph = _clean_text(" ".join(self.current_paragraph))
            if len(paragraph) >= 30:
                self.all_paragraphs.append(paragraph)
                if self.current_preferred:
                    self.preferred_paragraphs.append(paragraph)
            self.current_paragraph = None
            self.current_preferred = False
        elif tag == "script" and self.in_jsonld:
            raw = "".join(self.jsonld_chunks).strip()
            if raw and not self.json_article_body:
                try:
                    self.json_article_body = _clean_text(_find_json_article_body(json.loads(raw)))
                except Exception:
                    pass
            self.in_jsonld = False
            self.jsonld_chunks = []
        elif tag == "article" and self.article_depth:
            self.article_depth -= 1
        elif tag == "main" and self.main_depth:
            self.main_depth -= 1


def _extract_article_text_with_source(payload, charset="utf-8"):
    """Return extracted text and its HTML evidence source."""
    if not payload:
        return "", "fetch_failed"
    try:
        source = payload.decode(charset or "utf-8", errors="replace")
    except Exception:
        source = payload.decode("utf-8", errors="replace")

    parser = _ArticleHTMLParser()
    try:
        parser.feed(source)
        parser.close()
    except Exception:
        return "", "fetch_failed"

    candidates = (
        ("jsonld_article_body", parser.json_article_body),
        ("article_or_main_paragraphs", " ".join(parser.preferred_paragraphs)),
        ("all_page_paragraphs", " ".join(parser.all_paragraphs)),
        ("meta_description", parser.meta_description),
    )
    for kind, candidate in candidates:
        cleaned = _bounded_text(candidate)
        if len(cleaned) >= 80:
            return cleaned, kind
    fallback = _bounded_text(parser.meta_description)
    return fallback, "meta_description" if fallback else "fetch_failed"


def extract_article_text(payload, charset="utf-8"):
    """Preserve the text-only API used by existing consumers and tests."""
    return _extract_article_text_with_source(payload, charset=charset)[0]


def _read_url(url, with_source=False):
    now = time.time()
    with _CACHE_LOCK:
        cached = _CACHE.get(url)
        if cached and now - cached[0] <= _CACHE_TTL:
            text = cached[1]
            kind = cached[2] if len(cached) > 2 else "unknown"
            return {"text": text, "source": kind} if with_source else text

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "gaemiGTP/1.0",
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5",
        },
    )
    text, kind = "", "fetch_failed"
    try:
        with urllib.request.urlopen(request, timeout=_article_request_timeout()) as response:
            content_type = str(response.headers.get("Content-Type") or "").lower()
            if "html" not in content_type and "xhtml" not in content_type:
                return {"text": "", "source": "fetch_failed"} if with_source else ""
            charset = response.headers.get_content_charset() or "utf-8"
            payload = response.read(MAX_RESPONSE_BYTES)
        text, kind = _extract_article_text_with_source(payload, charset=charset)
    except Exception as exc:
        print(
            f"[news detail] failed url={url}: {type(exc).__name__}: {exc}",
            flush=True,
        )

    with _CACHE_LOCK:
        _CACHE[url] = (now, text, kind)
    return {"text": text, "source": kind} if with_source else text


_REGION_ALIASES = (
    ("미국", ("united states", "u.s.", "u.s ", "미국")),
    ("한국", ("south korea", "republic of korea", "한국", "대한민국")),
    ("중국", ("china", "중국")),
    ("일본", ("japan", "일본")),
    ("유럽", ("europe", "european union", "eu ", "유럽")),
    ("영국", ("united kingdom", "u.k.", "uk ", "영국")),
    ("독일", ("germany", "독일")),
    ("프랑스", ("france", "프랑스")),
    ("인도", ("india", "인도")),
    ("대만", ("taiwan", "대만", "타이완")),
    ("캐나다", ("canada", "캐나다")),
    ("멕시코", ("mexico", "멕시코")),
    ("중동", ("middle east", "중동")),
)

_PRODUCT_FACT_BLOCKLIST = {
    "미국", "한국", "중국", "일본", "유럽", "영국", "독일", "프랑스",
    "인도", "대만", "캐나다", "멕시코", "중동",
    "SEC", "FDA", "코스피", "코스닥", "나스닥", "뉴욕증시", "WTI",
}


def _company_alias_positions(text):
    lower = str(text or "").lower()
    matches = []
    seen = set()
    for stocks in STOCK_UNIVERSE.values():
        for canonical, aliases in stocks.items():
            for alias in (canonical, *(aliases or [])):
                token = str(alias or "").strip().lower()
                if not token:
                    continue
                if re.fullmatch(r"[a-z0-9.]+", token) and len(token.replace(".", "")) <= 5:
                    pattern = rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])"
                    positions = [match.start() for match in re.finditer(pattern, lower)]
                else:
                    positions = []
                    start = 0
                    while True:
                        index = lower.find(token, start)
                        if index < 0:
                            break
                        positions.append(index)
                        start = index + max(1, len(token))
                for position in positions:
                    key = (canonical, position)
                    if key not in seen:
                        seen.add(key)
                        matches.append((canonical, position))
    return matches


def _extract_regions(text):
    lower = f" {str(text or '').lower()} "
    regions = []
    for canonical, aliases in _REGION_ALIASES:
        if any(alias in lower for alias in aliases):
            regions.append(canonical)
    return regions[:3]


def _extract_amount(text):
    source = str(text or "")
    patterns = (
        r"\$\s*\d[\d,.]*(?:\s*(?:trillion|billion|million|bn|m))?",
        r"\d[\d,.]*\s*(?:trillion|billion|million)\s*(?:u\.s\.\s*)?dollars?",
        r"\d[\d,.]*\s*(?:조|억|만)?\s*달러",
        r"(?:\d{1,4}(?:,\d{3})*|\d+(?:\.\d+)?)\s*조(?:\s*(?:\d+천)?\s*\d{1,4}(?:,\d{3})*\s*억)?\s*원?",
        r"(?:\d+천\s*)?\d{1,4}(?:,\d{3})*\s*억원",
    )
    candidates = []
    for pattern in patterns:
        for match in re.finditer(pattern, source, flags=re.IGNORECASE):
            candidates.append((match.start(), _clean_text(match.group(0))))
    if not candidates:
        return ""

    event_positions = [
        match.start()
        for match in re.finditer(
            r"contract|agreement|deal|investment|invest|acquisition|acquire|"
            r"계약|협약|공급|투자|인수|매입",
            source,
            flags=re.IGNORECASE,
        )
    ]
    if event_positions:
        candidates.sort(key=lambda pair: min(abs(pair[0] - pos) for pos in event_positions))
    else:
        candidates.sort(key=lambda pair: pair[0])
    return candidates[0][1]


def _extract_key_numbers(text, amount=""):
    source = str(text or "")
    patterns = (
        r"(?<![\d.])\d+(?:\.\d+)?\s*%",
        r"(?<![\d.])\d+(?:\.\d+)?\s*(?:GW|MW|KW|TW|TB|GB|PB)\b",
        r"(?<![\d.])\d+(?:\.\d+)?\s*(?:million|billion|trillion)\s+"
        r"(?:users|customers|devices|shares|units)\b",
        r"(?<![\d.])\d+(?:\.\d+)?\s*-\s*year\b",
        r"(?<![\d.])\d+(?:\.\d+)?-year\b",
        r"(?<![\d.])\d+(?:\.\d+)?\s*(?:명|개|건|대|배)\b",
        r"(?<![\d.])\d+(?:\.\d+)?\s*년\b",
    )
    values = []
    for pattern in patterns:
        for match in re.finditer(pattern, source, flags=re.IGNORECASE):
            value = _clean_text(match.group(0))
            if value.endswith("년"):
                try:
                    numeric = float(re.search(r"\d+(?:\.\d+)?", value).group(0))
                except Exception:
                    numeric = 0
                if 1900 <= numeric <= 2100:
                    continue
            if amount and value.replace(" ", "").lower() in amount.replace(" ", "").lower():
                continue
            if value and value not in values:
                values.append(value)
            if len(values) >= 4:
                return values
    return values


def _extract_counterparty(text, stock_name):
    source = str(text or "")
    lower = source.lower()
    contract_positions = [
        match.start()
        for match in re.finditer(
            r"contract|agreement|deal|partnership|계약|협약|공급계약|공급 계약",
            lower,
            flags=re.IGNORECASE,
        )
    ]
    if not contract_positions:
        return ""

    selected = str(stock_name or "").strip()
    candidates = [
        (canonical, position)
        for canonical, position in _company_alias_positions(source)
        if canonical != selected
    ]
    if candidates:
        canonical, position = min(
            candidates,
            key=lambda pair: min(abs(pair[1] - event_pos) for event_pos in contract_positions),
        )
        if min(abs(position - event_pos) for event_pos in contract_positions) <= 220:
            return canonical

    english_patterns = (
        r"(?:agreement|deal|contract|partnership)\s+with\s+"
        r"([A-Z][A-Za-z0-9&.'\-]*(?:\s+[A-Z][A-Za-z0-9&.'\-]*){0,4})",
        r"(?:signed|entered|struck)\s+(?:an?\s+)?(?:agreement|deal|contract)\s+with\s+"
        r"([A-Z][A-Za-z0-9&.'\-]*(?:\s+[A-Z][A-Za-z0-9&.'\-]*){0,4})",
    )
    for pattern in english_patterns:
        match = re.search(pattern, source)
        if match:
            value = _clean_text(match.group(1)).strip(" ,.;:")
            if value and value.lower() not in {"the", "a", "an"}:
                return value

    korean_match = re.search(
        r"([가-힣A-Za-z0-9&.\-]{2,30})(?:와|과)\s+[^.]{0,50}?(?:공급\s*계약|계약|협약)",
        source,
    )
    if korean_match:
        value = _clean_text(korean_match.group(1))
        if value and value != selected:
            return value
    return ""


def extract_structured_article_facts(text, item, stock_name, grounded_tags=None):
    """Extract only explicit, bounded facts from the selected article detail."""
    source = str(text or "")
    item = dict(item or {})
    tags = [
        str(value or "").strip().lstrip("#")
        for value in (grounded_tags or item.get("grounded_tags") or [])
        if str(value or "").strip()
    ]

    company_names = {
        canonical
        for stocks in STOCK_UNIVERSE.values()
        for canonical in stocks
    }
    product_name = next(
        (
            tag for tag in tags
            if tag not in _PRODUCT_FACT_BLOCKLIST and tag not in company_names
        ),
        "",
    )

    relation = str(item.get("relation_type") or "").strip().lower()
    event_owner = str(item.get("event_owner") or "").strip()
    provider_stock = str(item.get("provider_stock") or "").strip()
    announcer = ""
    if relation == "direct" and event_owner:
        announcer = event_owner
    elif str(item.get("source_type") or "") == "official_company" and provider_stock:
        announcer = provider_stock

    amount = _extract_amount(source)
    facts = {
        "product_name": product_name,
        "counterparty": _extract_counterparty(source, stock_name),
        "amount": amount,
        "region": _extract_regions(source),
        "announcer": announcer,
        "key_numbers": _extract_key_numbers(source, amount=amount),
    }
    return facts


def read_selected_article_details(items, limit=3, with_sources=False):
    """Read selected articles; optionally retain source quality for central display."""
    source_items = list(items or [])
    empty = {"text": "", "source": "fetch_failed"}
    details = [dict(empty) if with_sources else "" for _ in source_items]
    jobs = {}

    with ThreadPoolExecutor(max_workers=min(3, max(1, len(source_items)))) as pool:
        for index, item in enumerate(source_items[:max(1, int(limit))]):
            if str(item.get("source_type") or "") == "sec_filing":
                continue
            url = str(item.get("url") or item.get("link") or "").strip()
            try:
                parsed = urllib.parse.urlparse(url)
            except Exception:
                continue
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                continue
            job = (pool.submit(_read_url, url, with_source=True)
                   if with_sources else pool.submit(_read_url, url))
            jobs[job] = index

        for future in as_completed(jobs):
            index = jobs[future]
            try:
                details[index] = future.result() or (dict(empty) if with_sources else "")
            except Exception:
                details[index] = dict(empty) if with_sources else ""

    return details
