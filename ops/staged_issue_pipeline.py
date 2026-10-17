"""Offline-testable issue evidence orchestration; not wired to production."""
from staged_issue_links import validate_links
from staged_issue_evidence import persist_issue_evidence


def save_verified_evidence(conn, issues, links, collected_ids, issue_ids):
    """Caller supplies reviewed mappings; membership checks do not prove factual support."""
    if not isinstance(issues, list) or not isinstance(issue_ids, (list, tuple)):
        raise ValueError('Invalid issue input')
    if len(issue_ids) != len(issues) or any(type(x) is not int or x <= 0 for x in issue_ids):
        raise ValueError('Issue IDs must correspond to issues')
    if len(set(issue_ids)) != len(issue_ids):
        raise ValueError('Duplicate issue IDs')
    mapped = validate_links(len(issues), links, collected_ids)
    if not mapped:
        return []
    # psycopg3 nested transactions use savepoints. If any issue fails,
    # rollback all evidence writes from this call, not just the last issue.
    if conn is None or not callable(getattr(conn, 'transaction', None)):
        raise ValueError('Transactional connection required')
    with conn.transaction():
        return [persist_issue_evidence(conn, issue_id, article_ids)
                for issue_id, article_ids in zip(issue_ids, mapped)]
