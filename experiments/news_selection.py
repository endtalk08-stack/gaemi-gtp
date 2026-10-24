"""Stage 1-3 of experiment #2: classify/filter METADATA before reading any article.

Pure selection functions use only title, snippet, timestamp and link. They DO
NOT fetch URLs, call AI, or write to any database. Full-article reads are an
explicit later action and restricted to selected candidate URLs.

Run:
  python -m experiments.news_selection --file metadata_candidates.json
  python -m experiments.news_selection --file metadata_candidates.json --read-selected

The second command is TEST ONLY: it reads selected article bodies and prints
unpublished previews. It does not post anything to the site.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse, urlunparse

CATEGORIES = (
    "미국 증시 마감",
    "개별 종목",
    "경제지표",
    "에너지",
    "연준 일정",
    "투자의견",
    "실적 발표",
)

# Explicit high-signal patterns only. First-match priority is for article
# routing, NOT evidence that the title/snippet itself is fully factual.
_PATTERNS = {
    "실적 발표": (
        r"실적\s*(?:발표|공개|보고|시즌)|어닝\s*서프라이즈|"
        r"(?:분기|1분기|2분기|3분기|4분기)[^.!?]{0,30}(?:매출|영업이익|순이익|EPS)|"
        r"주당\s*순이익|실적\s*가이던스",
    ),
    "투자의견": (
        r"(?:목표\s*주가|목표가)\s*(?:상향|하향|인상|인하|조정)|"
        r"투자\s*의견\s*(?:상향|하향|유지|매수|매도|중립)|"
        r"증권사[^.!?]{0,40}(?:목표가|투자의견)",
    ),
    "연준 일정": (
        r"(?:FOMC|연방공개시장위원회)[^.!?]{0,35}(?:일정|회의|개최|예정|발표)|"
        r"(?:연준|파월|연방준비제도)[^.!?]{0,35}(?:연설|발언\s*예정|회의\s*일정|일정|기자회견)|"
        r"기준금리\s*(?:결정|발표)\s*(?:예정|일정)",
    ),
    "경제지표": (
        r"(?<![A-Za-z])(?:CPI|PCE|GDP|PMI|NFP)(?![A-Za-z])|"
        r"(?:소비자|생산자)\s*물가(?:지수)?|고용\s*(?:지표|보고서)|"
        r"비농업\s*(?:고용|취업)|실업률|소매\s*판매|"
        r"미국\s*(?:성장률|국내총생산)",
    ),
    "에너지": (
        r"(?<![A-Za-z])(?:WTI|OPEC|Brent)(?![A-Za-z])|"
        r"국제\s*유가|원유\s*(?:가격|재고|생산량|감산)|"
        r"천연가스\s*(?:가격|재고|수요|공급)|"
        r"석유\s*(?:공급|생산|감산)",
    ),
    "미국 증시 마감": (
        r"(?:뉴욕|미국)\s*증시[^.!?]{0,45}(?:마감|종가)|"
        r"(?:다우|나스닥|S&P\s*500)[^.!?]{0,40}(?:마감|종가)|"
        r"월가[^.!?]{0,40}(?:거래\s*마감|하락\s*마감|상승\s*마감)",
    ),
}
_COMPILED = {name: re.compile(pattern, re.IGNORECASE) for name, pattern in _PATTERNS.items()}
# First matching specialist category wins. A single article may have additional
# categories for audit; secondary labels never trigger extra full-body reads.
_PRIORITY = ("실적 발표", "투자의견", "연준 일정", "경제지표",
             "에너지", "미국 증시 마감")


def _timestamp(value):
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _article_url(url):
    p = urlparse(str(url or "").strip())
    if p.scheme != "https" or not p.hostname or p.username or p.password:
        return ""
    if p.hostname in {"localhost", "127.0.0.1", "::1"}:
        return ""
    # Identity only: tracking queries/fragments must not create duplicate reads.
    return urlunparse((p.scheme, p.netloc.lower(), p.path.rstrip("/") or "/",
                       "", "", ""))


def classify_metadata(item):
    """Preliminary topic label based on TITLE + DESCRIPTION, never article body.

    A company name found as a passing mention is not treated as verified
    event ownership. That determination must be made after the full read.
    """
    text = " ".join(str(item.get(k) or "") for k in ("title", "description", "summary"))
    matches = [name for name in _PRIORITY if _COMPILED[name].search(text)]
    stock = str(item.get("stock_name") or "").strip()
    # Explicit stock identity required for generic company news.
    if stock and re.search(re.escape(stock), text, re.IGNORECASE):
        matches.append("개별 종목")
    if not matches:
        return None, []
    return matches[0], matches[1:]


def select_candidates(rows, *, now=None, limit_per_category=3, max_total=21,
                      max_age_hours=48):
    """Return eligible METADATA ONLY, grouped/limited before any full read.

    Publication recency is a first-pass filter; actual event/schedule date is
    validated after reading full text. Unknown publication date => exclude.
    """
    if not isinstance(rows, list):
        raise ValueError("candidate_list_required")
    now = _timestamp(now) if now is not None else datetime.now(timezone.utc)
    if now is None or limit_per_category < 1 or max_total < 1 or max_age_hours < 1:
        raise ValueError("invalid_selection_parameters")

    provisional = []
    seen_url = set()
    seen_title = set()
    for item in rows:
        if not isinstance(item, dict):
            continue
        url = _article_url(item.get("url") or item.get("link"))
        title = str(item.get("title") or "").strip()
        published = _timestamp(item.get("published_at"))
        if not url or len(title) < 8 or not published:
            continue
        if published > now or now - published > timedelta(hours=max_age_hours):
            continue
        category, secondary = classify_metadata(item)
        if not category:
            continue
        # Headline duplicates are a soft cross-publisher dedupe for test
        # samples. In production this must be reviewed for false positives.
        title_key = re.sub(r"[^가-힣A-Za-z0-9]+", "", title).casefold()
        if url in seen_url or title_key in seen_title:
            continue
        seen_url.add(url)
        seen_title.add(title_key)
        provisional.append({
            "category": category, "secondary_categories": secondary,
            "title": title,
            "description": str(item.get("description") or item.get("summary") or ""),
            "url": str(item.get("url") or item.get("link")),
            "published_at": published.isoformat(),
            "stock_name": str(item.get("stock_name") or ""),
            "publisher": str(item.get("source") or ""),
        })
    # Do not rank by article body: none has been fetched at this point.
    provisional.sort(key=lambda item: item["published_at"], reverse=True)
    selected = []
    per_category = {}
    for candidate in provisional:
        name = candidate["category"]
        if per_category.get(name, 0) >= limit_per_category:
            continue
        selected.append(candidate)
        per_category[name] = per_category.get(name, 0) + 1
        if len(selected) >= max_total:
            break
    return selected


def run_selected_trial(rows, *, read_article, compose_article, now=None, **limits):
    """Injectable test: call the reader ONLY for selected URLs.

    The caller supplies read_article and compose_article. No publishing,
    database access, or side effects are performed by the selection logic.
    """
    chosen = select_candidates(rows, now=now, **limits)
    output = []
    for item in chosen:
        try:
            article = read_article(item["url"])
            candidate = compose_article(article.text, item["url"],
                                        source_kind=article.source_kind)
            output.append({"category": item["category"], "original_title": item["title"],
                           "published_at": item["published_at"], **candidate})
        except Exception as exc:
            output.append({"category": item["category"], "original_title": item["title"],
                           "source_url": item["url"], "status": "not_supported",
                           "reason": f"full_article_unavailable:{type(exc).__name__}"})
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description="Categorize/filter news BEFORE full reads")
    parser.add_argument("--file", required=True, help="JSON list of collected metadata")
    parser.add_argument("--read-selected", action="store_true",
                        help="Opt in to full-article reads of SELECTED candidates only")
    parser.add_argument("--per-category", type=int, default=3)
    parser.add_argument("--max-total", type=int, default=21)
    args = parser.parse_args(argv)
    rows = json.loads(Path(args.file).read_text(encoding="utf-8"))
    settings = {"limit_per_category": args.per_category, "max_total": args.max_total}
    if args.read_selected:
        from experiments.full_article_news import read_article_html, compose_news
        result = run_selected_trial(rows, read_article=read_article_html,
                                    compose_article=compose_news, **settings)
    else:
        result = select_candidates(rows, **settings)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
