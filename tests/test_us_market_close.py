"""Offline regression contract for production US-close 3-index + 3-original editorial."""
import datetime as dt
import json
import unittest
from unittest.mock import patch

from backend.services import us_market_close as close
from backend.services import us_market_close_runtime as source

DAY = dt.date(2026, 10, 19)
NOW = dt.datetime(2026, 10, 19, 22, tzinfo=dt.timezone.utc)
PROMPT = """제공된 기사를 근거로 미국장은 어땠어? 를 작성해\n제목은 핵심만 짧게, 내용은 쉽고 구체적으로, 해시태그는 최대 3개. 반말로 답변해."""

INDICES = [
    {"symbol":".DJI","name":"다우존스","session_date_et":"2026-10-19","close":51966.03,"change":-36.38,"change_pct":-0.07},
    {"symbol":".IXIC","name":"나스닥 종합","session_date_et":"2026-10-19","close":26430.89,"change":290.85,"change_pct":1.11},
    {"symbol":".INX","name":"S&P 500","session_date_et":"2026-10-19","close":7690.73,"change":31.29,"change_pct":0.41},
]
NEWS = [
    {"title":"뉴욕증시 마감 반도체 반등", "description":"뉴욕증시 나스닥 다우 S&P 500 19일 반도체 금리 상승. "*27,
     "url":"https://publisher1.example/article1","published_at":"2026-10-20T06:40:00+09:00","publisher":"publisher1.example"},
    {"title":"뉴욕증시 혼조 마감 유가", "description":"19일 뉴욕증시는 S&P 500 나스닥 다우를 포함해서 유가와 국채의 영향이 있었다. "*27,
     "url":"https://publisher2.example/article2","published_at":"2026-10-20T06:50:00+09:00","publisher":"publisher2.example"},
    {"title":"나스닥 상승 마감 AI", "description":"19일 뉴욕증시는 다우 나스닥 S&P 500 세 지수의 혼조로 마감했고 AI 기술주가 반등했다. "*27,
     "url":"https://publisher3.example/article3","published_at":"2026-10-20T06:55:00+09:00","publisher":"publisher3.example"},
]


class FakeResponse:
    def __init__(self,obj): self.obj=obj
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def read(self,n=None): return json.dumps(self.obj,ensure_ascii=False).encode()


class TestUSClose(unittest.TestCase):
    def test_approved_prompt_is_unchanged(self):
        self.assertEqual(close.US_CLOSE_PROMPT, PROMPT)
        self.assertEqual(close.MODEL, "openai/gpt-oss-120b")

    def test_input_contains_three_originals_and_three_factual_indices(self):
        data=json.loads(close._prompt(NEWS, DAY, indices=INDICES))
        self.assertEqual(data["session_date_et"],"2026-10-19")
        self.assertEqual(len(data["market_indices"]),3)
        self.assertEqual(data["market_indices"][1]["close"],26430.89)
        self.assertEqual(len(data["news"]),3)
        self.assertEqual(data["news"][0]["description"],NEWS[0]["description"])
        self.assertEqual([x["source_id"] for x in data["news"]],[1,2,3])

    def test_real_index_poll_rejects_stale_date_and_market_open(self):
        rows=[{"reutersCode":i["symbol"],"closePriceRaw":str(i["close"]),
               "compareToPreviousClosePriceRaw":str(i["change"]),
               "fluctuationsRatioRaw":str(i["change_pct"]),
               "marketStatus":"CLOSE","localTradedAt":"2026-10-19T16:44:25-04:00"}
               for i in INDICES]
        def fetch(_req,timeout):return FakeResponse({"datas":rows})
        self.assertEqual(len(source.verified_indices(DAY,opener=fetch)),3)
        with self.assertRaisesRegex(ValueError,"trade_date"):
            source.verified_indices(dt.date(2026,10,16),opener=fetch)
        rows[2]["marketStatus"]="OPEN"
        with self.assertRaisesRegex(ValueError,"not_closed"):
            source.verified_indices(DAY,opener=fetch)
        rows.pop()
        with self.assertRaisesRegex(ValueError,"incomplete"):
            source.verified_indices(DAY,opener=fetch)

    def test_mismatched_and_short_body_are_rejected(self):
        entry={"title":"뉴욕증시 마감 반도체 반등"}
        valid="19일 뉴욕증시는 나스닥과 다우, S&P 500의 혼조 마감 속 반도체가 반등했다. "*25
        self.assertTrue(source._verified_article(entry, valid, "article_or_main_paragraphs", DAY))
        self.assertFalse(source._verified_article(entry, "짧음", "article_or_main_paragraphs", DAY))
        self.assertFalse(source._verified_article(entry, valid, "meta_description", DAY))
        unrelated="19일 한국 국내 백화점 경영진 이야기야. " * 50
        self.assertFalse(source._verified_article(entry, unrelated,"article_or_main_paragraphs", DAY))

    def test_selection_uses_only_actual_full_originals(self):
        with patch.object(close,"verified_originals",return_value=NEWS) as fn:
            result=close.collect_articles(DAY,NOW)
        self.assertEqual(result,NEWS)
        fn.assert_called_once()

    def test_renders_title_indices_summary_tags_in_order(self):
        payload=json.dumps({
            "session_date_et":DAY.isoformat(),"market_indices":INDICES,
            "issues":[{"headline":"기술주 반등","summary":"미국 증시는 혼조였어.",
                       "tags":["#나스닥","#반도체"],"source_ids":[1,2]}]
        },ensure_ascii=False)
        rendered=close._display_brief_content(payload)
        self.assertIn("다우존스 51,966.03 (-0.07%)",rendered)
        self.assertIn("나스닥 종합 26,430.89 (+1.11%)",rendered)
        self.assertIn("S&P 500 7,690.73 (+0.41%)",rendered)
        self.assertTrue(rendered.index("기술주 반등") < rendered.index("다우존스")
                        < rendered.index("나스닥 종합") < rendered.index("S&P 500")
                        < rendered.index("미국 증시는 혼조였어.")
                        < rendered.index("#나스닥 #반도체"))
        self.assertNotIn("미국장 마감 ·",rendered)
        self.assertNotIn("source_ids",rendered)
        structured=close._structured_brief(payload)
        self.assertEqual(structured["session_date_et"],DAY.isoformat())
        self.assertEqual(len(structured["market_indices"]),3)
        self.assertEqual(structured["issues"][0]["headline"],"기술주 반등")
        self.assertNotIn("source_ids",structured["issues"][0])
        self.assertEqual(close._display_brief_content("legacy"),"legacy")

    def test_invalid_or_stale_index_presentation_is_not_used(self):
        payload={"session_date_et":DAY.isoformat(),"market_indices":INDICES[:2],
                 "issues":[{"headline":"기술주 반등","summary":"미국 증시는 혼조였어."}]}
        self.assertIsNone(close._structured_brief(json.dumps(payload,ensure_ascii=False)))
        payload["market_indices"]=INDICES
        payload["session_date_et"]="2026-10-16"
        self.assertIsNone(close._structured_brief(json.dumps(payload,ensure_ascii=False)))

    def test_no_ai_when_fewer_than_three_originals(self):
        class Blank:
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def cursor(self):return self
            def execute(self,*args):pass
            def fetchone(self):return None
        with patch.object(close,"verified_indices",return_value=INDICES),\
             patch.object(close,"collect_articles",return_value=NEWS[:2]),\
             patch.object(close,"_connection",return_value=Blank()):
            result=close.publish_once(now_utc=NOW)
        self.assertEqual(result["status"],"insufficient_verified_originals")

    def test_wrong_session_indices_block_before_article_collection(self):
        class Blank:
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def cursor(self):return self
            def execute(self,*args):pass
            def fetchone(self):return None
        with patch.object(close,"verified_indices",side_effect=ValueError("wrong date")) ,\
             patch.object(close,"collect_articles",side_effect=AssertionError("no article fetch")) ,\
             patch.object(close,"_connection",return_value=Blank()):
            with self.assertRaisesRegex(ValueError,"wrong date"):
                close.publish_once(now_utc=NOW)

    def test_duplicate_row_prevents_ai_spend(self):
        class Duplicate:
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def cursor(self):return self
            def execute(self,*args):pass
            def fetchone(self):return None
        with patch.object(close,"verified_indices",return_value=INDICES),\
             patch.object(close,"collect_articles",return_value=NEWS),\
             patch.object(close,"_connection",return_value=Duplicate()):
            result=close.publish_once(now_utc=NOW,generator=lambda *_:self.fail("duplicate AI"))
        self.assertEqual(result["status"],"already_attempted")

    def test_publishes_only_ai_editorial_and_index_facts(self):
        calls=[]
        returned=[None,(DAY,)]
        class Conn:
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def cursor(self):return self
            def execute(self,sql,params=None):calls.append((sql,params))
            def fetchone(self):return returned.pop(0) if returned else None
        output="**미국 기술주 반등**\\n\\n나스닥이 1.11% 상승했어. 시장은 혼조를 보였고 반도체주에 매수세가 유입됐어.\\n\\n#미국장"
        with patch.object(close,"verified_indices",return_value=INDICES),\
             patch.object(close,"collect_articles",return_value=NEWS),\
             patch.object(close,"_connection",return_value=Conn()):
            result=close.publish_once(now_utc=NOW,generator=lambda *_:output)
        self.assertEqual(result["status"],"published")
        stored=str(calls)
        self.assertIn("26430.89",stored)
        self.assertNotIn(NEWS[0]["description"],stored)
        self.assertIn("미국 기술주 반등",stored)

    def test_parses_real_plain_answer_without_truncation(self):
        output = ("**미국 증시, AI·반도체 주도 반등했지만 혼조 마감**  \\n\\n"
                  "19일 뉴욕증시는 다우는 0.07% 떨어지고 나스닥은 1.1% 올랐어.  \\n\\n"
                  "**핵심 포인트**  \\n"
                  "- AI·반도체 저가 매수세가 나스닥을 끌어올림  \\n"
                  "- 금리·유가 상승이 상승 폭을 제한  \\n\\n"
                  "#AI반등 #금리불안 #빅테크실적")
        issue = close._parse_editorial(output)
        self.assertEqual(issue["headline"], "미국 증시, AI·반도체 주도 반등했지만 혼조 마감")
        self.assertIn("**핵심 포인트**", issue["summary"])
        self.assertIn("- AI·반도체", issue["summary"])
        self.assertEqual(issue["tags"], ["#AI반등", "#금리불안", "#빅테크실적"])
        self.assertEqual(issue["source_ids"], [])
        packed = json.dumps({"session_date_et": DAY.isoformat(), "market_indices": INDICES,
                             "issues": [issue]}, ensure_ascii=False)
        self.assertEqual(close._structured_brief(packed)["issues"][0]["summary"], issue["summary"])
        self.assertIn("나스닥 종합", close._display_brief_content(packed))

    def test_rejects_missing_final_tags_and_long_body(self):
        with self.assertRaises(RuntimeError):
            close._parse_editorial("제목\\n\\n" + "내용 " * 30)
        with self.assertRaises(RuntimeError):
            close._parse_editorial("제목\\n\\n" + "긴 내용 " * 600 + "\\n\\n#미국장")

    def test_second_schedule_skips_existing_session_without_provider_calls(self):
        class Published:
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def cursor(self):return self
            def execute(self,*args):pass
            def fetchone(self):return ("published",)
        with patch.object(close,"_connection",return_value=Published()),\
             patch.object(close,"verified_indices",side_effect=AssertionError("no repeat quotes")),\
             patch.object(close,"collect_articles",side_effect=AssertionError("no repeat news")):
            result=close.publish_once(now_utc=NOW)
        self.assertEqual(result["status"],"already_attempted")

    def test_weekend_skips_calls(self):
        saturday=dt.datetime(2026,10,17,22,tzinfo=dt.timezone.utc)
        with patch.object(close,"verified_indices",side_effect=AssertionError("weekend")):
            self.assertEqual(close.publish_once(now_utc=saturday)["status"],"market_not_closed")

if __name__=="__main__":unittest.main()
