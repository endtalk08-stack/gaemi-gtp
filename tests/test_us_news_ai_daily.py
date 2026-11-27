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


GOOD = {"type": "reason", "headline_keyword": "장기 공급계약 확대", "news_headline": "",
        "keywords": ["중국 HBM 경쟁", "장기 공급계약 확대", "AI 메모리 수요"],
        "lines": ["마이크론이 AI 데이터센터용 메모리 장기 공급계약을 확대했어요.",
                  "고객사 조달 안정성이 높아져 메모리 업종 분위기가 좋아졌어요.",
                  "마이크론은 HBM 등 고성능 메모리를 만드는 미국 반도체 기업이에요."],
        "source_ids": [1]}
NEWS = {"type": "news", "headline_keyword": "AI 광고 심의", "news_headline": "애플, 아이폰16 AI 기능 광고 심의 착수",
        "keywords": ["AI 광고 심의", "애플 인텔리전스", "공정위 조사"],
        "lines": ["공정위가 아이폰16 AI 기능 광고를 심의한다는 소식이 있어요.",
                  "애플 인텔리전스 기능이 광고와 다르다는 지적이 나온 데 따른 거예요.",
                  "애플은 아이폰과 맥, 서비스 사업을 하는 미국 기술 기업이에요."],
        "source_ids": [1]}


class SelectArticlesTest(unittest.TestCase):
    def test_keeps_only_recent_titles_naming_the_company(self):
        stock = {"name": "마이크론 테크놀로지", "symbol": "MU"}
        raw = [
            article("[미국 특징주] 마이크론, HBM 시장서 도전 직면", 3, 1),
            article("코스피·코스닥 동반 급등…외국인 저가 매수", 1, 2),          # no company in title
            article("Micron raises outlook", 5, 3, source="Reuters"),
            article("마이크론 전날 장 마감 전 기사", 20, 4),                    # before Tuesday's close
            article("마이크론, 장기 공급계약 확대", 2, 1),                       # duplicate URL
        ]
        with patch.object(job, "title_terms", return_value={"마이크론", "micron", "mu"}):
            picked = job.select_articles(stock, raw, now=RUN_AT)
        self.assertEqual([a["title"] for a in picked],
                         ["[미국 특징주] 마이크론, HBM 시장서 도전 직면", "Micron raises outlook"])

    def test_window_starts_at_the_previous_us_close(self):
        # Wednesday 10:30 NY -> Tuesday 16:00 NY.
        self.assertEqual(job.previous_close(RUN_AT).astimezone(UTC),
                         dt.datetime(2026, 11, 24, 21, 0, tzinfo=UTC))
        # Monday 10:30 NY -> Friday 16:00 NY (weekend news included).
        monday = dt.datetime(2026, 11, 30, 15, 30, tzinfo=UTC)
        self.assertEqual(job.previous_close(monday).astimezone(UTC),
                         dt.datetime(2026, 11, 27, 21, 0, tzinfo=UTC))
        # Friday after Thanksgiving -> Wednesday 16:00 NY.
        friday = dt.datetime(2026, 11, 27, 15, 30, tzinfo=UTC)
        self.assertEqual(job.previous_close(friday).astimezone(UTC),
                         dt.datetime(2026, 11, 25, 21, 0, tzinfo=UTC))

    def test_short_names_do_not_match_inside_other_words(self):
        self.assertFalse(job.title_names("릴리바이레드 '러브빔 치크밤', 올리브영 어워즈 1위", "릴리"))
        self.assertTrue(job.title_names("일라이 릴리, 비만약 판매 호조", "릴리"))
        self.assertTrue(job.title_names("메타가 AI 안경 신제품 공개", "메타"))
        self.assertFalse(job.title_names("메타버스 플랫폼 투자 확대", "메타"))
        self.assertTrue(job.title_names("Lilly raises guidance", "lilly"))


class ValidateTest(unittest.TestCase):
    def test_good_results_pass(self):
        self.assertEqual(job.validate(GOOD, 3), [])
        self.assertEqual(job.validate(NEWS, 3), [])

    def test_rule_violations_are_caught(self):
        cases = {
            "keywords": {**GOOD, "keywords": GOOD["keywords"][:2]},
            "headline_keyword": {**GOOD, "headline_keyword": "다른 키워드"},
            "lines": {**GOOD, "lines": GOOD["lines"][:2]},
            "number_in_lines": {**GOOD, "lines": ["주가가 6.4% 올랐어요.", *GOOD["lines"][1:]]},
            "source_ids": {**GOOD, "source_ids": [9]},
            "type": {**GOOD, "type": "maybe"},
            "result_keyword": {**GOOD, "keywords": ["앤트로픽 상승", *GOOD["keywords"][1:]],
                               "headline_keyword": "앤트로픽 상승"},
            "formal_ending": {**GOOD, "lines": [*GOOD["lines"][:2], "애플은 기술 기업입니다."]},
            "news_headline": {**NEWS, "news_headline": ""},
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


class MarketWrapOnlyTest(unittest.TestCase):
    def test_type_none_publishes_nothing(self):
        stock = {"rank": 3, "symbol": "ANT", "name": "앤트로픽"}
        raw = [article("[속보] 미국 뉴욕 증시 기술주 혼조…테슬라·앤트로픽 상승", 1, 7)]
        none = {**GOOD, "type": "none"}
        with patch.object(job, "title_terms", return_value={"앤트로픽"}):
            status, result, articles, tokens, diag = job.analyze_stock(
                stock, {}, fetch=lambda *a, **k: raw, reader=lambda *a, **k: [],
                groq=lambda message: (none, 900), now=RUN_AT)
        self.assertEqual((status, result, tokens), ("no_news", None, 900))
        self.assertEqual(diag["attempts"], 1)


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
            return "no_news", None, [], None, {"articles": 0}
        articles = [{"title": "마이크론, 장기 공급계약 확대", "url": "https://news.example/1",
                     "source": "제민일보", "_published": RUN_AT}]
        return "ok", GOOD, articles, 2586, {"articles": 1, "bodies": 1, "attempts": 1}

    def run_job(self, **kw):
        return job.run(RUN_AT, top20=lambda: self.stocks, analyze=self.analyze,
                       upload=lambda payload, key: self.uploads.append((key, payload)),
                       state_path=self.state_path, sleeper=self.sleeps.append, **kw)

    def test_publishes_each_stock_and_the_top20_list(self):
        with patch.object(job, "us_trading_day", return_value=dt.date(2026, 11, 25)):
            outcome = self.run_job()
        self.assertEqual(outcome["counts"], {"ok": 1, "no_news": 1})
        # MU, the list right after MU, then the final complete list.
        self.assertEqual([key for key, _ in self.uploads],
                         ["news/ai/us/MU.json", "news/ai/us/TOP20.json", "news/ai/us/TOP20.json"])
        self.assertFalse(self.uploads[1][1]["complete"])
        self.assertTrue(self.uploads[2][1]["complete"])
        mu = self.uploads[0][1]
        self.assertEqual(mu["headline_keyword"], "장기 공급계약 확대")
        self.assertEqual(mu["change_pct"], 6.26)                      # number from Kiwoom, not the model
        self.assertEqual(mu["sources"][0]["url"], "https://news.example/1")   # stored, not shown
        self.assertEqual(mu["type"], "reason")
        self.assertEqual(mu["diagnostics"], {"articles": 1, "bodies": 1, "attempts": 1})
        top = self.uploads[2][1]
        self.assertEqual([i["symbol"] for i in top["items"]], ["MU", "SNDK"])
        self.assertEqual(top["items"][1]["status"], "no_news")
        self.assertEqual(self.sleeps, [300])
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
