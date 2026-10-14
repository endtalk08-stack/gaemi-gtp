import importlib.util
import pathlib
import unittest

MODULE = pathlib.Path(__file__).resolve().parents[1] / 'backend/services/news_ai_briefs.py'
spec = importlib.util.spec_from_file_location('news_ai_briefs_test', MODULE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class TestNewsAiBriefs(unittest.TestCase):
    def setUp(self):
        self.briefs = [{
            'headline': '사업 제휴 이슈', 'summary': '종전 기사 문장.',
            'tags': ['사업제휴', 'AI투자'], 'time': '14:32',
            'reaction_at': '2026-10-14T04:00:00+00:00',
        }]
        self.articles = [{
            'title': 'LS머트리얼즈, 미국 기업에 690억원 규모 UC 공급계약 체결',
            'description': 'AI 데이터센터 설비에 UC를 공급한다. 2027년 4월부터 납품 예정.',
            'published_at': '2026-10-14T04:00:00+00:00',
        }]
        self.body = ['LS머트리얼즈가 미국 기업과 690억원 규모 UC 공급 계약을 체결했다. '
                     '회사는 AI 데이터센터 수요에 대응한다. 납품은 2027년 4월 시작할 예정이라고 밝혔다.']

    def test_preserves_headline_tags_time(self):
        stories = mod._input_stories(self.briefs, self.articles, self.body)
        self.assertEqual(len(stories), 1)
        raw = '{"items":[{"id":1,"summary":"LS머트리얼즈가 미국 기업과 690억원 규모의 UC 공급 계약을 체결했다. 2027년 4월부터 AI 데이터센터 관련 납품을 시작할 예정이라고 밝혔다."}]}'
        got = mod._apply_response(self.briefs, stories, raw)
        self.assertEqual(got[0]['headline'], '사업 제휴 이슈')
        self.assertEqual(got[0]['tags'], ['사업제휴', 'AI투자'])
        self.assertEqual(got[0]['time'], '14:32')
        self.assertIn('690억원', got[0]['summary'])
        self.assertEqual(self.briefs[0]['summary'], '종전 기사 문장.')

    def test_rejects_fabricated_number(self):
        stories = mod._input_stories(self.briefs, self.articles, self.body)
        raw = '{"items":[{"id":1,"summary":"LS머트리얼즈가 미국 기업과 999억원 공급계약을 발표했다. 회사는 이 계약을 통해 매출 확대를 기대한다고 밝혔다."}]}'
        got = mod._apply_response(self.briefs, stories, raw)
        self.assertEqual(got, self.briefs)

    def test_rejects_unknown_story(self):
        stories = mod._input_stories(self.briefs, self.articles, self.body)
        got = mod._apply_response(self.briefs, stories, '{"items":[{"id":2,"summary":"다른 기업이 새로운 계약을 진행한다고 설명했다. 관련 내용은 추후 확인이 필요하다."}]}')
        self.assertEqual(got, self.briefs)

    def test_disabled_does_not_call_ai(self):
        import os
        from unittest.mock import patch
        with patch.dict(os.environ, {'GROQ_API_KEY': '', 'AI_TEST_ENABLED': '0'}):
            self.assertIs(mod.enrich_issue_briefs('LS머트리얼즈', self.briefs, self.articles, self.body), self.briefs)


if __name__ == '__main__':
    unittest.main()
