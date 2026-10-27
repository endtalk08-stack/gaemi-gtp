"""Selected issues display provider text without changing stored keywords."""
import ast
import copy
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('freshness_under_test', ROOT / 'backend/services/news_freshness.py')
freshness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(freshness)

class ProviderIssueDisplayTests(unittest.TestCase):
    def payload(self):
        now = datetime.now(timezone.utc)
        issues, articles = [], []
        for i in range(5):
            stamp = (now-timedelta(minutes=i+1)).isoformat()
            url = f'https://publisher.example/{i}'
            issues.append({'headline':'기존 사건 제목', 'summary':'원문 확인 불가',
                'tags':['휴머노이드공동개발', f'기존태그{i}'],
                'stock_names':['엔비디아'], 'evidence_source':'original_unavailable',
                'source_articles':[{'title':f'원 기사 제목 {i}', 'url':url, 'published_at':stamp}]})
            articles.append({'title':f'원 기사 제목 {i}', 'description':'[핵심포인트] 제공 내용… 하나… 둘… 마침표 없음',
                'url':url, 'published_at':stamp, 'article_keywords':['휴머노이드공동개발',f'기존태그{i}']})
        return {'_title_only_revision':3, '_code_fact_extraction_version':3,
                '_code_issue_briefs':list(reversed(issues)), 'paired_news_items':articles,
                'storyboard_news_items':copy.deepcopy(articles)}, now

    def test_provider_text_latest_three_and_exact_keywords(self):
        payload, now = self.payload(); before = copy.deepcopy(payload)
        out = freshness.clean_us_snapshot(payload, now=now)
        self.assertEqual(len(out['issue_briefs']),3)
        for i, brief in enumerate(out['issue_briefs']):
            self.assertEqual(brief['headline'],f'원 기사 제목 {i}')
            self.assertEqual(brief['summary'],payload['paired_news_items'][i]['description'])
            self.assertEqual(brief['tags'],['휴머노이드공동개발',f'기존태그{i}'])
        self.assertEqual(payload,before)
        self.assertEqual(len(out['paired_news_items']),5)

    def test_missing_body_keeps_title_tags_and_source(self):
        payload, now = self.payload(); payload['paired_news_items'][0]['description']=''
        payload['storyboard_news_items'][0]['description']=''
        out = freshness.clean_us_snapshot(payload,now=now)['issue_briefs'][0]
        self.assertEqual(out['headline'],'원 기사 제목 0')
        self.assertEqual(out['summary'],'')
        self.assertEqual(out['tags'],['휴머노이드공동개발','기존태그0'])
        self.assertTrue(out['source_articles'])

    def test_expired_issue_is_not_replaced_by_unselected_panel_news(self):
        payload, now = self.payload()
        for brief in payload['_code_issue_briefs']:
            brief['source_articles'][0]['published_at']=(now-timedelta(hours=25)).isoformat()
        self.assertEqual(freshness.clean_us_snapshot(payload,now=now)['issue_briefs'],[])

    def test_display_does_not_blank_or_shorten_provider_text(self):
        payload, now = self.payload()
        result = freshness.clean_us_snapshot(payload,now=now)
        parsed = ast.parse((ROOT/'backend/services/news_result.py').read_text())
        helper = next(n for n in parsed.body if isinstance(n,ast.FunctionDef)
                      and n.name=='_sanitize_news_display_briefs')
        scope={'re':re}
        exec(compile(ast.Module(body=[helper],type_ignores=[]),'display-only','exec'),scope)
        before=copy.deepcopy(result['issue_briefs'])
        after=scope['_sanitize_news_display_briefs'](result,market='미국')
        self.assertEqual([(b['headline'],b['summary'],b['tags']) for b in after['issue_briefs']],
                         [(b['headline'],b['summary'],b['tags']) for b in before])

if __name__=='__main__': unittest.main()
