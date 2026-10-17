"""Staged Groq issue response validator; not connected to the worker."""
import json

MODEL = "openai/gpt-oss-20b"
PROMPT = """주가에 영향을 줄 핵심 이슈를 0-3개 선정해.

제목은 핵심 짧게, 내용은 쉽게 설명 , 해시태그는 각각 최대 3개. 반말로 답변해

한국어 JSON만 반환해:

{"issues":[{"headline":"제목","summary":"내용","tags":["#핵심어"]}]}"""


def parse_issues(response_text):
    result = json.loads(response_text)
    if not isinstance(result, dict) or set(result) != {"issues"}:
        raise ValueError("Invalid issue response")
    issues = result["issues"]
    if not isinstance(issues, list) or len(issues) > 3:
        raise ValueError("Expected 0-3 issues")
    for item in issues:
        if not isinstance(item, dict) or set(item) != {"headline", "summary", "tags"}:
            raise ValueError("Invalid fields")
        if any(not isinstance(item[k], str) or not item[k].strip() for k in ("headline", "summary")):
            raise ValueError("Invalid text")
        tags = item["tags"]
        if not isinstance(tags, list) or len(tags) > 3 or any(not isinstance(t, str) or not t.startswith("#") for t in tags):
            raise ValueError("Invalid tags")
    return issues
