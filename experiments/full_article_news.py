"""Standalone, code-only full-article news experiment. Not imported by the live app.

Run:
    python -m experiments.full_article_news --url "https://publisher.example/article"
    python -m experiments.full_article_news --file article.txt

Requires a verifiable FULL article body. Unknown formats return "not_supported"
instead of reusing the source headline or inventing facts. No database writes.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from backend.services.news_byline import strip_leading_news_credit
from backend.services.news_detail import _ArticleHTMLParser

_MAX_BYTES = 1_500_000
_MAX_CHARS = 60_000
_EVENTS = (
    ("AI데이터센터", r"AI|인공지능"),
    ("투자", r"투자|투입"),
    ("사업확대", r"사업\s*확대|사업\s*영역"),
    ("공급계약", r"공급\s*계약|납품\s*계약"),
    ("임상시험", r"임상\s*[123]상|임상시험"),
    ("실적", r"영업이익|매출|순이익"),
    ("수요증가", r"수요\s*증가|수요\s*확대"),
    ("목표가상향", r"목표\s*주가\s*상향"),
)
_SENTS = re.compile(r"(?<=[.!?])\s+(?=[가-힣A-Za-z0-9\"“‘(])")


@dataclass(frozen=True)
class OriginalBody:
    text: str
    source_kind: str


def read_article_html(url: str) -> OriginalBody:
    """One-off TEST reader: inspect full JSON-LD body or all article/main paragraphs.

    Existing production reader truncates at 5,000 characters; bypass that
    excerpt cap in the experiment without modifying the production reader.
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("https_article_url_required")
    request = urllib.request.Request(
        url, headers={"User-Agent": "gaemiGTP-experiment/1.0",
                      "Accept": "text/html,application/xhtml+xml"},
    )
    with urllib.request.urlopen(request, timeout=9) as response:
        mime = str(response.headers.get("Content-Type") or "").lower()
        if "html" not in mime:
            raise ValueError("not_html")
        data = response.read(_MAX_BYTES + 1)
        if len(data) > _MAX_BYTES:
            raise ValueError("article_page_too_large")
        charset = response.headers.get_content_charset() or "utf-8"
    parser = _ArticleHTMLParser()
    parser.feed(data.decode(charset, errors="replace"))
    parser.close()
    if parser.json_article_body:
        body, kind = parser.json_article_body, "jsonld_article_body"
    elif parser.preferred_paragraphs:
        body, kind = " ".join(parser.preferred_paragraphs), "article_or_main_paragraphs"
    else:
        raise ValueError("verified_full_body_unavailable")
    body = strip_leading_news_credit(html.unescape(re.sub(r"\s+", " ", body)).strip())
    if len(body) > _MAX_CHARS:
        raise ValueError("article_body_over_limit")
    return OriginalBody(body, kind)


def _sentences(text: str) -> list[str]:
    # Do not treat isolated headings / advertisements as article facts.
    return [s.strip() for s in _SENTS.split(re.sub(r"\s+", " ", text))
            if len(s.strip()) >= 12]


def _actor(sentences: list[str]) -> str:
    first = " ".join(sentences[:2])
    patterns = (
        r"(?:모빌리티\s+및\s+특수\s+프로모션\s+)?전문기업\s+([가-힣A-Za-z0-9·-]{2,25})(?=[이가은는의\s])",
        r"(?:미국\s+)?제약사\s+([가-힣A-Za-z0-9·-]{2,25})(?=[이가은는의\s])",
        r"(?:세계\s+최대\s+)?(?:클라우드\s+서비스\s+기업)\s+([가-힣A-Za-z0-9·-]{2,25})(?=[이가은는의\s])",
        r"(?:일론\s+)?(머스크)(?=[가은는의\s])",
        r"^([가-힣A-Za-z0-9·-]{2,25})(?:가|은|는)\s",
    )
    for pattern in patterns:
        m = re.search(pattern, first)
        if m:
            return re.sub(r"(?:이|가|은|는|의)$", "", m.group(1))
    return ""


def _new_story(body: str) -> tuple[str, list[str], list[str]]:
    """Rule-based fact synthesis across the ENTIRE article, not first 2-3 sentences.

    Each successful branch uses multiple independently checked facts. This
    first experiment deliberately supports only a few event structures.
    """
    sentences = _sentences(body)
    full = " ".join(sentences)
    actor = _actor(sentences)
    title = ""
    paragraphs: list[str] = []
    evidence: list[str] = []

    # An investment POSSIBILITY is never upgraded to a confirmed investment.
    amount = re.search(r"최대\s*(\d[\d,]*(?:조|억)?\s*(?:달러|원))", full)
    possibility = re.search(r"(?:투입할\s*수\s*있|가능성|분석이\s*나왔다|관측)", full)
    if actor and "데이터센터" in full and "AI" in full and amount and possibility:
        title = f"{actor}, AI 데이터센터 최대 {amount.group(1)} 투자 가능성"
        paragraphs = [
            f"{actor}의 AI 데이터센터 사업과 관련해 최대 {amount.group(1)} 규모의 투자 가능성이 거론됐다.",
            "이는 확정된 투자 발표가 아니라 기사에서 제시한 전망 또는 분석이다.",
        ]
        evidence = ["AI", "데이터센터", amount.group(1), possibility.group(0)]
        if "테슬라" in full and "스페이스X" in full and re.search(r"합병을?\s*추진", full):
            paragraphs.append("테슬라와 스페이스X의 합병 추진도 해당 보도에서 함께 다뤄졌다.")
            evidence.append("합병")
        if "컴퓨팅 인프라" in full:
            paragraphs.append("보도는 AI 컴퓨팅 인프라 구축을 사업 구상의 주요 배경으로 설명했다.")
            evidence.append("컴퓨팅 인프라")

    # News actor is the company which acquired the vehicles, NOT manufacturer.
    elif actor and "사이버트럭" in full and re.search(r"(?:다수\s*)?확보", full) and "사업 확대" in full:
        title = f"{actor}, 사이버트럭 확보해 모빌리티 사업 확대"
        paragraphs = [
            f"{actor}이 사이버트럭 차량을 확보해 관련 모빌리티 사업을 넓힐 계획이다.",
        ]
        evidence = [actor, "사이버트럭", "확보", "사업 확대"]
        uses = [(r"광고", "광고"), (r"렌트|차량\s*대여", "차량 대여"),
                (r"촬영\s*지원|촬영", "촬영 지원"), (r"의전", "의전")]
        activities = [label for pattern, label in uses if re.search(pattern, full)]
        if activities:
            paragraphs.append("기사에서 제시한 활용 분야는 " + "·".join(activities) + " 등이다.")
            evidence += [matched.group(0) for pattern, _ in uses
                         if (matched := re.search(pattern, full))]
        if re.search(r"복수\s*차량|여러\s*대|다수", full) and "행사" in full:
            paragraphs.append("여러 대의 차량을 활용한 행사 운영도 사업 계획에 포함됐다.")
            evidence.append("행사")

    # A clinical efficacy report with verified study phase and observed facts.
    elif actor and re.search(r"암\s*백신", full) and re.search(r"(?:임상\s*)?3상", full):
        risk = re.search(r"(?:재발|사망)\s*(?:또는\s*사망)?\s*위험[^.!?]{0,70}?(\d{1,2}(?:\.\d+)?)%\s*(?:낮췄|감소|줄였)", full)
        if risk:
            title = f"{actor} 암백신, 임상 3상서 재발 위험 {risk.group(1)}% 감소"
            paragraphs = [
                f"{actor}의 암백신 임상 3상에서 재발 관련 위험이 {risk.group(1)}% 낮아진 결과가 보고됐다.",
                "해당 수치는 기사에 제시된 임상시험 결과로, 모든 환자에게 동일한 효과를 보장하는 것은 아니다.",
            ]
            evidence = [actor, "암백신", "3상", risk.group(1) + "%"]
            if "MSD" in full or "머크" in full:
                paragraphs.append("임상시험은 공동 개발사와 진행한 연구로 소개됐다.")
                evidence.append("공동 개발")
            drop = re.search(r"주가[^.!?]{0,42}?(\d{1,2}(?:\.\d+)?)%\s*(?:가까이\s*)?급락", full)
            if drop:
                paragraphs.append(f"반면 주가는 보도에서 {drop.group(1)}% 가까이 급락한 것으로 전해졌다.")
                evidence.append(drop.group(1) + "%")

    # General high-level result if strict templates have no faithful coverage.
    if not title or len(title) > 48 or len(paragraphs) < 2:
        return "", [], []
    return title, paragraphs, evidence


def compose_news(full_article: str, source_url: str, *, source_kind: str = "verified_full_body") -> dict:
    """Prepare a title + self-composed article body; never store/publish."""
    source = re.sub(r"\s+", " ", strip_leading_news_credit(full_article)).strip()
    base = {"status": "not_supported", "source_url": source_url,
            "source_kind": source_kind, "article_length": len(source),
            "headline": "", "body": "", "tags": [], "reason": ""}
    if len(source) < 240 or len(_sentences(source)) < 4:
        return {**base, "reason": "full_body_not_verified_or_too_short"}
    if len(source) > _MAX_CHARS:
        return {**base, "reason": "source_over_limit"}
    title, paragraphs, evidence = _new_story(source)
    if not title:
        return {**base, "reason": "unsupported_or_ambiguous_article"}
    # Guard against accidental verbatim sentence reuse, source headline copying,
    # and conclusions with no trace in the article.
    if any(line in source for line in paragraphs) or any(word not in source for word in evidence):
        return {**base, "reason": "unsupported_fact_or_verbatim_copy"}
    tags = [name for name, pattern in _EVENTS if re.search(pattern, source)][:4]
    return {**base, "status": "experimental", "reason": "",
            "headline": title, "body": "\n\n".join(paragraphs),
            "tags": tags, "evidence_terms": evidence}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Offline/one-off full-article news experiment")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", help="Test publisher article URL (read-only)")
    group.add_argument("--file", help="UTF-8 text file containing the complete article")
    args = ap.parse_args(argv)
    try:
        if args.url:
            article = read_article_html(args.url)
            result = compose_news(article.text, args.url, source_kind=article.source_kind)
        else:
            raw = Path(args.file).read_text(encoding="utf-8")
            result = compose_news(raw, Path(args.file).name)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] == "experimental" else 2
    except Exception as e:
        print(json.dumps({"status": "not_supported", "reason": str(e)},
                         ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    sys.exit(main())
