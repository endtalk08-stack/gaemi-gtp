"""Simple paired news/storyboard path.

This module intentionally does not collect, score, or invent keywords.
It receives the already-scored news list, reuses the existing article keyword
extractor, and keeps article + timestamp + keyword together as one bundle.
"""

import datetime
import re
from difflib import SequenceMatcher
from zoneinfo import ZoneInfo


def _parse_article_datetime(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(raw)
    except Exception:
        try:
            dt = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt


def build_simple_today_news(items, stock_name, limit=3, display_timezone="Asia/Seoul"):
    """Return today's article bundles; each article keeps its own keyword and time."""
    try:
        tz = ZoneInfo(str(display_timezone or "Asia/Seoul"))
    except Exception:
        tz = datetime.timezone.utc

    source_items = [dict(item) for item in (items or [])]

    today = datetime.datetime.now(tz).date()
    bundles = []

    for article in source_items:
        dt = _parse_article_datetime(article.get("pub_date") or article.get("published_at"))
        if not dt:
            continue
        local_dt = dt.astimezone(tz)
        if local_dt.date() != today:
            continue

        keywords = list(article.get("article_keywords") or [])
        details = list(article.get("article_keyword_details") or [])
        detail_by_label = {
            str(detail.get("label") or "").strip(): detail
            for detail in details
            if str(detail.get("label") or "").strip()
        }
        storyboard_keywords = [str(keyword).strip() for keyword in keywords[:3] if str(keyword).strip()]
        storyboard_keyword_tones = {}
        for keyword in storyboard_keywords:
            detail = detail_by_label.get(keyword, {})
            tone = str(detail.get("tone") or "neutral").strip()
            if tone not in ("positive", "negative", "neutral"):
                tone = "neutral"
            storyboard_keyword_tones[keyword] = tone

        representative = storyboard_keywords[0] if storyboard_keywords else ""
        tone = storyboard_keyword_tones.get(representative, "neutral") if representative else "neutral"

        article["article_keywords"] = keywords
        article["article_keyword_details"] = details
        article["storyboard_keywords"] = storyboard_keywords
        article["storyboard_keyword_tones"] = storyboard_keyword_tones
        article["storyboard_keyword"] = representative
        article["storyboard_keyword_tone"] = tone
        article["storyboard_time"] = local_dt.strftime("%H:%M")
        article["storyboard_date"] = local_dt.strftime("%Y-%m-%d")
        bundles.append((local_dt, article))

    bundles.sort(key=lambda pair: pair[0], reverse=True)
    ordered = [article for _, article in bundles]
    if limit is None:
        return ordered
    return ordered[:max(1, int(limit))]


_FINANCIAL_AMOUNT_METRICS = (
    "영업이익", "매출", "순이익", "HBM매출", "D램매출", "낸드매출",
)
_FORECAST_WORDS = ("전망", "예상", "추정", "관측", "컨센서스", "기대")
_ACTUAL_WORDS = ("확정", "발표", "잠정", "기록", "공시", "달성")


def _financial_amount_fact(source, label):
    """Return a comparable financial amount fact, or None for non-amount labels."""
    compact = re.sub(r"\s+", "", str(label or "")).replace(",", "")
    metric = next((name for name in _FINANCIAL_AMOUNT_METRICS if compact.startswith(name)), "")
    if not metric:
        return None

    rest = compact[len(metric):]
    match = re.match(
        r"(?P<jo>\d+(?:\.\d+)?)조"
        r"(?:(?P<cheon>\d+)천억원|(?P<eok>\d+)억원|원)?",
        rest,
    )
    precision = 0
    if match:
        amount = float(match.group("jo")) * 10000
        if "." in match.group("jo"):
            precision = 1
        if match.group("cheon"):
            amount += int(match.group("cheon")) * 1000
            precision = 2
        elif match.group("eok"):
            amount += int(match.group("eok"))
            precision = 2
        suffix = rest[match.end():]
    else:
        match = re.match(r"(?P<eok>\d+)억원", rest)
        if not match:
            return None
        amount = float(match.group("eok"))
        precision = 1
        suffix = rest[match.end():]

    evidence = ""
    for detail in source.get("article_keyword_details") or []:
        if str((detail or {}).get("label") or "").strip() == str(label or "").strip():
            evidence = str((detail or {}).get("evidence") or "").strip()
            break

    stage = "unknown"
    for context in (suffix, evidence, str(source.get("title") or "")):
        lower = context.lower()
        if any(word in lower for word in _FORECAST_WORDS):
            stage = "forecast"
            break
        if any(word in lower for word in _ACTUAL_WORDS):
            stage = "actual"
            break

    title = str(source.get("title") or "")
    period_match = re.search(r"(?:(20\d{2})년\s*)?([1-4])분기", title)
    quarter_match = re.search(r"(?:(20\d{2})\s*)?([1-4])Q", title, flags=re.IGNORECASE)
    if period_match:
        period = ("quarter", int(period_match.group(2)), period_match.group(1) or "")
    elif quarter_match:
        period = ("quarter", int(quarter_match.group(2)), quarter_match.group(1) or "")
    elif "상반기" in title:
        period = ("half", 1, "")
    elif "하반기" in title:
        period = ("half", 2, "")
    elif "내년" in title:
        period = ("next-year", 0, "")
    elif "연간" in title or "올해" in title:
        period = ("annual", 0, "")
    else:
        period = None

    return {
        "metric": metric,
        "amount": amount,
        "precision": precision,
        "stage": stage,
        "period": period,
    }


def _same_financial_event(left_source, left_label, right_source, right_label):
    left = _financial_amount_fact(left_source, left_label)
    right = _financial_amount_fact(right_source, right_label)
    if not left or not right or left["metric"] != right["metric"]:
        return False

    scale = max(abs(left["amount"]), abs(right["amount"]), 1.0)
    if abs(left["amount"] - right["amount"]) / scale > 0.005:
        return False

    if (
        left["stage"] != "unknown"
        and right["stage"] != "unknown"
        and left["stage"] != right["stage"]
    ):
        return False

    if left["period"] and right["period"]:
        if left["period"][:2] != right["period"][:2]:
            return False
        if left["period"][2] and right["period"][2] and left["period"][2] != right["period"][2]:
            return False
    return True


def _financial_fact_quality(source, label):
    fact = _financial_amount_fact(source, label)
    if not fact:
        return 0
    return fact["precision"] + (2 if fact["stage"] != "unknown" else 0)


def _merge_central_labels(target_source, target_labels, source, source_labels):
    """Merge central-only labels without repeating the same financial amount fact."""
    merged = [str(value).strip() for value in target_labels or [] if str(value).strip()]
    owners = [target_source] * len(merged)

    for raw in source_labels or []:
        label = str(raw or "").strip()
        if not label or label in merged:
            continue

        duplicate_index = next(
            (
                index for index, existing in enumerate(merged)
                if _same_financial_event(owners[index], existing, source, label)
            ),
            None,
        )
        if duplicate_index is None:
            merged.append(label)
            owners.append(source)
            continue

        if _financial_fact_quality(source, label) > _financial_fact_quality(
            owners[duplicate_index], merged[duplicate_index]
        ):
            merged[duplicate_index] = label
            owners[duplicate_index] = source

    return merged


def select_keyword_storyboard_news(items, limit=3):
    """Pick at most limit notable, distinct events for the central flow.

    The source list is already restricted to today's stock-relevant articles.
    This final step must not simply show the three newest articles: a direct,
    concrete event is more useful than a newer but weak mention. It also keeps
    the selection deliberately sparse; if no article has a grounded event
    keyword, the caller receives an empty list rather than filler.
    """
    selected = []

    def _number(value, default=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _relation_type(source):
        relation = str(source.get("relation_type") or "unknown").strip().lower()
        return relation if relation in {"direct", "indirect", "mention_only"} else "unknown"

    def _representative_detail_source(source):
        keyword = str(source.get("storyboard_keyword") or "").strip()
        for detail in source.get("article_keyword_details") or []:
            if str((detail or {}).get("label") or "").strip() == keyword:
                return str((detail or {}).get("source") or "").strip()
        return ""

    def _central_candidate_allowed(source):
        """Keep central issues stock-owned; preserve legacy items with no ownership annotation."""
        relation = _relation_type(source)
        if relation == "mention_only":
            return False
        if relation != "indirect":
            return True

        # Indirect events are allowed only when the selected stock has a strong
        # description-level transmission path.  A different company's title
        # event (for example Samsung HBM news that merely mentions Google later)
        # must stay in related news, not become the selected stock's central issue.
        tier = max(0, int(_number(source.get("analysis_relevance_tier"))))
        event_strength = max(0.0, _number(source.get("analysis_event_strength")))
        material_signal = bool(source.get("analysis_material_signal"))
        detail_source = _representative_detail_source(source)
        return (
            tier >= 2
            and event_strength >= 2
            and material_signal
            and detail_source.startswith("description")
        )

    def _selection_score(source):
        """Rank evidence without inventing a market interpretation."""
        tier = max(0, int(_number(source.get("analysis_relevance_tier"))))
        event_strength = max(0.0, _number(source.get("analysis_event_strength")))
        breakdown = source.get("flow_score_breakdown") or {}
        direct = max(0.0, _number(breakdown.get("direct_stock")))
        material = max(0.0, _number(breakdown.get("material_strength")))
        signal = max(0.0, _number(breakdown.get("movement_signal")))
        relation = _relation_type(source)
        relation_bonus = 300.0 if relation == "direct" else 40.0 if relation == "indirect" else 0.0

        return (
            relation_bonus
            + (tier * 100)
            + min(event_strength, 8.0) * 8.0
            + min(direct, 35.0)
            + min(material, 20.0)
            + min(signal, 20.0)
            + min(_number(source.get("flow_score")), 100.0) / 10.0
        )

    def _keyword_key(value):
        return "".join(str(value or "").split()).lower()

    def _keywords_overlap(left, right):
        left_key = _keyword_key(left)
        right_key = _keyword_key(right)
        if not left_key or not right_key:
            return False
        if left_key == right_key:
            return True
        return (
            min(len(left_key), len(right_key)) >= 5
            and (left_key in right_key or right_key in left_key)
        )

    def _headline_key(value):
        return re.sub(r"[^0-9a-z가-힣]", "", str(value or "").lower())

    def _source_time(source):
        dt = _parse_article_datetime(source.get("published_at") or source.get("pub_date"))
        return dt.timestamp() if dt else float("inf")

    def _same_selected_event(source, keyword, previous):
        previous_keyword = str(previous.get("storyboard_keyword") or "").strip()
        source_fact = _financial_amount_fact(source, keyword)
        previous_fact = _financial_amount_fact(previous, previous_keyword)

        if source_fact and previous_fact:
            return _same_financial_event(source, keyword, previous, previous_keyword)

        if _keywords_overlap(keyword, previous_keyword):
            return True

        source_headline = _headline_key(source.get("title"))
        previous_headline = _headline_key(previous.get("title"))
        return (
            min(len(source_headline), len(previous_headline)) >= 12
            and SequenceMatcher(None, source_headline, previous_headline).ratio() >= 0.75
        )

    def _merge_duplicate(previous, source, keyword):
        if _source_time(source) < _source_time(previous):
            earliest_timestamp = source.get("published_at") or source.get("pub_date")
            if earliest_timestamp:
                previous["published_at"] = earliest_timestamp
            if source.get("pub_date"):
                previous["pub_date"] = source.get("pub_date")
            for field in ("storyboard_time", "storyboard_date"):
                if source.get(field):
                    previous[field] = source.get(field)

        previous["article_keywords"] = _merge_central_labels(
            previous,
            previous.get("article_keywords") or [],
            source,
            source.get("article_keywords") or [],
        )

        previous_keyword = str(previous.get("storyboard_keyword") or "").strip()
        if _same_financial_event(source, keyword, previous, previous_keyword):
            if _financial_fact_quality(source, keyword) > _financial_fact_quality(
                previous, previous_keyword
            ):
                tone = (source.get("storyboard_keyword_tones") or {}).get(keyword, "neutral")
                previous["storyboard_keyword"] = keyword
                previous["storyboard_keywords"] = [keyword]
                previous["storyboard_keyword_tone"] = tone
                previous["storyboard_keyword_tones"] = {keyword: tone}

        for field in ("stock_entities", "grounded_tags"):
            values = list(previous.get(field) or [])
            for value in source.get(field) or []:
                if value not in values:
                    values.append(value)
            if values:
                previous[field] = values

    candidates = []
    for source in items or []:
        if not _central_candidate_allowed(source):
            continue

        keywords = [
            str(value).strip()
            for value in (source.get("storyboard_keywords") or [])
            if str(value).strip()
        ]
        if not keywords:
            continue

        article = dict(source)
        article["article_keywords"] = _merge_central_labels(
            article,
            [],
            source,
            source.get("article_keywords") or [],
        )
        keywords = _merge_central_labels(article, [], source, keywords)
        candidates.append((article, keywords))

    candidates.sort(
        key=lambda pair: (
            _selection_score(pair[0]),
            str(pair[0].get("published_at") or pair[0].get("pub_date") or ""),
        ),
        reverse=True,
    )

    for source, keywords in candidates:
        duplicate = None
        keyword = ""

        for value in keywords:
            matched = next(
                (
                    previous for previous in selected
                    if _same_selected_event(source, value, previous)
                ),
                None,
            )
            if matched is not None:
                duplicate = matched
                continue
            keyword = value
            break

        if not keyword:
            if duplicate is not None:
                _merge_duplicate(duplicate, source, str(keywords[0] or ""))
            continue

        headline_duplicate = next(
            (
                previous for previous in selected
                if _same_selected_event(source, keyword, previous)
            ),
            None,
        )
        if headline_duplicate is not None:
            _merge_duplicate(headline_duplicate, source, keyword)
            continue

        if len(selected) >= max(1, int(limit)):
            # Keep scanning lower-ranked articles only to move an already
            # selected duplicate back to its first-report timestamp.
            continue

        tones = dict(source.get("storyboard_keyword_tones") or {})
        article = dict(source)
        article["storyboard_keywords"] = [keyword]
        article["storyboard_keyword"] = keyword
        article["storyboard_keyword_tones"] = {keyword: tones.get(keyword, "neutral")}
        article["storyboard_keyword_tone"] = tones.get(keyword, "neutral")
        article["storyboard_selection_score"] = round(_selection_score(source), 1)
        selected.append(article)

    selected.sort(
        key=lambda item: str(item.get("published_at") or item.get("pub_date") or ""),
        reverse=True,
    )
    return selected
