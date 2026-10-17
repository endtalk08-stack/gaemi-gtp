"""Offline-testable issue evidence orchestration; not wired to production."""
from staged_issue_links import validate_links
from staged_issue_evidence import persist_issue_evidence


def save_verified_evidence(conn, issues, links, collected_ids, issue_ids):
    """Only persist independently verified mappings; no automatic guessing."""
    if len(issue_ids) != len(issues) or any(type(x) is not int or x <= 0 for x in issue_ids):
        raise ValueError('Issue IDs must correspond to issues')
    if len(set(issue_ids)) != len(issue_ids):
        raise ValueError('Duplicate issue IDs')
    mapped = validate_links(len(issues), links, collected_ids)
    counts = []
    for issue_id, article_ids in zip(issue_ids, mapped):
        counts.append(persist_issue_evidence(conn, issue_id, article_ids))
    return counts
