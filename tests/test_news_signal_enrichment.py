import unittest
from unittest.mock import patch
from backend.services.news_signal_enrichment import classify_article, cluster_events, clean_original_excerpt, translate_records


def article(title, url="https://source.example/a", description=""):
    return {"title": title, "description": description, "url": url, "published_at": "2026-10-26T01:00:00+00:00"}


class SignalTests(unittest.TestCase):
    def test_numeric_target_and_two_sources_one_event(self):
        items = [article("스티펠, 목표주가 115→130 달러, 매수의견 유지", url) for url in ("https://a", "https://b")]
        for row in items:
            row["event_classification"] = classify_article(row)
        groups = [g for g in cluster_events(items, "HNGE") if g["event_type"] == "ANALYST_TARGET_UP"]
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]["source_urls"]), 2)
        self.assertEqual(groups[0]["facts"][0]["new_value"], 130)
        self.assertIn("매수의견유지", items[0]["event_classification"]["keywords"])

    def test_plain_target_does_not_invent_direction(self):
        out = classify_article(article("목표주가 70 달러 제시"))
        self.assertEqual(out["keywords"], ["목표주가제시"])

    def test_rating_change_separate_from_target(self):
        out = classify_article(article("필립증권, 매수→중립. 목표주가 70 달러 유지."))
        self.assertIn("투자의견하향", out["keywords"])
        self.assertNotIn("목표주가하향", out["keywords"])

    def test_growth_is_not_earnings_surprise(self):
        out = classify_article(article("매출은 전년 대비 15% 증가했다."))
        self.assertIn("매출증가", out["keywords"])
        self.assertNotIn("예상치상회", out["keywords"])

    def test_earnings_and_guidance_do_not_cancel_each_other(self):
        out = classify_article(article("EPS가 시장 예상치를 상회했다. 가이던스 하향을 발표했다."))
        self.assertIn("예상치상회", out["keywords"])
        self.assertIn("가이던스하향", out["keywords"])

    def test_consideration_is_not_execution(self):
        out = classify_article(article("자사주 매입 계획을 승인했다. 특별배당을 검토한다."))
        self.assertIn("자사주매입계획", out["keywords"])
        self.assertIn("특별배당검토", out["keywords"])

    def test_mou_not_firm_contract(self):
        out = classify_article(article("공급 협약 MOU 체결"))
        self.assertEqual(out["keywords"], ["공급협약"])
        self.assertEqual(out["events"][0]["status"], "memorandum")

    def test_humanoid_joint_development(self):
        out = classify_article(article("삼성의 로봇 손가락", description="LG는 엔비디아와 휴머노이드를 공동 개발한다."))
        self.assertEqual(out["keywords"][0], "휴머노이드공동개발")

    def test_background_does_not_turn_into_stock_event(self):
        out = classify_article(article("한국공학대 고교생 진로 교육", description="엔비디아 직원들이 참여했다."))
        self.assertEqual(out["keywords"], [])
        self.assertIn("PROMOTIONAL_OR_BACKGROUND", out["failure_labels"])

    def test_capacity_not_turned_into_sold_out(self):
        out = classify_article(article("AWS 클라우드 용량 대부분 계약"))
        self.assertIn("용량계약", out["keywords"])
        self.assertNotIn("매진", str(out["keywords"]))

    def test_same_label_different_broker_not_merged(self):
        items = [article(f"{actor} 목표주가 115→130 달러", f"https://{i}") for i, actor in enumerate(("스티펠", "리링크"))]
        for row in items:
            row["event_classification"] = classify_article(row)
        groups = [g for g in cluster_events(items, "HNGE") if g["event_type"] == "ANALYST_TARGET_UP"]
        self.assertEqual(len(groups), 2)

    def test_page_furniture_not_article_body(self):
        self.assertEqual(clean_original_excerpt("Google 검색에서 기사를 더 자주 볼 수 있습니다. 무단 전재 금지."), "")

    def test_translation_without_key_preserves_original(self):
        rows = [{"title": "Nvidia launches new robot system", "description": "", "summary": ""}]
        with patch.dict("os.environ", {"GROQ_API_KEY": ""}):
            out = translate_records(rows)
        self.assertEqual(out[0]["title"], rows[0]["title"])
        self.assertEqual(out[0]["summary"], "")
        self.assertEqual(out[0]["translation_status"], "pending")



class SelectedIssueTests(unittest.TestCase):
    def test_selection_retention_and_reaction_anchor(self):
        from datetime import datetime, timedelta, timezone
        from backend.services.news_signal_enrichment import select_issue_articles
        now = datetime.now(timezone.utc)
        rows, briefs = [], []
        for title, url in [
            ("엔비디아, LG와 휴머노이드 공동 개발", "https://a"),
            ("한국공학대 고교생 진로 교육, 엔비디아 직원 참여", "https://b"),
            ("메타가 자본 조달을 발표했다. 엔비디아도 언급됐다.", "https://c"),
        ]:
            row = {"title": title, "url": url, "published_at": now.isoformat()}
            row["event_classification"] = classify_article(row)
            rows.append(row)
            briefs.append({"headline": title, "summary": "", "source_articles": [
                {"title": title, "url": url, "published_at": now.isoformat()}]})
        selected, rejected = select_issue_articles(rows, briefs, "엔비디아", now=now)
        self.assertEqual(len(selected), 1)
        self.assertEqual(len(rows), 3)
        self.assertEqual(len(rejected), 2)
        self.assertEqual(selected[0]["tags"][0], "휴머노이드공동개발")
        selected[0]["stock_reactions"] = [{"observed_at": now.isoformat()}]
        kept, _ = select_issue_articles([], [], "엔비디아", previous=selected,
                                        now=now + timedelta(hours=23))
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["issue_id"], selected[0]["issue_id"])
        self.assertEqual(kept[0]["stock_reactions"], selected[0]["stock_reactions"])
        expired, _ = select_issue_articles([], [], "엔비디아", previous=selected,
                                           now=now + timedelta(hours=25))
        self.assertEqual(expired, [])



class OwnershipRegressionTests(unittest.TestCase):
    def test_other_company_target_does_not_use_article_intro_as_evidence(self):
        from datetime import datetime, timezone
        from backend.services.news_signal_enrichment import select_issue_articles
        now = datetime.now(timezone.utc).isoformat()
        a = {"title": "테슬라, 합병 기대감 급등", "url": "https://a", "published_at": now}
        a["event_classification"] = classify_article(a,
            "메타, 알파벳, 엔비디아는 동반 조정을 겪었다. 테슬라 목표주가를 기존 370달러에서 450달러로 상향했다.")
        b = {"summary": "무관한 도입 문장입니다.", "original_summary": "무관한 도입 문장입니다.",
             "source_articles": [{"url": "https://a", "published_at": now}]}
        wrong, _ = select_issue_articles([a], [b], "엔비디아")
        self.assertEqual(wrong, [])
        correct, _ = select_issue_articles([a], [b], "테슬라")
        self.assertEqual(len(correct), 1)
        self.assertIn("테슬라 목표주가", correct[0]["summary"])
        self.assertNotIn("무관한", correct[0]["summary"])

    def test_oil_fall_and_stock_rise_are_different_subjects(self):
        result = classify_article({"title": "국제유가 하락도 증시 상승을 뒷받침했다."})
        self.assertIn("유가하락", result["keywords"])
        self.assertNotIn("유가상승", result["keywords"])

    def test_ipo_does_not_mean_product_launch(self):
        result = classify_article({"title": "AI 모델 클로드 개발사 앤트로픽이 기업공개 증권신고서를 제출했다."})
        self.assertNotIn("제품공개", result["keywords"])

    def test_automatic_translation_is_off_without_opt_in(self):
        with patch.dict("os.environ", {"NEWS_TRANSLATION_ENABLED": "0", "GROQ_API_KEY": "not-used"}):
            with patch("urllib.request.urlopen") as request:
                translate_records([{"title": "Nvidia launches new robot system", "summary": "", "description": ""}])
        request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
