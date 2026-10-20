"""Isolated one-shot prompt test for US market close.

Invoked only by the root-owned, restricted systemd runner. Uses the live,
unchanged NAVER collector and 120B generator. Publishes only after validating
a substantive JSON response. Does not affect stock issue AI.
"""
import datetime as dt
import json
import os
from pathlib import Path

from backend.services import us_market_close as close

PROMPT_FILE = Path("/run/gaemi-us-close-test/prompt.txt")
NY = close.NY


def latest_closed_session(now):
    ny = now.astimezone(NY)
    date = ny.date()
    if ny.hour < 16:
        date -= dt.timedelta(days=1)
    while date.weekday() >= 5:
        date -= dt.timedelta(days=1)
    return date


def validate_analysis(raw, article_count):
    result = json.loads(raw)
    if not isinstance(result, dict) or not isinstance(result.get("issues"), list):
        raise ValueError("expected_issues_json")
    issues = result["issues"]
    if not 1 <= len(issues) <= 3:
        raise ValueError("issue_count_out_of_range")
    for index, item in enumerate(issues):
        if not isinstance(item, dict):
            raise ValueError("issue_not_object")
        title = item.get("headline")
        summary = item.get("summary")
        tags = item.get("tags")
        source_ids = item.get("source_ids")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("missing_headline")
        if not isinstance(summary, str) or len(summary.strip()) < 200:
            raise ValueError("summary_too_short")
        if not isinstance(tags, list) or not all(
            isinstance(tag, str) and tag.startswith("#") and 1 < len(tag) <= 60
            for tag in tags
        ):
            raise ValueError("invalid_tags")
        if (index != len(issues) - 1 and tags) or (
            index == len(issues) - 1 and (len(tags) != 3 or len(set(tags)) != 3)
        ):
            raise ValueError("exactly_three_final_tags_required")
        if not isinstance(source_ids, list) or not source_ids or any(
            type(item_id) is not int or not 1 <= item_id <= article_count
            for item_id in source_ids
        ):
            raise ValueError("invalid_source_ids")
    return result


def main():
    prompt = PROMPT_FILE.read_text(encoding="utf-8").strip()
    if not 300 <= len(prompt) <= 12000:
        raise ValueError("invalid_prompt_length")
    now = dt.datetime.now(dt.timezone.utc)
    session_date = latest_closed_session(now)
    print(f"US_CLOSE_TEST_SESSION={session_date.isoformat()}", flush=True)
    articles = close.collect_articles(session_date, now_utc=now)
    print(f"US_CLOSE_TEST_SELECTED={len(articles)}", flush=True)
    if not articles:
        raise RuntimeError("no_post_close_naver_articles")
    # Override only the in-memory prompt for this one test process.
    close.US_CLOSE_PROMPT = prompt
    raw = close._generate(articles, session_date)
    issues = validate_analysis(raw, len(articles))
    manifest = [
        {key: article[key] for key in ("title", "url", "published_at", "publisher")}
        for article in articles
    ]
    # The prior published answer remains intact until the Groq call AND
    # validation succeed. Only the one daily US-close record is changed.
    with close._connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO public.us_market_close_briefs
                   (session_date,status,content,published_at,expires_at,source_manifest,model)
                   VALUES (%s,'published',%s,now(),now()+interval '24 hours',%s::jsonb,%s)
                   ON CONFLICT (session_date) DO UPDATE SET
                     status='published',content=EXCLUDED.content,
                     published_at=EXCLUDED.published_at,
                     expires_at=EXCLUDED.expires_at,
                     source_manifest=EXCLUDED.source_manifest,
                     model=EXCLUDED.model""",
                (session_date, raw, json.dumps(manifest, ensure_ascii=False), close.MODEL),
            )
    print(
        "US_CLOSE_TEST_PUBLISHED " +
        json.dumps({
            "session_date": session_date.isoformat(),
            "source_count": len(articles),
            "issue_count": len(issues["issues"]),
            "summary_chars": [len(i["summary"]) for i in issues["issues"]],
            "tags_at_end": issues["issues"][-1]["tags"],
            "model": close.MODEL,
        }, ensure_ascii=False),
        flush=True,
    )


if __name__ == "__main__":
    main()
