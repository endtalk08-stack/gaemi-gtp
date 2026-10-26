"""Evidence-first article taxonomy from the supplied signal design (2026-10-26).

This enriches articles. It never filters the 24-hour feed or invents a price cause.
Original titles, snippets, and excerpts remain distinct from Korean translations.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import urllib.request

TAXONOMY_VERSION = 1
EVENT_FAMILIES = ("EARNINGS", "GUIDANCE", "ANALYST", "MACRO", "COMMODITY",
                  "SECTOR", "OPERATIONS", "CONTRACT", "PRODUCT", "REGULATION",
                  "CAPITAL", "CORPORATE", "LEGAL", "FLOW")

# Patterns find actual clauses; labels normalize wording without inferring impact.
# Longer, more specific actions precede general context labels.
RULES = (
 ("ANALYST", "ANALYST_TARGET_UP", "목표주가상향", r"목표\s*(?:주가|가격|가)[^.!?\n]{0,55}?(?:상향|높였|높여|올렸)|(?:raises?|raised|lifts?)\s+(?:its\s+)?(?:price\s+)?target"),
 ("ANALYST", "ANALYST_TARGET_DOWN", "목표주가하향", r"목표\s*(?:주가|가격|가)[^.!?\n]{0,55}?(?:하향|낮췄|낮춰)|(?:cuts?|lowers?|lowered)\s+(?:its\s+)?(?:price\s+)?target"),
 ("ANALYST", "ANALYST_RATING_CHANGE", "투자의견하향", r"(?:투자\s*의견|투자\s*등급)[^.!?\n]{0,45}?(?:하향|낮췄)|downgrad(?:e[sd]?|ing)"),
 ("ANALYST", "ANALYST_RATING_CHANGE", "투자의견상향", r"(?:투자\s*의견|투자\s*등급)[^.!?\n]{0,45}?(?:상향|높였)|upgrad(?:e[sd]?|ing)"),
 ("ANALYST", "ANALYST_RATING_INIT", "분석개시", r"(?:분석|커버리지)[^.!?\n]{0,18}(?:개시|시작)|initiat(?:e[sd]?|ing)\s+coverage"),
 ("ANALYST", "ANALYST_RATING_MAINTAIN", "매수의견유지", r"매수\s*(?:의견|등급)[^.!?\n]{0,15}유지|maintain[^.!?\n]{0,20}\bbuy\b"),
 ("ANALYST", "ANALYST_TARGET_SET", "목표주가제시", r"목표\s*(?:주가|가격|가)[^.!?\n]{0,45}?(?:제시|유지)|price\s+target\s+(?:of|at)"),
 ("GUIDANCE", "GUIDANCE_UP", "가이던스상향", r"(?:가이던스|매출\s*전망|이익\s*전망)[^.!?\n]{0,35}(?:상향|높였)|rais(?:e[sd]?|ing)[^.!?\n]{0,25}(?:guidance|outlook)"),
 ("GUIDANCE", "GUIDANCE_DOWN", "가이던스하향", r"(?:가이던스|매출\s*전망|이익\s*전망)[^.!?\n]{0,35}(?:하향|축소|낮췄)|(?:cuts?|lowers?)[^.!?\n]{0,25}(?:guidance|outlook)"),
 ("GUIDANCE", "GUIDANCE_MAINTAIN", "가이던스유지", r"가이던스[^.!?\n]{0,20}(?:유지|재확인)|reaffirm[^.!?\n]{0,25}(?:guidance|outlook)"),
 ("EARNINGS", "EARNINGS_BEAT", "예상치상회", r"(?:매출|EPS|주당\s*순이익|이익|실적)[^.!?\n]{0,50}(?:예상|전망|컨센서스)[^.!?\n]{0,20}(?:상회|웃돌)|(?:beat[ s]?|tops?)[^.!?\n]{0,20}(?:estimates|expectations)"),
 ("EARNINGS", "EARNINGS_MISS", "예상치하회", r"(?:매출|EPS|주당\s*순이익|이익|실적)[^.!?\n]{0,50}(?:예상|컨센서스)[^.!?\n]{0,20}(?:하회|밑돌)|miss(?:es|ed)?[^.!?\n]{0,20}(?:estimates|expectations)"),
 ("EARNINGS", "REVENUE_GROWTH", "매출증가", r"매출[^.!?\n]{0,45}(?:증가|성장|급증)|revenue[^.!?\n]{0,35}(?:grew|growth|rose|increas)"),
 ("EARNINGS", "REVENUE_DECLINE", "매출감소", r"매출[^.!?\n]{0,35}(?:감소|하락|급감)|revenue[^.!?\n]{0,35}(?:fell|declin|decreas)"),
 ("EARNINGS", "EARNINGS_RELEASE", "실적발표", r"(?:분기|연간|잠정)?\s*실적\s*(?:발표|공개)|(?:quarterly|annual)\s+(?:results|earnings)"),
 ("PRODUCT", "HUMANOID_DEVELOPMENT", "휴머노이드공동개발", r"휴머노이드[^.!?\n]{0,65}공동\s*개발"),
 ("PRODUCT", "PRODUCT_DEVELOPMENT", "공동개발", r"공동\s*개발|co[- ]develop"),
 ("PRODUCT", "PRODUCT_RELEASE", "제품공개", r"(?:제품|솔루션|신형|로봇|모델|시스템)[^.!?\n]{0,35}(?:공개|출시|선보)|(?:unveils?|launches?|introduces?)[^.!?\n]{0,45}(?:product|model|system|robot)"),
 ("PRODUCT", "TECHNOLOGY_ADOPTION", "기술적용", r"(?:AI|디지털\s*트윈|GPU|인공지능)[^.!?\n]{0,35}(?:적용|도입|구동)|(?:applying|deploying)[^.!?\n]{0,30}(?:AI|digital twins)"),
 ("CONTRACT", "CONTRACT_SUPPLY", "공급계약", r"(?:공급|납품)\s*(?:계약|협약)|supply\s+(?:agreement|contract|deal)"),
 ("CONTRACT", "CONTRACT_ORDER", "신규수주", r"(?:신규|대형|대규모)\s*수주|수주\s*(?:확보|계약)"),
 ("CONTRACT", "PARTNERSHIP", "사업협력", r"(?:전략적|기술|사업)\s*(?:협력|제휴)|partner(?:ship|s?\s+with)|엔비디아와[^.!?\n]{0,30}협력"),
 ("OPERATIONS", "DEMAND_CAPACITY", "용량계약", r"(?:클라우드|AWS|컴퓨팅)[^.!?\n]{0,55}(?:용량|공급\s*능력)[^.!?\n]{0,35}(?:계약|예약)|capacity[^.!?\n]{0,35}(?:booked|contracted|reserved)"),
 ("OPERATIONS", "CUSTOMER_GROWTH", "고객증가", r"(?:고객|가입자|이용자)[^.!?\n]{0,35}(?:증가|급증|확대)|(?:customers|subscribers|users)[^.!?\n]{0,25}(?:growth|grew|rose)"),
 ("OPERATIONS", "PRODUCTION_EXPANSION", "생산확대", r"(?:생산|공장|설비)[^.!?\n]{0,35}(?:확대|증설)|capacity\s+expansion"),
 ("SECTOR", "SUPPLY_SHORTAGE", "공급부족", r"공급\s*부족|반도체\s*품귀|supply\s+shortage"),
 ("SECTOR", "DEMAND_OUTLOOK", "수요전망", r"(?:AI|반도체|메모리|클라우드)[^.!?\n]{0,30}수요[^.!?\n]{0,20}(?:전망|호조|증가|확대)|(?:strong|growing)\s+(?:AI\s+)?demand"),
 ("COMMODITY", "GOLD_PRICE_UP", "금값반등", r"(?:금값|금\s*가격)[^.!?\n]{0,20}(?:반등|상승)|gold\s+prices?[^.!?\n]{0,20}(?:rise|rebound|gain)"),
 ("COMMODITY", "OIL_PRICE_DOWN", "유가하락", r"유가[^.!?\n]{0,20}하락|oil\s+prices?[^.!?\n]{0,20}(?:fall|drop|declin)"),
 ("COMMODITY", "OIL_PRICE_UP", "유가상승", r"유가[^.!?\n]{0,20}(?:상승|급등)|oil\s+prices?[^.!?\n]{0,20}(?:rise|surge)"),
 ("MACRO", "RATE_CUT", "금리인하", r"금리\s*인하|interest\s+rate\s+cut"),
 ("MACRO", "INFLATION_EASING", "인플레완화", r"(?:인플레|인플레이션|물가)[^.!?\n]{0,25}(?:둔화|완화)|(?:easing|cooling)\s+inflation"),
 ("REGULATION", "POLICY_ELECTION", "선거정책", r"룰라[^.!?\n]{0,20}(?:재선|당선)|(?:선거|대선)[^.!?\n]{0,25}(?:승리|결과)|election\s+(?:victory|win|result)"),
 ("REGULATION", "EXPORT_CONTROL", "수출규제", r"수출\s*(?:통제|규제|제한)|export\s+(?:controls|restrictions)"),
 ("REGULATION", "TARIFF", "관세정책", r"관세[^.!?\n]{0,20}(?:인상|완화|부과|유예)|tariff[^.!?\n]{0,20}(?:raise|pause|cut|impos)"),
 ("CAPITAL", "SHARE_BUYBACK", "자사주매입", r"자사주[^.!?\n]{0,25}(?:매입|취득)|share\s+(?:repurchase|buyback)"),
 ("CAPITAL", "SPECIAL_DIVIDEND", "특별배당", r"특별\s*배당|special\s+dividend"),
 ("CAPITAL", "CAPITAL_RAISE", "자본조달", r"자본\s*조달|자금\s*조달|주식\s*공모|capital\s+rais|debt\s+(?:deal|financing)|stock\s+offering"),
 ("CAPITAL", "CAPITAL_STRUCTURE", "전환사채전환", r"전환\s*사채[^.!?\n]{0,30}전환|convertible\s+(?:bonds?|notes?)[^.!?\n]{0,25}conversion"),
 ("CAPITAL", "PRS_SETTLEMENT", "PRS상환", r"PRS[^.!?\n]{0,25}(?:상환|정산)"),
 ("CORPORATE", "MNA_NEGOTIATION", "인수협상", r"인수[^.!?\n]{0,25}(?:협상|검토|추진)|(?:acquisition|takeover)[^.!?\n]{0,25}talks|talks\s+to\s+acquire"),
 ("CORPORATE", "MNA_CONFIRMED", "인수계약", r"인수\s*계약[^.!?\n]{0,15}(?:체결|서명)|agrees?\s+to\s+(?:buy|acquire)"),
 ("CORPORATE", "STAKE_CHANGE", "지분변동", r"지분[^.!?\n]{0,35}(?:확대|매입|매각|양수|인수)|stake[^.!?\n]{0,25}(?:buys?|sells?|increas)"),
 ("PRODUCT", "CLINICAL_POSITIVE", "임상성과", r"임상[^.!?\n]{0,40}(?:호조|효능|성공|성과|목표\s*달성)|(?:trial|clinical)[^.!?\n]{0,35}(?:positive|met\s+.*endpoint)"),
 ("PRODUCT", "CLINICAL_RISK", "임상위험", r"임상[^.!?\n]{0,35}(?:실패|중단|부작용|목표\s*미달)|trial[^.!?\n]{0,25}(?:failed|halted)"),
 ("REGULATION", "REGULATORY_APPROVAL", "허가승인", r"(?:FDA|신약|품목)[^.!?\n]{0,25}승인|FDA\s+approv"),
 ("LEGAL", "LITIGATION", "소송", r"소송|lawsuit|litigation"),
 ("LEGAL", "RECALL", "제품리콜", r"리콜|product\s+recall"),
 ("FLOW", "FOREIGN_FLOW", "외국인순매도", r"외국인[^.!?\n]{0,25}순매도"),
 ("FLOW", "FOREIGN_BUY", "외국인순매수", r"외국인[^.!?\n]{0,25}순매수"),
 ("FLOW", "ETF_FLOW", "ETF자금유입", r"ETF[^.!?\n]{0,35}(?:자금\s*유입|순유입)|ETF[^.!?\n]{0,25}inflows"),
 ("FLOW", "SHORT_INTEREST", "공매도증가", r"공매도[^.!?\n]{0,25}(?:증가|급증)|short\s+interest[^.!?\n]{0,25}(?:rise|increas)"),
)

CONTEXT_RULES = (
 ("DRIVER", "밸류에이션부담", r"밸류에이션\s*부담|valuation\s+concerns"),
 ("SECTOR", "AI인프라", r"AI\s*(?:인프라|데이터센터)|AI\s+infrastructure"),
 ("SECTOR", "디지털트윈", r"디지털\s*트윈|digital\s+twins?"),
 ("SECTOR", "휴머노이드", r"휴머노이드|humanoid"),
 ("SECTOR", "로봇", r"로봇|\brobots?\b"),
 ("SECTOR", "금채굴", r"금\s*채굴|gold\s+mining"),
 ("SECTOR", "디지털금융", r"디지털\s*(?:금융|은행)|digital\s+bank"),
 ("METRIC", "HBM", r"\bHBM\b|고대역폭\s*메모리"),
 ("METRIC", "GPU", r"\bGPU\b"),
)
ACTORS = ("스티펠", "필립증권", "리링크", "골드만삭스", "모건스탠리",
          "번스타인", "UBS", "Stifel", "Phillip", "Leerink", "New Street Research")
_CACHE, _LOCK = {}, threading.Lock()


def _status(text):
    for status, pattern in (("negated", r"(?:않|없|부인|not\b|won.t\b)"),
                            ("considering", r"검토|협상|고려|talks|consider"),
                            ("planned", r"예정|계획|추진|승인|plans?\b|approved"),
                            ("forecast", r"전망|예상|추정|가능성|forecast|expects?|estimat")):
        if re.search(pattern, text, re.I):
            return status
    return "reported"


def classify_article(article, body_text=""):
    """Return grounded events and flexible keyword slots, including source spans."""
    fields = [("title", str(article.get("title") or "")),
              ("description", str(article.get("description") or "")),
              ("body", str(body_text or "")[:12000])]
    events, seen = [], set()
    for field, text in fields:
        target = re.search(r"목표\s*(?:주가|가격|가)[^.!?\n]{0,18}?(\d[\d,]*(?:\.\d+)?)\s*(달러|원)?\s*(?:→|에서|to)\s*(\d[\d,]*(?:\.\d+)?)\s*(달러|원)?", text, re.I)
        if target and not any(e["event_type"].startswith("ANALYST_TARGET_") for e in events):
            old, new = (float(target.group(i).replace(",", "")) for i in (1, 3))
            if old != new:
                direction = "UP" if new > old else "DOWN"
                label = "목표주가상향" if new > old else "목표주가하향"
                actors = [a for a in ACTORS if a.lower() in text.lower()]
                events.append({"family": "ANALYST", "event_type": "ANALYST_TARGET_" + direction,
                    "label": label, "status": "reported", "evidence_field": field,
                    "evidence_span": target.group(), "evidence_sentence": text[:700],
                    "actor": actors[0] if actors else "", "old_value": old, "new_value": new,
                    "unit": target.group(4) or target.group(2) or "",
                    "reported_numbers": [str(old), str(new)],
                    "source_url": article.get("url") or article.get("link") or ""})
                seen.add("ANALYST_TARGET_" + direction)
        rating = re.search(r"(매수|비중확대|중립|매도|buy|outperform|neutral|sell)\s*(?:에서|→|to)\s*(매수|비중확대|중립|매도|buy|outperform|neutral|sell)", text, re.I)
        if rating and "ANALYST_RATING_CHANGE" not in seen:
            ranks = {"매수": 2, "비중확대": 2, "buy": 2, "outperform": 2,
                     "중립": 1, "neutral": 1, "매도": 0, "sell": 0}
            old, new = (ranks[rating.group(i).lower()] for i in (1, 2))
            if old != new:
                actors = [a for a in ACTORS if a.lower() in text.lower()]
                events.append({"family": "ANALYST", "event_type": "ANALYST_RATING_CHANGE",
                    "label": "투자의견상향" if new > old else "투자의견하향", "status": "reported",
                    "old_rating": rating.group(1), "new_rating": rating.group(2),
                    "evidence_field": field, "evidence_span": rating.group(), "evidence_sentence": text[:700],
                    "actor": actors[0] if actors else "", "reported_numbers": [],
                    "source_url": article.get("url") or article.get("link") or ""})
                seen.add("ANALYST_RATING_CHANGE")
        for family, event_type, label, pattern in RULES:
            if event_type in seen:
                continue
            match = re.search(pattern, text, re.I)
            if not match:
                continue
            left = max(text.rfind(".", 0, match.start()), text.rfind("\n", 0, match.start())) + 1
            right = re.search(r"[.!?\n]", text[match.end():])
            end = match.end() + right.start() if right else len(text)
            clause = text[left:end].strip()
            status = _status(clause)
            if status == "negated":
                continue
            if event_type == "CONTRACT_SUPPLY" and re.search(r"MOU|양해\s*각서|협약", clause, re.I):
                status, label = "memorandum", "공급협약"
            suffix = {"considering": "검토", "planned": "계획", "forecast": "전망"}.get(status, "")
            if suffix and event_type in {"MNA_CONFIRMED", "SHARE_BUYBACK", "SPECIAL_DIVIDEND", "CONTRACT_SUPPLY", "PRODUCT_RELEASE"}:
                label += suffix
            actors = [a for a in ACTORS if a.lower() in clause.lower()]
            # A plain target value never proves an upgrade or downgrade.
            numbers = re.findall(r"(?<![A-Za-z0-9])\d[\d,]*(?:\.\d+)?\s*(?:달러|원|%|billion|million)?", clause)
            events.append({"family": family, "event_type": event_type, "label": label,
                           "status": status, "evidence_field": field,
                           "evidence_span": match.group(), "evidence_sentence": clause[:700],
                           "actor": actors[0] if actors else "", "reported_numbers": numbers[:8],
                           "source_url": article.get("url") or article.get("link") or ""})
            seen.add(event_type)
    # Targets with only a number are metrics, not direction changes.
    text = " ".join(value for _, value in fields)
    contexts = []
    for role, label, pattern in CONTEXT_RULES:
        match = re.search(pattern, text, re.I)
        if match:
            contexts.append({"role": role, "label": label, "evidence_span": match.group()})
    keyword_details = [{"role": "EVENT", "label": e["label"],
                        "evidence_span": e["evidence_span"], "event_type": e["event_type"]}
                       for e in events]
    if events:
        keyword_details += [{"role": "ACTOR", "label": e["actor"],
                             "evidence_span": e["actor"]} for e in events if e["actor"]]
        keyword_details += contexts
    labels, details = [], []
    for detail in keyword_details:
        if detail["label"] not in labels:
            labels.append(detail["label"])
            details.append(detail)
        if len(labels) == 3:
            break
    failures = []
    if not events:
        failures.append("NO_SUPPORTED_EVENT")
    if re.search(r"진로\s*교육|고교생|경품|사전예약\s*방법", fields[0][1] + " " + fields[1][1]):
        failures.append("PROMOTIONAL_OR_BACKGROUND")
    return {"taxonomy_version": TAXONOMY_VERSION, "events": events,
            "families": list(dict.fromkeys(e["family"] for e in events)),
            "keywords": labels, "keyword_details": details,
            "contexts": contexts, "failure_labels": failures}


def cluster_events(articles, company):
    """Merge only strong identical facts. Article display remains untouched."""
    groups = {}
    for article in articles:
        for event in (article.get("event_classification") or {}).get("events", []):
            # Do not merge different target prices/brokers based on labels alone.
            strong = event.get("actor") and event.get("reported_numbers")
            identity = [company, event["event_type"], event.get("actor"),
                        event.get("reported_numbers"), event["status"],
                        str(article.get("published_at") or "")[:10]]
            if not strong:
                identity.append(event["source_url"])
            key = hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()[:24]
            group = groups.setdefault(key, {"event_id": key, "company": company,
                "event_type": event["event_type"], "family": event["family"],
                "label": event["label"], "status": event["status"], "facts": [], "source_urls": []})
            if event["source_url"] not in group["source_urls"]:
                group["source_urls"].append(event["source_url"])
                group["facts"].append(event)
    return list(groups.values())


def clean_original_excerpt(text):
    """Reject page furniture as prose, without hiding the source article."""
    if re.search(r"Google 검색에서|저작권법의 보호|무단 전재|사전 허가 없는|프리미엄9.*구독", text):
        return ""
    return text


def _needs_korean(text):
    return bool(re.search(r"[A-Za-z]{4}", text)) and not bool(re.search(r"[가-힣]", text))


def translate_records(records, previous=None):
    """Translate original text only through the existing Groq account, in batches.

    Never translate an unavailable body into a generated summary. Failures retain
    the original article, flag pending translation, and retry on a later refresh.
    """
    previous = previous or {}
    pending = []
    for index, record in enumerate(records):
        original = {k: str(record.get(k) or "") for k in ("title", "description", "summary")}
        key = hashlib.sha256(json.dumps(original, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        prior = previous.get(key)
        with _LOCK:
            cached = _CACHE.get(key)
        if isinstance(prior, dict):
            cached = prior
        if cached:
            record.update(cached)
            record["translation_key"] = key
            continue
        if not any(_needs_korean(v) for v in original.values()):
            continue
        record["translation_status"] = "pending"
        pending.append((index, key, original))
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        return records
    for start in range(0, min(len(pending), 2), 2):
        batch = pending[start:start + 2]
        inputs = [{"id": i, **{k: v[:1800] for k, v in original.items()}}
                  for i, _, original in batch]
        payload = {"model": "openai/gpt-oss-20b", "temperature": 0,
            "reasoning_effort": "low", "max_completion_tokens": 2500,
            "response_format": {"type": "json_object"}, "messages": [
             {"role": "system", "content": "금융 기사 번역기다. 입력의 title, description, summary를 각각 한국어로 충실히 번역한다. 요약하거나 새 사실·인과·키워드를 추가하지 않는다. 숫자·통화·회사명·부정·검토/예정/전망 상태를 보존한다. 빈 문자열은 빈 문자열로 둔다. 이미 한국어인 항목은 그대로 둔다. JSON {\"items\":[{\"id\":정수,\"title\":문자열,\"description\":문자열,\"summary\":문자열}]}만 반환한다."},
             {"role": "user", "content": json.dumps(inputs, ensure_ascii=False)}]}
        request = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode(), method="POST",
            headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                result = json.load(response)
            choice = result["choices"][0]
            if choice.get("finish_reason") == "length":
                raise ValueError("translation_truncated")
            values = json.loads(choice["message"]["content"])["items"]
            found = {r["id"]: r for r in values if isinstance(r, dict) and type(r.get("id")) is int}
            for i, key, original in batch:
                translated = found.get(i, {})
                valid = True
                for field, source in original.items():
                    target = translated.get(field)
                    if not isinstance(target, str) or (not source and target) or (source and not target):
                        valid = False
                        break
                    if _needs_korean(source) and not re.search(r"[가-힣]", target):
                        valid = False
                        break
                    # Exact numeric tokens must survive translation; no new figures.
                    number = lambda s: sorted(re.findall(r"\d+(?:[,.]\d+)*", s))
                    if number(source[:1800]) != number(target):
                        valid = False
                        break
                if not valid:
                    continue
                cached = {k: translated[k] for k in original}
                cached.update(translation_status="translated", original_text=original)
                records[i].update(cached)
                records[i]["translation_key"] = key
                with _LOCK:
                    if len(_CACHE) > 4000:
                        _CACHE.clear()
                    _CACHE[key] = cached
        except Exception as exc:
            print("[news translation] failed=" + type(exc).__name__, flush=True)
    return records


def select_issue_articles(articles, briefs, company, aliases=(), previous=(), now=None):
    """Select source-backed company events, preserve the article feed separately.

    No minimum price move is required: the issue must exist before its reaction.
    Stable IDs and original timestamps let later price observations join the event.
    """
    from datetime import datetime, timezone, timedelta
    from email.utils import parsedate_to_datetime
    now = now or datetime.now(timezone.utc)
    def stamp(value):
        try:
            try:
                d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except ValueError:
                d = parsedate_to_datetime(str(value))
            return d.astimezone(timezone.utc) if d.tzinfo else None
        except (ValueError, TypeError, OverflowError):
            return None
    names = [str(n).lower().strip() for n in (company, *aliases) if str(n).strip()]
    def mentions(text):
        text = re.sub(r"\s+", "", str(text).lower())
        for name in names:
            token = re.sub(r"\s+", "", name)
            if re.fullmatch(r"[a-z0-9.]{1,5}", token):
                if re.search(r"(?<![a-z0-9])" + re.escape(token) + r"(?![a-z0-9])", text):
                    return True
            elif token and token in text:
                return True
        return False
    selected = {}
    rejected = []
    for article, brief in zip(articles, briefs):
        classification = article.get("event_classification") or {}
        if "PROMOTIONAL_OR_BACKGROUND" in classification.get("failure_labels", []):
            rejected.append({"url": article.get("url"), "reason": "PROMOTIONAL_OR_BACKGROUND"})
            continue
        events = []
        for event in classification.get("events", []):
            if mentions(event.get("evidence_sentence")):
                events.append(event)
            elif mentions(article.get("title")) and re.search(
                r"(?:이 회사|회사[는가]|동사|the company|its )", event.get("evidence_sentence", ""), re.I
            ):
                events.append(event)
        if not events:
            rejected.append({"url": article.get("url"), "reason": "NO_COMPANY_EVENT_EVIDENCE"})
            continue
        main = events[0]
        # Use exact reported actor+facts for research notes. For less structured
        # events only merge highly similar concrete evidence, never a label alone.
        evidence = re.sub(r"\s+", "", str(main.get("evidence_span") or "")).lower()
        strong = main.get("actor") and main.get("reported_numbers")
        identity = [company, main["event_type"], main.get("status"), main.get("actor"),
                    main.get("reported_numbers") if strong else evidence,
                    "" if strong else str(article.get("original_title") or article.get("title"))]
        issue_id = hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()[:24]
        sources = [s for s in brief.get("source_articles", []) if stamp(s.get("published_at"))]
        if not sources:
            continue
        first = min(stamp(s["published_at"]) for s in sources)
        if not now - timedelta(hours=24) <= first <= now:
            continue
        entry = dict(brief)
        entry.update(issue_id=issue_id, selection_revision=1, selected_events=events,
                     event_types=list(dict.fromkeys(e["event_type"] for e in events)),
                     _issue_first_published_at=first.isoformat(),
                     _issue_expires_at=(first+timedelta(hours=24)).isoformat(),
                     reaction_anchor_at=first.isoformat(),
                     reaction_status="awaiting_market_observation",
                     selection_reason="company_event_with_cited_evidence")
        # Display only the selected company's grounded event labels. An event
        # belonging to another company in the same article must not supply tags.
        entry["tags"] = list(dict.fromkeys(e["label"] for e in events))[:3]
        if issue_id in selected:
            existing = selected[issue_id]
            known = {s.get("url") for s in existing["source_articles"]}
            existing["source_articles"].extend(s for s in sources if s.get("url") not in known)
            if first < stamp(existing["_issue_first_published_at"]):
                for field in ("_issue_first_published_at", "_issue_expires_at", "reaction_anchor_at"):
                    existing[field] = entry[field]
        else:
            selected[issue_id] = entry
    # Retain selected issues across refreshes/Top50 churn until their original
    # 24h expiry. Never preserve the old unselected article-as-issue snapshots.
    for old in previous or []:
        if old.get("selection_revision") != 1 or not old.get("issue_id"):
            continue
        expiry = stamp(old.get("_issue_expires_at"))
        if not expiry or expiry <= now:
            continue
        issue_id = old["issue_id"]
        if issue_id not in selected:
            selected[issue_id] = dict(old)
        else:
            current = selected[issue_id]
            prior_first = stamp(old.get("_issue_first_published_at"))
            if prior_first and prior_first < stamp(current["_issue_first_published_at"]):
                for field in ("_issue_first_published_at", "_issue_expires_at", "reaction_anchor_at"):
                    current[field] = old[field]
            # Reaction observations must survive text/translation refreshes.
            for field in ("stock_reactions", "reaction_observations", "reaction_status"):
                if old.get(field):
                    current[field] = old[field]
    result = sorted(selected.values(), key=lambda b:b["_issue_first_published_at"], reverse=True)
    return result, rejected
