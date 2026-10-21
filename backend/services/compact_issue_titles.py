"""Display-only concise domestic issue headlines. shared-v1 extractor stays unchanged."""
import re
from .shared_v1_issue_titles import clean

def compact_issue_title(extracted, article_title):
    """Shorten a selected event title using only wording in its source headline."""
    source=clean(article_title)
    source=re.sub(r"\s*\[[^\]]{1,30}\]\s*$","",source).strip()
    # News headline contains the clearest complete event; leave the extractor
    # untouched and shorten just the selected brief display label.
    clauses=[part.strip(" ,.:…") for part in re.split(r"…|[|｜]",source) if part.strip(" ,.:…")]
    if not clauses:
        return clean(extracted)
    first=clauses[0]
    # A leading named subject before a comma is unnecessary on a stock-specific panel.
    first=re.sub(r"^[^,，]{2,28}[,，]\s*","",first)
    first=re.sub(r"\b\d+\s*(?:일|주|달|개월)\s*앞당겨\s*","",first)
    if len(clauses)>1 and len(first)<=23:
        second=clauses[1]
        if len(second)<=13 and re.search(r"(?:완료|예정|확정|검토|추진)",second):
            joined=first+"·"+second
            if len(joined)<=32:
                return joined
    if len(first)<=27:
        return first
    # Append a short second event clause only when it carries the completion
    # state of the preceding first headline (e.g. 전량 소각 예정).
    if len(first)<=29:
        return first
    # Prefer coherent, source-derived clauses over truncating characters.
    fragments=[s.strip(" ,.:") for s in re.split(r"[,，·] ",first) if s.strip(" ,.:")]
    for part in fragments:
        if 8<=len(part)<=27 and re.search(r"(?:완료|예정|전망|추진|확대|계약|흑자|실적|공급|매입|소각|합병|투자|돌파|상향|하향)",part):
            return part
    return first
