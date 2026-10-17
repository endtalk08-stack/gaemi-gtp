"""Read-only presentation fix for accidental AI timestamp labels."""
import unittest
from backend.services.news_result import _sanitize_news_display_briefs

class IssueTimeDisplayTests(unittest.TestCase):
    def test_removes_unrequested_article_and_ai_labels(self):
        data={"issue_briefs":[{"headline":"실제 이슈","summary":"원문","time":"기사 발행 10.15 06:58 · AI 분석 08:00"}]}
        result=_sanitize_news_display_briefs(data)
        self.assertEqual(result["issue_briefs"][0]["time"],"06:58")
        self.assertEqual(result["issue_briefs"][0]["summary"],"원문")
        self.assertEqual(result["issue_briefs"][0]["headline"],"실제 이슈")
    def test_removes_unrequested_ai_only_label(self):
        data={"issue_briefs":[{"headline":"소식","summary":"본문","time":"AI 분석 2026-10-18 07:16"}]}
        self.assertEqual(_sanitize_news_display_briefs(data)["issue_briefs"][0]["time"],"07:16")
    def test_keeps_existing_plain_time_and_unrelated_code_briefs(self):
        data={"issue_briefs":[{"headline":"기존 코드","summary":"본문","time":"06:23"}]}
        self.assertEqual(_sanitize_news_display_briefs(data)["issue_briefs"][0]["time"],"06:23")
    def test_keeps_invalid_or_freeform_times_unchanged(self):
        data={"issue_briefs":[{"headline":"뉴스","summary":"본문","time":"예상"}]}
        self.assertEqual(_sanitize_news_display_briefs(data)["issue_briefs"][0]["time"],"예상")

if __name__=="__main__":
    unittest.main()
