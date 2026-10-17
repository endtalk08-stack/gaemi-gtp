"""Prepare AI issues for the existing issue_briefs snapshot field.

This adapter is staged only. The collector owns timestamps and stock identity.
"""
import json
from staged_daily_groq_issues import parse_issues


def to_issue_briefs(issues, display_time, stock_names):
    validated = parse_issues(json.dumps({"issues": issues}, ensure_ascii=False))
    if not isinstance(display_time, str):
        raise ValueError("Invalid display time")
    if not isinstance(stock_names, list) or any(
        not isinstance(name, str) or not name.strip() for name in stock_names
    ):
        raise ValueError("Invalid stock names")
    return [
        {
            "time": display_time,
            "reaction_at": "",
            "headline": issue["headline"],
            "summary": issue["summary"],
            "tags": issue["tags"],
            "stock_names": stock_names[:4],
        }
        for issue in validated
    ]
