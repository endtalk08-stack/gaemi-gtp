"""Evidence-bound business, demand and industry catalysts missing from legacy topics."""
import re

# Complements legacy company-event extraction; never infers a movement from stock price.
_RULES = (
    ("실적전망상향", "실적 전망 상향", "positive", r"(?:실적\s*전망|가이던스)[^.!?\n]{0,12}(?:상향|높였|올렸)"),
    ("실적전망하향", "실적 전망 하향", "negative", r"(?:실적\s*전망|가이던스)[^.!?\n]{0,12}(?:하향|낮췄|내렸)"),
    ("고객사발주확대", "고객사 발주 확대", "positive", r"(?:고객사|주요\s*고객)[^.!?\n]{0,18}(?:발주|주문)[^.!?\n]{0,12}(?:확대|증가|급증)"),
    ("고객사발주축소", "고객사 발주 축소", "negative", r"(?:고객사|주요\s*고객)[^.!?\n]{0,18}(?:발주|주문)[^.!?\n]{0,12}(?:축소|감소|취소|중단)"),
    ("수주잔고증가", "수주잔고 증가", "positive", r"수주\s*잔고[^.!?\n]{0,14}(?:증가|확대|급증|사상\s*최대)"),
    ("수주잔고감소", "수주잔고 감소", "negative", r"수주\s*잔고[^.!?\n]{0,14}(?:감소|축소|급감)"),
    ("공급과잉", "공급과잉", "negative", r"(?:반도체|배터리|철강|석유화학|메모리|D램|낸드)[^.!?\n]{0,24}공급\s*과잉"),
    ("공급부족", "공급 부족", "positive", r"(?:반도체|배터리|철강|석유화학|메모리|D램|낸드)[^.!?\n]{0,24}공급\s*부족"),
    ("재고증가", "재고 증가", "negative", r"(?:제품\s*|완성품\s*)?재고[^.!?\n]{0,12}(?:급증|증가|누적|쌓여|확대)"),
    ("재고감소", "재고 감소", "positive", r"(?:제품\s*|완성품\s*)?재고[^.!?\n]{0,12}(?:감소|축소|급감|소진)"),
    ("생산중단", "생산 중단", "negative", r"(?:공장|생산\s*라인|생산)[^.!?\n]{0,20}(?:가동\s*중단|생산\s*중단|일시\s*중단)"),
    # Match explicitly postponed product schedules, never hypothetical delays.
    ("제품일정연기", "양산·출시 일정 연기", "negative",
     r"(?:양산|출시)\s*(?:시점|일정|계획|예정일)(?:을|이|은|는)?[^.!?\n]{0,55}?"
     r"(?:미뤘|연기했|늦췄|연기(?:됐다|되었|한다)?|미뤄|지연(?:됐|되었|된다)?)"),
    ("생산재개", "생산 재개", "positive", r"(?:공장|생산\s*라인|생산)[^.!?\n]{0,20}(?:가동\s*재개|생산\s*재개|정상\s*가동)"),
    ("임상시험성공", "임상시험 성공", "positive", r"(?:임상(?:\s*\d상)?|임상\s*시험)[^.!?\n]{0,25}(?:성공|목표\s*달성)"),
    ("임상시험실패", "임상시험 실패", "negative", r"(?:임상(?:\s*\d상)?|임상\s*시험)[^.!?\n]{0,25}(?:실패|목표\s*미달)"),
    ("신약승인", "신약 승인", "positive", r"(?:신약|치료제)[^.!?\n]{0,24}(?:허가|승인)\s*(?:획득|받아|완료|확정)"),
    ("신약승인거절", "신약 승인 거절", "negative", r"(?:신약|치료제)[^.!?\n]{0,24}(?:허가|승인)[^.!?\n]{0,12}(?:거절|불허|반려)"),
)
_FALSE_CONTEXT = re.compile(r"(?:가능성|우려|루머|부인|사실무근|아니라|아니다|검토|관측|예상|전망치|추측|철회|번복|취소)")


def business_material_title_and_tags(text, limit=None):
    """Return one named event and all distinct tags only on explicit evidence."""
    matches, ranges, tags = [], [], []
    for n, clause in enumerate(re.split(r"(?<=[.!?])\s+", str(text or ""))):
        if _FALSE_CONTEXT.search(clause):
            continue
        for pos, (tag, heading, tone, pattern) in enumerate(_RULES):
            m = re.search(pattern, clause, flags=re.IGNORECASE)
            if m:
                matches.append((n, m.start(), pos, m.end(), tag, heading, tone))
    matches.sort()
    for n, start, _, end, tag, heading, tone in matches:
        if tag in [row[0] for row in tags]:
            continue
        if any(i == n and start < b and end > a for i, a, b in ranges):
            continue
        tags.append((tag, heading, tone))
        ranges.append((n, start, end))
        if limit is not None and len(tags) >= max(1, int(limit)):
            break
    if not tags:
        return "", [], ""
    directions = {row[2] for row in tags}
    tone = next(iter(directions)) if len(directions) == 1 else "mixed"
    return tags[0][1] + " 이슈", [row[0] for row in tags], tone
