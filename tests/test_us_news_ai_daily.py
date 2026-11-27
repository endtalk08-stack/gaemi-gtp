import datetime as dt
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from backend import us_news_ai_daily as job

UTC = dt.timezone.utc
# Wednesday 2026-11-25 10:30 New York (00:30 KST Thursday).
RUN_AT = dt.datetime(2026, 11, 25, 15, 30, tzinfo=UTC)


def article(title, hours_ago, url_id, source="연합뉴스", description="요약"):
    return {"title": title, "url": f"https://news.example/{url_id}", "source": source,
            "description": description,
            "published_at": (RUN_AT - dt.timedelta(hours=hours_ago)).isoformat()}


GOOD = {"headline_keyword": "장기 공급계약 확대",
        "keywords": ["중국 HBM 경쟁", "장기 공급계약 확대", "AI 메모리 수요"],
        "lines": ["마이크론이 AI 데이터센터용 메모리 장기 공급계약을 확대했어요.",
                  "고객사 조달 안정성이 높아져 메모리 업종 분위기가 좋아졌어요.",
                  "마이크론은 HBM 등 고성능 메모리를 만드는 미국 반도체 기업이에요."],
        "confidence": "high", "source_ids": [1]}


class SelectArticlesTest(unittest.TestCase):
    def test_keeps_only_recent_titles_naming_the_company(self):
        stock = {"name": "마이크론 테크놀로지", "symbol": "MU"}
        raw = [
            article("[미국 특징주] 마이크론, HBM 시장서 도전 직면", 3, 1),
            article("코스피·코스닥 동반 급등…외국인 저가 매수", 1, 2),          # no company in title
            article("Micron raises outlook", 5, 3, source="Reuters"),
            article("마이크론 옛날 기사", 100, 4),                              # older than 72h
            article("마이크론, 장기 공급계약 확대", 2, 1),                       # duplicate URL
        ]
        with patch.object(job, "title_terms", return_value={"마이크론", "micron", "mu"}):
            picked = job.select_articles(stock, raw, now=RUN_AT)
        self.assertEqual([a["title"] for a in picked],
                         ["[미국 특징주] 마이크론, HBM 시장서 도전 직면", "Micron raises outlook"])


class ValidateTest(unittest.TestCase):
    def test_good_result_passes(self):
        self.assertEqual(job.validate(GOOD, 3), [])

    def test_rule_violations_are_caught(self):
        cases = {
            "keywords": {**GOOD, "keywords": GOOD["keywords"][:2]},
            "headline_keyword": {**GOOD, "headline_keyword": "다른 키워드"},
            "lines": {**GOOD, "lines": GOOD["lines"][:2]},
            "number_in_lines": {**GOOD, "lines": ["주가가 6.4% 올랐어요.", *GOOD["lines"][1:]]},
            "source_ids": {**GOOD, "source_ids": [9]},
            "high_without_sources": {**GOOD, "source_ids": []},
        }
        for problem, result in cases.items():
            self.assertIn(problem, job.validate(result, 3), problem)


class CallGroqTest(unittest.TestCase):
    def test_retries_once_after_rate_limit(self):
        calls, waits = [], []
        body = {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(GOOD)}}],
                "usage": {"total_tokens": 2500}}

        class Response(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *a): return False

        def opener(request, timeout):
            calls.append(request)
            if len(calls) == 1:
                raise urllib.error.HTTPError(request.full_url, 429, "rate", {"retry-after": "20"}, None)
            return Response(json.dumps(body).encode())

        result, tokens = job.call_groq("msg", api_key="k", opener=opener, sleeper=waits.append)
        self.assertEqual(result, GOOD)
        self.assertEqual(tokens, 2500)
        self.assertEqual(waits, [20.0])
        payload = json.loads(calls[0].data)
        self.assertEqual(payload["response_format"]["type"], "json_schema")


class RunTest(unittest.TestCase):
    def setUp(self):
        self.state_path = Path(tempfile.mkdtemp()) / "state.json"
        self.uploads = []
        self.sleeps = []
        self.stocks = [
            {"rank": 1, "symbol": "MU", "name": "마이크론 테크놀로지", "price": 621.1, "change_pct": 6.26,
             "reference_close_date": "2026-11-24"},
            {"rank": 2, "symbol": "SNDK", "name": "샌디스크", "price": 75.0, "change_pct": 10.2,
             "reference_close_date": "2026-11-24"},
        ]

    def analyze(self, stock, profiles):
        if stock["symbol"] == "SNDK":
            return "no_news", None, [], None
        articles = [{"title": "마이크론, 장기 공급계약 확대", "url": "https://news.example/1",
                     "source": "제민일보", "_published": RUN_AT}]
        return "ok", GOOD, articles, 2586

    def run_job(self, **kw):
        return job.run(RUN_AT, top20=lambda: self.stocks, analyze=self.analyze,
                       upload=lambda payload, key: self.uploads.append((key, payload)),
                       state_path=self.state_path, sleeper=self.sleeps.append, **kw)

    def test_publishes_each_stock_and_the_top20_list(self):
        with patch.object(job, "us_trading_day", return_value=dt.date(2026, 11, 25)):
            outcome = self.run_job()
        self.assertEqual(outcome["counts"], {"ok": 1, "no_news": 1})
        self.assertEqual([key for key, _ in self.uploads], ["news/ai/us/MU.json", "news/ai/us/TOP20.json"])
        mu = self.uploads[0][1]
        self.assertEqual(mu["headline_keyword"], "장기 공급계약 확대")
        self.assertEqual(mu["change_pct"], 6.26)                      # number from Kiwoom, not the model
        self.assertEqual(mu["sources"][0]["url"], "https://news.example/1")
        top = self.uploads[1][1]
        self.assertEqual([i["symbol"] for i in top["items"]], ["MU", "SNDK"])
        self.assertEqual(top["items"][1]["status"], "no_news")
        self.assertEqual(self.sleeps, [job.PACE_SECONDS])
        state = json.loads(self.state_path.read_text())
        self.assertEqual(state["last_day"], "2026-11-25")
        self.assertIn("MU", state["profiles"])                         # company line reused next time

    def test_runs_once_per_day(self):
        with patch.object(job, "us_trading_day", return_value=dt.date(2026, 11, 25)):
            self.run_job()
            self.uploads.clear()
            self.assertEqual(self.run_job()["status"], "already_ran")
        self.assertEqual(self.uploads, [])

    def test_day_is_reserved_before_any_analysis(self):
        def boom(stock, profiles):
            self.assertEqual(json.loads(self.state_path.read_text())["last_day"], "2026-11-25")
            raise RuntimeError("groq down")
        with patch.object(job, "us_trading_day", return_value=dt.date(2026, 11, 25)):
            job.run(RUN_AT, top20=lambda: self.stocks, analyze=boom,
                    upload=lambda payload, key: self.uploads.append((key, payload)),
                    state_path=self.state_path, sleeper=self.sleeps.append)
        self.assertEqual([key for key, _ in self.uploads], ["news/ai/us/TOP20.json"])

    def test_skips_holidays_and_weekends(self):
        thanksgiving = dt.datetime(2026, 11, 26, 15, 30, tzinfo=UTC)
        saturday = dt.datetime(2026, 11, 28, 15, 30, tzinfo=UTC)
        self.assertIsNone(job.us_trading_day(thanksgiving))
        self.assertIsNone(job.us_trading_day(saturday))
        self.assertEqual(job.us_trading_day(RUN_AT), dt.date(2026, 11, 25))


if __name__ == "__main__":
    unittest.main()
