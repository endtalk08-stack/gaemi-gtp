"""Canonical news URLs: retain story-identifying query parameters."""
import hashlib
import urllib.parse

_TRACKING_KEYS = {
    "fbclid", "gclid", "dclid", "msclkid", "igshid",
    "utm_source", "utm_medium", "utm_campaign", "utm_term",
    "utm_content", "utm_id", "ref_src", "mc_cid", "mc_eid",
}


def canonical_news_url(url):
    try:
        parts = urllib.parse.urlsplit(str(url or "").strip())
        if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
            return ""
        host = parts.netloc.lower()
        query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
        kept = sorted((k, v) for k, v in query
                      if k.lower() not in _TRACKING_KEYS
                      and not k.lower().startswith("utm_"))
        return urllib.parse.urlunsplit((
            parts.scheme.lower(), host, parts.path.rstrip("/") or "/",
            urllib.parse.urlencode(kept, doseq=True), ""))
    except (ValueError, TypeError):
        return ""


def news_url_hash(url):
    canonical = canonical_news_url(url)
    return hashlib.sha256(canonical.encode()).hexdigest() if canonical else None
