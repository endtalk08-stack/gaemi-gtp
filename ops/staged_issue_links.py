"""Validate reviewed links from issues to collected articles."""

def validate_links(issue_count, links, collected_ids):
    if type(issue_count) is not int or not 0 <= issue_count <= 3:
        raise ValueError('Invalid issue count')
    if not isinstance(links, dict) or set(links) != set(range(issue_count)):
        raise ValueError('Missing issue links')
    if not isinstance(collected_ids, (list, tuple, set)):
        raise ValueError('Invalid collected articles')
    if any(type(x) is not int or x <= 0 for x in collected_ids):
        raise ValueError('Invalid collected article ID')
    allowed = set(collected_ids)
    output = []
    for index in range(issue_count):
        ids = links[index]
        if not isinstance(ids, list) or not ids:
            raise ValueError('Missing evidence')
        if any(type(x) is not int or x <= 0 or x not in allowed for x in ids):
            raise ValueError('Unsupported evidence')
        output.append(list(dict.fromkeys(ids)))
    return output
