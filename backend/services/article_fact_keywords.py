"""Source-grounded stock news facts for the existing issue-brief UI.

The article's title/description provides the words; price direction only nudges
ordering. This module never invokes AI and never infers a cause of price movement.
"""
from datetime import datetime, timezone
import os
import re

from backend.analysis.news.catalog import STOCK_UNIVERSE

_MOVEMENT_UP = re.compile(r"증가|확대|개선|상회|성장|출시|계약|체결|채택|승인|진출|확보|수주|상향|도입|성공|강화|launch|gain|expand|increase|deal", re.I)
_MOVEMENT_DOWN = re.compile(r"감소|축소|하향|철회|취소|중단|유출|적자|고갈|부담|우려|위축|부진|지연|제재|거부|부족|급락|하락|reduce|cut|reject|risk|loss", re.I)
_ONLY_QUOTE = re.compile(r"^(?:주가|주식|증시|시장|나스닥|반도체주|오늘의|속보).{0,40}(?:%|상승|하락|급등|급락)", re.I)
_BAD_TITLES = re.compile(r"^(?:USA APPLE IPHONE LAUNCH|Apple iPhone Duo|Brazil Election Amazon|\[오늘의 경제상식\])", re.I)
_COMPANY_SUFFIX = r"(?:은|는|이|가|의|와|과|을|를|도|에|에서|에게|측)?"
_NONCOMPANY = (
    re.compile(r"애플힙|애플파이|애플수박|메타(?:파머스|케이|버스|데이터|휴먼)|아마존\s*(?:강|숲|열대우림|산림|지역)", re.I),
    re.compile(r"STX(?:조선|엔진|그린로지스)|유니마이크론", re.I),
)


def _aliases(stock_name):
    name = str(stock_name or "").strip()
    aliases = [name]
    for canonical, variants in STOCK_UNIVERSE.get("미국", {}).items():
        if name == canonical or name.casefold().startswith(canonical.casefold() + " "):
            aliases.extend(variants)
            continue
        if any(name.casefold() == str(v).casefold() for v in variants):
            aliases.extend([canonical, *variants])
    # Exchange listing labels are not necessarily identical to the news catalog.
    # Use an unambiguous company-name prefix, but never short exchange tickers.
    prefix = name.split(" ", 1)[0].split("(", 1)[0]
    if len(prefix) >= 3 and prefix not in {"알파벳", "메타"}:
        aliases.append(prefix)
    if name.startswith("메타 플랫폼스"):
        aliases.extend(["메타 플랫폼스", "메타", "Meta Platforms"])
    if name.startswith("알파벳"):
        aliases.extend(["구글", "Google", "Alphabet", "알파벳"])
    if name.startswith("아마존"):
        aliases.extend(["아마존", "아마존닷컴", "Amazon", "AWS"])
    if name.startswith("팔란티어"):
        aliases.extend(["팔란티어", "Palantir"])
    if name.startswith("웨스턴"):
        aliases.extend(["웨스턴디지털", "웨스턴 디지털", "Western Digital"])
    if name.startswith("시게이트"):
        aliases.extend(["시게이트", "씨게이트", "Seagate"])
    if name.startswith("루멘텀"):
        aliases.extend(["루멘텀", "Lumentum"])
    if name.startswith("크라우드스트라이크"):
        aliases.extend(["크라우드스트라이크", "CrowdStrike"])
    cleaned = []
    for alias in aliases:
        alias = str(alias).strip()
        if alias and alias not in cleaned and not (len(alias) <= 3 and alias.isascii()):
            cleaned.append(alias)
    return sorted(cleaned, key=len, reverse=True)


def _company_match(text, aliases):
    source = str(text or "")
    # Don't mistake Korean STX shipbuilding, apple hip, Amazon rainforest, etc.
    for alias in aliases:
        pattern = (
            rf"(?<![가-힣A-Za-z0-9]){re.escape(alias)}{_COMPANY_SUFFIX}(?![가-힣A-Za-z0-9])"
            if re.search(r"[가-힣]", alias)
            else rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])"
        )
        for match in re.finditer(pattern, source, re.I):
            span = source[max(0, match.start() - 10):match.end() + 15]
            if any(bad.search(span) for bad in _NONCOMPANY):
                continue
            return match
    return None


def _clean(text):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", str(text or ""))).strip()


def _short_fact(text, aliases):
    """Extract a compact phrase from article words, never from a predefined label."""
    source = re.sub(r"^\s*\[[^\]]{1,22}\]\s*", "", _clean(text))
    match = _company_match(source, aliases)
    if not match:
        return ""
    # Prefer the company's own clause in mixed-stock titles.
    part = source[match.end():].lstrip(" ,:·—-'\"“”")
    if not part or len(part) < 5:
        before = source[:match.start()].split("…")[-1].split("⋯")[-1]
        part = (before + " " + part).strip()
    part = re.split(r"(?:(?:\.{3}|…|⋯)|[。!?]|\s+\|\s+)", part)[0]
    part = part.split("…")[0].strip(" ,.:;·—-'\"“”")
    if len(part) < 5:
        return ""
    tokens = part.split()
    phrase = " ".join(tokens[:9])[:66].rstrip(" ,.:;·—-'\"“”")
    return phrase if len(phrase) >= 6 else ""


def _story_timestamp(article):
    stamp = article.get("published_at") or article.get("pubDate") or ""
    try:
        value = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
        if value.tzinfo is None:
            return None
        return value.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def _sentiment(text):
    positive = bool(_MOVEMENT_UP.search(text))
    negative = bool(_MOVEMENT_DOWN.search(text))
    if positive == negative:
        return 0
    return 1 if positive else -1


def _normalize_tag(phrase):
    # Compact only the factual fragment, retaining numbers, names, and qualifiers.
    cleaned = re.sub(r"[#\\/]+", " ", _clean(phrase)).strip()
    return "".join(cleaned.split())[:32]


def build_article_fact_briefs(articles, stock_name, *, price_change_pct=None, limit=3):
    """Return UI-compatible briefs (headline, summary, tags, evidence URLs).

    Existing stored keyword annotations, AI analyses and movement_signals are
    deliberately not read. Quote sign is only a small ordering tie-breaker.
    """
    if not isinstance(articles, list) or not stock_name or limit <= 0:
        return []
    aliases = _aliases(stock_name)
    price_dir = 0
    try:
        price = float(price_change_pct)
        if abs(price) <= 1000:
            price_dir = (price > 0) - (price < 0)
    except (TypeError, ValueError, OverflowError):
        pass
    seen_urls = set()
    candidates = []
    now = datetime.now(timezone.utc)
    for article in articles:
        if not isinstance(article, dict):
            continue
        title = _clean(article.get("title"))
        description = _clean(article.get("description"))
        url = str(article.get("url") or article.get("link") or "").strip()
        if not title or _BAD_TITLES.match(title):
            continue
        published = _story_timestamp(article)
        if published is None or not (0 <= (now - published).total_seconds() <= 86400):
            continue
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        title_match = _company_match(title, aliases)
        body_match = _company_match(description, aliases)
        if not title_match and not body_match:
            continue
        # Title must be about this company, or its own sentence in the description
        # must explicitly describe an event, not merely enumerate tickers.
        snippet = ""
        if body_match:
            clauses = re.split(r"(?<=[.!?。])\s+|(?<=다\.)\s+", description)
            snippet = next((clause for clause in clauses if _company_match(clause, aliases)), "")
        fact = _short_fact(title, aliases) if title_match else ""
        if not fact and snippet:
            fact = _short_fact(snippet, aliases)
        if not fact:
            continue
        combined = (title + " " + snippet)
        # Pure price reports alone are not corporate news facts.
        if _ONLY_QUOTE.match(title) and not re.search(r"실적|계약|임상|출시|투자|공급|사업|공시", combined):
            continue
        # Reject obvious incidental comparisons where the target is not acting.
        if re.search(r"처럼|제치고|제쳤|보다\s*높|보다\s*낮", title[max(0, title_match.start() if title_match else 0):][:45]):
            continue
        tone = _sentiment(combined)
        day_recency = max(0.0, 1.0 - (now - published).total_seconds() / 86400)
        score = (5.0 if title_match else 2.5) + (1.0 if re.search(r"\d", fact) else 0)
        score += day_recency * 1.2
        if price_dir and price_dir == tone:
            score += 0.8
        if _ONLY_QUOTE.match(title):
            score -= 3.0
        if re.search(r"종목|ETF\s*(?:편입|출시)|언론|\[사설\]|\[신간\]|팝업스토어", title):
            score -= 1.4
        tag = _normalize_tag(fact)
        if len(tag) < 5:
            continue
        display_headline = title[:125]
        candidates.append({
            "score": score, "tag": tag, "brief": {
                "time": published.astimezone(__import__("zoneinfo").ZoneInfo("Asia/Seoul")).strftime("%H:%M"),
                "reaction_at": published.isoformat(),
                "headline": display_headline,
                "summary": description[:350] or display_headline,
                "tags": [tag],
                "stock_names": [stock_name],
                "evidence_source": "article_title_description_price_context",
                "source_articles": [{"title": title, "url": url, "published_at": published.isoformat()}] if url.startswith(("https://", "http://")) else [],
            }
        })
    candidates.sort(key=lambda row: (-row["score"], row["brief"]["headline"]))
    selected, seen_tags = [], set()
    for item in candidates:
        prefix = item["tag"][:13]
        if prefix in seen_tags:
            continue
        seen_tags.add(prefix)
        selected.append(item["brief"])
        if len(selected) >= limit:
            break
    return selected


def read_us_price_change_pct(stock_name):
    """Read existing Kiwoom ranking snapshot on the DO worker; no new quote API call."""
    database_url = (os.environ.get("NEWS_DATABASE_URL") or "").strip()
    if not database_url:
        return None
    try:
        import psycopg
        with psycopg.connect(database_url, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT e.change_rate
                       FROM public.market_rank_entries e
                       JOIN public.market_rank_snapshots s ON e.snapshot_id=s.id
                       WHERE s.market='US' AND e.display_name=%s
                         AND s.captured_at>now()-interval '6 hours'
                       ORDER BY s.captured_at DESC, e.rank ASC LIMIT 1""",
                    (stock_name,),
                )
                row = cur.fetchone()
        return float(row[0]) if row and row[0] is not None else None
    except (ImportError, Exception) as exc:
        print("[fact keywords] quote_snapshot_unavailable: " + type(exc).__name__, flush=True)
        return None
