#!/usr/bin/env bash
set -euo pipefail
cd /opt/gaemigtp-news/app
export PYTHONPATH=/opt/gaemigtp-news/app
venv=/opt/gaemigtp-news/venv/bin/python
test -x "$venv"
test -f ops/.article-facts-v2.next
test -f ops/.news-result-facts-v2.next
backup="$(mktemp -d ./ops/.code-facts-v2-backup.XXXXXX)"
cp -p backend/services/article_fact_keywords.py "$backup/article_fact_keywords.py"
cp -p backend/services/news_result.py "$backup/news_result.py"
cp -p backend/services/news_processed_store.py "$backup/news_processed_store.py"
rollback() {
  trap - ERR
  set +e
  install -m 644 "$backup/article_fact_keywords.py" backend/services/article_fact_keywords.py
  install -m 644 "$backup/news_result.py" backend/services/news_result.py
  install -m 644 "$backup/news_processed_store.py" backend/services/news_processed_store.py
  sudo -n /usr/bin/systemctl restart gaemigtp-news.service
  echo CODE_FACTS_V2_ROLLED_BACK
  exit 1
}
trap rollback ERR
"$venv" - <<'PY'
from pathlib import Path
import ast
p=Path('backend/services/news_processed_store.py')
s=p.read_text()
anchor='            payload = row[1] if isinstance(row[1], dict) else {}\n'
if s.count(anchor)!=1:raise RuntimeError('Live read_signature changed')
if 'normalized["issue_briefs"] = normalized.get("_code_issue_briefs") or []' not in s:
    raise RuntimeError('Live code issue display patch missing')
patch=(
    '            # Refresh each old US snapshot once with source-grounded issue facts.\n'
    '            if market in ("미국", "US") and payload.get("_code_fact_extraction_version") != 2:\n'
    '                return None\n'
)
s=s.replace(anchor,anchor+patch,1)
ast.parse(s)
p.write_text(s)
PY
install -m 644 ops/.article-facts-v2.next backend/services/article_fact_keywords.py
install -m 644 ops/.news-result-facts-v2.next backend/services/news_result.py
"$venv" -m py_compile backend/services/article_fact_keywords.py backend/services/news_result.py backend/services/news_processed_store.py
"$venv" - <<'PY'
from datetime import datetime,timezone
from backend.services.article_fact_keywords import build_article_fact_briefs
news=[{
    'title':'모더나 암 백신 재발·사망 위험 42% 감소',
    'description':'모더나가 임상 3상 결과를 발표했다.',
    'url':'https://example.com/a',
    'published_at':datetime.now(timezone.utc).isoformat()
}]
result=build_article_fact_briefs(news,'모더나',price_change_pct=-2.45)
assert len(result)==1 and '42%' in result[0]['headline']
assert result[0]['evidence_source']=='article_title_description_price_context'
print('CODE_FACTS_V2_SMOKE_OK')
PY
sudo -n /usr/bin/systemctl restart gaemigtp-news.service
test "$(systemctl is-active gaemigtp-news.service)" = active
trap - ERR
echo CODE_FACTS_V2_LIVE_ACTIVATED
