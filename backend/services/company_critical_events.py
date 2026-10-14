"""Conservative, article-grounded company material events for stock issues.

Only explicit occurrences are recognized, not inferred price causes. Selected
company linkage and publication freshness remain handled by existing callers.
"""

import re

_COMPANY_CRITICAL_RULES = (
    ("신용등급상향", "신용등급 상향", "positive", r"신용\s*등급(?:을|이)?\s*(?:상향|상승|격상|올렸|높였)"),
    ("신용등급하향", "신용등급 하향", "negative", r"신용\s*등급(?:을|이)?\s*(?:하향|강등|하락|낮췄|내렸)"),
    ("채무상환완료", "채무 상환 완료", "positive", r"(?:채무|차입금|회사채)[^.!?\n]{0,28}(?:전액\s*)?상환(?:을)?\s*(?:완료|마쳤|끝냈)|(?:채무|차입금|회사채)\s*전액\s*상환"),
    ("채무불이행", "채무 불이행", "negative", r"(?:채무\s*불이행|대출금\s*연체)[^.!?\n]{0,15}(?:발생|확정|공시|통보|결정)"),
    ("자본잠식해소", "자본잠식 해소", "positive", r"자본\s*잠식[^.!?\n]{0,14}(?:해소|탈피|벗어나|벗어났)"),
    ("자본잠식", "자본잠식 발생", "negative", r"자본\s*잠식[^.!?\n]{0,14}(?:발생|확정|공시|상태에\s*진입)"),
    ("감사의견적정", "감사의견 적정", "positive", r"감사\s*의견[^.!?\n]{0,12}(?<!부)적정(?:을\s*받|으로\s*변경|으로\s*회복|으로\s*확정|\b)"),
    ("감사의견거절", "감사의견 거절", "negative", r"감사\s*의견[^.!?\n]{0,12}(?:거절|부적정|한정)(?:\s*판정|\s*통보|\s*확정|\s*의견)?"),
    ("거래재개", "거래 재개", "positive", r"(?:주식\s*|주권\s*)?거래\s*재개(?:\s*(?:결정|확정|공시|발표))?"),
    ("거래정지", "거래정지", "negative", r"(?:주식\s*|주권\s*)?거래\s*정지\s*(?:결정|조치|확정|공시|통보|발표)"),
    ("상장유지결정", "상장 유지 결정", "positive", r"상장\s*유지\s*(?:결정|확정|판정)"),
    ("상장폐지결정", "상장폐지 결정", "negative", r"상장\s*폐지\s*(?:결정|확정|의결|통보)"),
    ("계약해지", "계약 해지", "negative", r"(?:공급\s*|대형\s*|납품\s*)?계약\s*(?:해지|취소|파기)(?:\s*(?:결정|공시|통보|발표|확정))?"),
    ("수주취소", "수주 취소", "negative", r"(?:대형\s*|신규\s*)?수주\s*(?:취소|철회)(?:\s*(?:결정|공시|통보|확정))?"),
    ("유상증자결정", "유상증자 결정", "neutral", r"유상\s*증자\s*(?:결정|공시|확정|발표)"),
    ("유상증자철회", "유상증자 철회", "neutral", r"유상\s*증자\s*(?:철회|취소)(?:\s*(?:결정|공시|발표))?"),
    ("횡령배임혐의", "횡령·배임 혐의", "negative", r"(?:횡령|배임)(?:\s*[·,/및과]\s*(?:횡령|배임))?\s*혐의(?:가)?\s*(?:발생|제기|확인|공시|고발|수사)"),
)

_UNCONFIRMED = re.compile(
    r"사실무근|부인했|부인한다|부인\b|반박|루머|\b가짜뉴스\b|아니다|아니라|아님|아닌|"
    r"(?:가능성|우려|검토|추진|예상|전망|관측|설|의혹|미확정|논의)"
)


def company_critical_title_and_tags(text, limit=None):
    """Return one title, all distinct grounded tags, and an event direction."""
    events, covered = [], []
    for clause_no, clause in enumerate(re.split(r"(?<=[.!?])\s+", str(text or ""))):
        if _UNCONFIRMED.search(clause):
            continue
        # Conflicting rating actions require a separate chronology review.
        if re.search(r"신용\s*등급[^.!?\n]{0,40}(?:상향[^.!?\n]{0,20}하향|하향[^.!?\n]{0,20}상향)", clause):
            continue
        found = []
        for order, (tag, heading, direction, pattern) in enumerate(_COMPANY_CRITICAL_RULES):
            match = re.search(pattern, clause, flags=re.IGNORECASE)
            if match:
                # Never promote an action explicitly canceled in its own sentence.
                suffix = clause[match.end():match.end() + 16]
                if re.search(r"철회|취소|번복|무효|해제|없음|않|아님|아니", suffix):
                    continue
                found.append((match.start(), order, match.end(), tag, heading, direction))
        found.sort()
        for start, _, end, tag, heading, direction in found:
            if any(i == clause_no and start < e and end > s for i, s, e in covered):
                continue
            if any(e[0] == tag for e in events):
                continue
            events.append((tag, heading, direction))
            covered.append((clause_no, start, end))
            if limit is not None and len(events) >= max(1, int(limit)):
                break
        if limit is not None and len(events) >= max(1, int(limit)):
            break
    if not events:
        return "", [], ""
    directions = {e[2] for e in events if e[2] != "neutral"}
    tone = next(iter(directions)) if len(directions) == 1 else "mixed" if directions else "neutral"
    return events[0][1] + " 이슈", [e[0] for e in events], tone
