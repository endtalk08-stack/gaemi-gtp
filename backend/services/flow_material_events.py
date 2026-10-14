"""Explicit investor flow and index membership news, not inferred price causes."""
import re

_RULES = (
    ("기관순매수", "기관 순매수", "positive", r"(?:기관|기관투자자)[^.!?\n]{0,8}(?:순\s*매수|매수\s*우위)"),
    ("기관순매도", "기관 순매도", "negative", r"(?:기관|기관투자자)[^.!?\n]{0,8}(?:순\s*매도|매도\s*우위)"),
    ("연기금순매수", "연기금 순매수", "positive", r"연기금[^.!?\n]{0,8}순\s*매수"),
    ("연기금순매도", "연기금 순매도", "negative", r"연기금[^.!?\n]{0,8}순\s*매도"),
    ("프로그램순매수", "프로그램 순매수", "positive", r"프로그램[^.!?\n]{0,8}순\s*매수"),
    ("프로그램순매도", "프로그램 순매도", "negative", r"프로그램[^.!?\n]{0,8}순\s*매도"),
    ("대주주지분매수", "대주주 지분 매수", "positive", r"(?:대주주|최대\s*주주)[^.!?\n]{0,22}(?:지분|주식)[^.!?\n]{0,12}(?:매입|매수|취득)"),
    ("대주주지분매각", "대주주 지분 매각", "negative", r"(?:대주주|최대\s*주주)[^.!?\n]{0,22}(?:지분|주식)[^.!?\n]{0,12}(?:매각|매도|처분)"),
    ("블록딜매각", "블록딜 매각", "neutral", r"(?:블록딜|시간외\s*대량\s*매매)[^.!?\n]{0,12}(?:매각|매도|실시|체결)"),
    ("보호예수해제", "보호예수 해제", "neutral", r"보호\s*예수[^.!?\n]{0,12}(?:해제|만료|종료)"),
    ("보호예수연장", "보호예수 연장", "neutral", r"보호\s*예수[^.!?\n]{0,12}(?:연장|재설정)"),
    ("지수편입", "지수 편입", "positive", r"(?:MSCI|코스피\s*200|코스닥\s*150|S&P\s*500)[^.!?\n]{0,24}(?:신규\s*)?편입(?:\s*(?:확정|결정|발표))?"),
    ("지수편출", "지수 편출", "negative", r"(?:MSCI|코스피\s*200|코스닥\s*150|S&P\s*500)[^.!?\n]{0,24}편출(?:\s*(?:확정|결정|발표))?"),
    ("공매도급증", "공매도 급증", "negative", r"공매도[^.!?\n]{0,14}(?:급증|폭증|크게\s*증가)"),
    ("공매도급감", "공매도 급감", "positive", r"공매도[^.!?\n]{0,14}(?:급감|크게\s*감소)"),
    ("반대매매발생", "반대매매 발생", "negative", r"반대\s*매매[^.!?\n]{0,14}(?:발생|실행|급증)"),
)
_UNCONFIRMED = re.compile(r"가능성|우려|관측|예상|예정|검토|부인|사실무근|루머|의혹|추진|거론|계획|설")


def flow_material_title_and_tags(text, limit=None):
    found, ranges, tags = [], [], []
    for n, clause in enumerate(re.split(r"(?<=[.!?])\s+", str(text or ""))):
        if _UNCONFIRMED.search(clause):
            continue
        for rank, (tag, title, tone, pattern) in enumerate(_RULES):
            match = re.search(pattern, clause, flags=re.IGNORECASE)
            if match:
                found.append((n, match.start(), rank, match.end(), tag, title, tone))
    found.sort()
    for n, start, _, end, tag, title, tone in found:
        if any(i == n and start < e and end > s for i, s, e in ranges):
            continue
        if tag in [e[0] for e in tags]:
            continue
        tags.append((tag, title, tone))
        ranges.append((n, start, end))
        if limit is not None and len(tags) >= max(1, int(limit)):
            break
    if not tags:
        return "", [], ""
    tones = {t[2] for t in tags if t[2] != "neutral"}
    tone = next(iter(tones)) if len(tones) == 1 else "mixed" if tones else "neutral"
    return tags[0][1] + " 이슈", [t[0] for t in tags], tone
