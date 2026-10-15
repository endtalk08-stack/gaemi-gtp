"""Display-only removal of attributed Korean news byline prefixes.

Strip only recognisable LEADING press credits; preserve substantive sentences,
article titles, source metadata, and original links without an outlet allowlist.
"""
from __future__ import annotations

import re

_NAME = r"(?:[가-힣]{2,5}|[A-Za-z][A-Za-z .'-]{1,32})"
_ROLE = r"(?:(?:인턴|수습|객원)\s*)?(?:기자|특파원|통신원)"
_BYLINE = rf"{_NAME}(?:\s*[·ㆍ,]\s*{_NAME}){{0,2}}\s*{_ROLE}"
_SOURCE = r"[가-힣A-Za-z0-9][가-힣A-Za-z0-9\s&·ㆍ.+/'()\-]{0,58}?"
_BAR = r"[|｜│]"
_DATELINE = r"(?:서울|세종|부산|인천|대구|대전|광주|울산|제주|수원|뉴욕|워싱턴|런던|도쿄|베이징|상하이|파리|로이터|AP)"
_PATTERNS = tuple(re.compile(pattern, re.IGNORECASE) for pattern in (
    # | 스마트비즈 = 김혜인 기자 | / │ ZDNET Korea : John Kim 기자 │
    rf"^\s*{_BAR}\s*{_SOURCE}\s*[:=]\s*{_BYLINE}\s*{_BAR}\s*",
    # [한경=김민수 기자] / 【스마트비즈 = 김혜인 기자】
    rf"^\s*[\[【(]\s*{_SOURCE}\s*[:=]\s*{_BYLINE}\s*[\]】)]\s*(?:{_BAR}\s*)?",
    # 스마트비즈 = 김혜인 기자 / 연합뉴스: 김민지 특파원
    rf"^\s*(?:{_BAR}\s*)?{_SOURCE}\s*[:=]\s*{_BYLINE}\s*(?:{_BAR}\s*)?",
    # 매일경제 김민수 기자 = / 전자신문 이나리 기자 |
    rf"^\s*(?:{_BAR}\s*)?{_SOURCE}\s+{_BYLINE}\s*(?:[:=]|{_BAR})\s*",
    # 김철수 기자 = / 홍길동 특파원 :
    rf"^\s*(?:{_BAR}\s*)?{_BYLINE}\s*(?:[:=]|{_BAR})\s*",
    # (서울=뉴스1) 홍길동 기자 = / 【세종=뉴시스】김철수 기자=
    rf"^\s*[\[(【]\s*{_DATELINE}\s*=\s*[^\])】\]]{{2,36}}[\])】\]]\s*(?:{_BYLINE}\s*[:=]?\s*)?",
))


def strip_leading_news_credit(text: str) -> str:
    """Remove well-formed opening credits only; leave actual prose intact."""
    content = str(text or "").strip()
    for _ in range(4):
        for pattern in _PATTERNS:
            match = pattern.match(content)
            if match:
                content = content[match.end():].lstrip()
                break
        else:
            break
    return content
