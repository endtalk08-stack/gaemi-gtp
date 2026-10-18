"""Panel may show older genuine articles; AI source window and DB TTL stay unchanged."""
import datetime
import pathlib
import unittest
from backend.analysis.news.storyboard import build_simple_today_news


class NewsPanelWindowTests(unittest.TestCase):
    def test_weekend_news_visible_without_reusing_it_as_daily_ai_evidence(self):
        old_time=(datetime.datetime.now(datetime.timezone.utc)
                  - datetime.timedelta(hours=48)).isoformat()
        row={"title":"Nebius existing report","description":"Dated company report",
             "published_at":old_time,"url":"https://example.org/nebius"}
        self.assertEqual(build_simple_today_news([row], "네비우스 그룹",limit=None), [])
        panel=build_simple_today_news([row], "네비우스 그룹",limit=None,
                                      max_age_hours=7*24)
        self.assertEqual([x["title"] for x in panel], ["Nebius existing report"])

    def test_presentation_only_contract(self):
        root=pathlib.Path(__file__).resolve().parents[1]
        result=(root/"backend/services/news_result.py").read_text()
        engine=(root/"backend/services/engine.py").read_text()
        frontend=(root/"frontend/widgets/analysis-data/analysis-data.js").read_text()
        self.assertIn('"paired_news_items": paired_news_items', result)
        self.assertIn('"panel_news_items": recent_news[:20]', result)
        self.assertIn('"panel_news_items": news_result.get("panel_news_items"', engine)
        self.assertIn('Array.isArray(result?.panel_news_items)', frontend)

if __name__=="__main__":
    unittest.main()
