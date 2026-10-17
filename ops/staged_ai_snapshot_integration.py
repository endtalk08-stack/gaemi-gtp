"""Staged integration with the existing processed snapshot payload.

Pure functions only. Never call AI, open a DB connection, or write snapshots.
"""
from copy import deepcopy
from staged_ai_issue_display_adapter import to_issue_briefs


def with_ai_issue_briefs(result_payload, issues, *, display_time, stock_names, sources_by_issue=None):
    """Replace only issue_briefs, retaining all existing news and analysis data."""
    if not isinstance(result_payload, dict):
        raise ValueError("Expected existing snapshot JSON object")
    briefs = to_issue_briefs(issues, display_time, stock_names, sources_by_issue=sources_by_issue)
    updated = deepcopy(result_payload)
    updated["issue_briefs"] = briefs
    return updated
