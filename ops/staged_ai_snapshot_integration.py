"""Staged integration with the existing processed snapshot payload.

Pure functions only. Never call AI, open a DB connection, or write snapshots.
"""
from copy import deepcopy
from staged_ai_issue_display_adapter import to_issue_briefs


def with_ai_issue_briefs(result_payload, issues, *, display_time, stock_names,
                         sources_by_issue=None, exchange_day=None):
    """AI is primary for 'why moved'; original code issues remain separately saved.

    No provider calls, new collections, or changes to raw article/quote content.
    An empty AI result stays empty on US issue displays; code remains internal.
    """
    if not isinstance(result_payload, dict):
        raise ValueError("Expected existing snapshot JSON object")
    briefs = to_issue_briefs(issues, display_time, stock_names, sources_by_issue=sources_by_issue)
    updated = deepcopy(result_payload)
    code_briefs = deepcopy(updated.get("_code_issue_briefs", updated.get("issue_briefs") or []))
    updated["_code_issue_briefs"] = code_briefs
    updated["_ai_issue_briefs"] = briefs
    if exchange_day is not None:
        updated["_ai_exchange_day"] = exchange_day.isoformat()
    updated["issue_briefs"] = briefs
    return updated
