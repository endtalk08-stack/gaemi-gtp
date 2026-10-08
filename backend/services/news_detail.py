"""Second-pass article detail reader for already-selected central news.

The first-pass feed/scoring pipeline remains unchanged.  This module reads only
the final storyboard candidates (normally <= 3), extracts a bounded amount of
article text, and returns it for fact re-extraction.  Raw article text is never
returned to the frontend.
"""

import html
import json
import re
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser


REQUEST_TIMEOUT = 1.6
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


def extract_article_text(payload, charset="utf-8"):
    """Extract a bounded article body from HTML bytes without returning page chrome."""
    if not payload:
        return ""
    try:
        source = payload.decode(charset or "utf-8", errors="replace")
    except Exception:
        source = payload.decode("utf-8", errors="replace")

    parser = _ArticleHTMLParser()
    try:
        parser.feed(source)
        parser.close()
    except Exception:
        return ""

    candidates = [
        parser.json_article_body,
        " ".join(parser.preferred_paragraphs),
        " ".join(parser.all_paragraphs),
        parser.meta_description,
    ]
    for candidate in candidates:
        cleaned = _bounded_text(candidate)
        if len(cleaned) >= 80:
            return cleaned
    return _bounded_text(parser.meta_description)


def _read_url(url):
    now = time.time()
    with _CACHE_LOCK:
        cached = _CACHE.get(url)
        if cached and now - cached[0] <= _CACHE_TTL:
            return cached[1]

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "gaemiGTP/1.0",
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5",
        },
    )
    text = ""
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            content_type = str(response.headers.get("Content-Type") or "").lower()
            if "html" not in content_type and "xhtml" not in content_type:
                return ""
            charset = response.headers.get_content_charset() or "utf-8"
            payload = response.read(MAX_RESPONSE_BYTES)
        text = extract_article_text(payload, charset=charset)
    except Exception as exc:
        print(
            f"[news detail] failed url={url}: {type(exc).__name__}: {exc}",
            flush=True,
        )

    with _CACHE_LOCK:
        _CACHE[url] = (now, text)
    return text


def read_selected_article_details(items, limit=3):
    """Read only selected central candidates; results align with the input list."""
    source_items = list(items or [])
    details = [""] * len(source_items)
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
            jobs[pool.submit(_read_url, url)] = index

        for future in as_completed(jobs):
            index = jobs[future]
            try:
                details[index] = future.result() or ""
            except Exception:
                details[index] = ""

    return details
