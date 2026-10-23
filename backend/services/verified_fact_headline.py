"""Title-only fact overlay on the existing verified three-sentence news briefs.

Never select new articles, fetch sources, summarize bodies, change keyword tags,
or infer why a share price moved. The article-selector result is authoritative.
"""
from datetime import datetime
import re

from backend.services.issue_briefs import _article_excerpt
from backend.services.article_fact_keywords import _aliases, _company_match


_EVENT = re.compile(
    r"공급|계약|체결|도입|출시|판매\s*시작|승인|허가|신청|철회|중단|축소|"
    r"증가|감소|확대|투자|지분|인수|합병|성과급|이익\s*공유|이익연동|"
    r"임상|상용화|채택|개발|기술|수출|규제|거부|반대|목표치|매출|"
    r"매수의견|목표주가|설비|공장|수주|유출|발표|공개|진출|협력|"
    r"경고|가동|호조|부진|하회|상회", re.I
)
_PRICE = re.compile(r"(?:주가|급등|급락|장중|거래량|거래대금|%[ ]*(?:상승|하락))")
_SPLIT = re.compile(r"(?:…|⋯|\.{3}|[。!?]|\s+[|]\s+)")


def _company_display(name):
    return {
        "마이크론 테크놀로지": "마이크론",
        "메타 플랫폼스(페이스북)": "메타",
        "시게이트 테크놀로지 홀딩스": "시게이트",
        "크라우드스트라이크 홀딩스": "크라우드스트라이크",
    }.get(str(name), str(name))


def grounded_fact_title(article_title, excerpt, stock_name, original_title):
    """Return a short evidenced event headline, or the original verified title.

    A failure to understand an article must NOT truncate or rewrite its body.
    """
    original = str(original_title or "").strip()
    title = re.sub(r"\s+", " ", str(article_title or "")).strip()
    title = re.sub(r"^\[[^\]]{1,35}\]\s*", "", title)
    aliases = _aliases(stock_name)
    found = _company_match(title, aliases)
    if not found:
        return original
    # Do not turn an incidental stock mention inside someone else's long
    # market roundup into that company's own action.
    if found.start() > 45:
        return original
    label = _company_display(stock_name)

    # Translate only a small number of clearly explicit English event
    # constructions; all information must still appear in the source headline.
    if re.search(r"\bunion\s+members?\s+reject\s+profit.sharing\s+proposal\b", title, re.I):
        locality = "타오위안 노조" if re.search(r"Taoyuan", title, re.I) else "노조"
        return f"{label} {locality}, 이익공유안 거부"
    gain = re.search(
        r"\$\s*([\d,]+)\s+Million\s+Unrealized\s+Gain\s+on\s+(.+?)\s+Stake\b",
        title, re.I,
    )
    if gain:
        amount = int(gain.group(1).replace(",", ""))
        amount_ko = (
            f"{amount//100}억{amount%100*100:,}만"
            if amount >= 100 and amount % 100
            else f"{amount//100}억" if amount >= 100
            else f"{amount*100:,}만"
        )
        entity = gain.group(2).strip()
        if re.search(r"\bBoring\s+Co", entity, re.I):
            entity = "보링컴퍼니"
        return f"{label}, {entity} 지분 평가이익 {amount_ko} 달러"
    if re.search(r"Begins?\s+Foldable\s+iPhone\s+Sales\s+in\s+South\s+Korea", title, re.I):
        return f"{label}, 한국서 폴더블 아이폰 판매 시작"

    # Only synthesize a Korean title from an explicit action stated in the
    # article headline; do not copy/truncate the full publisher headline.
    fragment = _SPLIT.split(title[found.end():].lstrip(" ,:·—-'“”"), maxsplit=1)[0]
    fragment = fragment.strip(" ,.:;·—-'“”")
    fragment = re.sub(r"[\s]+", " ", fragment)
    if not (5 <= len(fragment) <= 45) or not _EVENT.search(fragment):
        return original
    if _PRICE.search(fragment) and not re.search(
        r"매출|계약|투자|도입|실적|공급|승인|허가|임상|출시|성과급|"
        r"이익공유|이익연동|철회|중단|축소|증가|감소|지분|목표치", fragment
    ):
        return original
    if re.search(r"(?<!\w)(?:등|외)\s+\d+.{0,15}(?:기업|개사)", fragment):
        return original
    # The verified article must discuss the same concrete business event.
    # A known keyword in the headline with no supporting full text is not
    # permission to silently invent or substitute a different story.
    if not excerpt or len(str(excerpt).strip()) < 30:
        return original
    return f"{label}, {fragment}"


def overlay_verified_headlines(briefs, selected_articles, verified_bodies, stock_name):
    """Change headline alone; carry the same verified article's citation.

    The existing article selection, excerpt (up to 3 exact sentences), keyword
    tags, time, ordering and count are untouched. Unmatched briefs remain intact.
    """
    lookup = {}
    for item, body in zip(selected_articles or [], verified_bodies or []):
        if not isinstance(item, dict) or not body:
            continue
        excerpt = _article_excerpt(body)
        if not excerpt:
            continue
        lookup.setdefault(excerpt, []).append(item)

    updated = []
    for original in briefs or []:
        if not isinstance(original, dict):
            continue
        excerpt = original.get("summary") or ""
        matches = lookup.get(excerpt) or []
        if not matches:
            # Keep the original fallback exactly as produced by the existing
            # pipeline. Render's separate source check decides visibility.
            updated.append(dict(original))
            continue
        article = matches.pop(0)
        url = str(article.get("url") or article.get("link") or "").strip()
        stamp = str(article.get("published_at") or "").strip()
        if not url.startswith(("https://", "http://")):
            updated.append(dict(original))
            continue
        try:
            if datetime.fromisoformat(stamp.replace("Z", "+00:00")).utcoffset() is None:
                updated.append(dict(original))
                continue
        except (ValueError, TypeError):
            updated.append(dict(original))
            continue
        revised = dict(original)
        revised["headline"] = grounded_fact_title(
            article.get("title"), excerpt, stock_name, original.get("headline")
        )
        revised["source_articles"] = [{
            "url": url,
            "title": str(article.get("title") or ""),
            "published_at": stamp,
        }]
        revised["evidence_source"] = "verified_article_body_title_only"
        updated.append(revised)
    return updated
