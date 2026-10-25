"""Central body contract, independent of sidebar headline formatting."""
import copy
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from backend.services import news_result
from backend.services.news_freshness import clean_us_snapshot


class RenderBodyTests(unittest.TestCase):
    def render(self, title, summary):
        snapshot = {
            '_news_status': 'ok', '_title_only_revision': 3,
            '_code_fact_extraction_version': 3,
            '_code_issue_briefs': [{
                'headline': title, 'summary': summary, 'tags': ['original'],
                'source_articles': [{
                    'url': 'https://example.org/article', 'source': 'test',
                    'published_at': datetime.now(timezone.utc).isoformat(),
                    'title': 'Publisher title must never be copied',
                }],
            }],
            'issue_briefs': [],
        }
        before = copy.deepcopy(snapshot)
        sidebar_before = clean_us_snapshot(snapshot)
        with patch.object(news_result, 'resolve_us_news_identity',
                          return_value={'snapshot_names': ['test']}), patch.object(
                news_result, '_read_worker_news_snapshot', return_value=snapshot):
            result = news_result.get_shared_stock_news_result('test', market='미국')
        self.assertEqual(snapshot, before)
        self.assertEqual(clean_us_snapshot(snapshot), sidebar_before)
        return result['issue_briefs']

    def test_nvidia_event_extracted_from_prose(self):
        body = ('엔비디아 최고경영자 젠슨 황이 엔스케일에 데이터센터 건설을 촉구했다. '
                '엔스케일의 데이터센터 구축 지연에 신속한 대응을 주문했다.')
        result = self.render('AI 반도체 이슈', body)[0]
        self.assertEqual(result['headline'], '엔비디아 젠슨 황, 엔스케일에 데이터센터 건설 촉구')
        self.assertEqual(result['summary'], body)

    def test_live_nvidia_long_request(self):
        # Captured from the authenticated production API on 2026-10-25.
        body = ('엔비디아 최고경영자 젠슨 황이 인공지능 클라우드 기업 엔스케일에 '
                '데이터센터 구축 과정에서 발생한 문제를 해결하고 시설 가동에 속도를 낼 것을 촉구했다. '
                '인공지능 연산 수요가 빠르게 증가하는 가운데, 실제 시설을 완공하고 전력과 장비를 '
                '확보하는 과정이 업계의 주요 과제로 떠오르고 있다. '
                '블블룸버그는 젠슨 황 CEO가 엔스케일의 데이터센터 구축 지연과 관련해 '
                '신속한 대응을 주문했다고 보도했다.')
        result = self.render('기사 주요 내용', body)[0]
        self.assertEqual(result['headline'],
                         '엔비디아 젠슨 황, 엔스케일에 데이터센터 문제 해결·가동 가속 촉구')
        self.assertEqual(result['summary'], body)

    def test_live_nvidia_limited_prose_does_not_invent_power_shortage(self):
        body = '글로벌 인공지능(AI) 반도체 시장을 독점하고 있는 엔비디아의 앞길에 강력한 경고등이 켜졌다.'
        self.assertEqual(self.render('AI 반도체 이슈', body), [])

    def test_live_micron_is_preserved(self):
        body = ('인공지능 산업의 성장으로 메모리 반도체의 중요성이 커지면서 미국 반도체 기업 '
                '마이크론 테크놀로지의 주가 향방에 관심이 집중되고 있다. 고성능 인공지능 시스템에 '
                '필요한 메모리 수요가 확대되고 공급 부족이 장기화할 수 있다는 전망은 주가에 '
                '긍정적인 요인으로 꼽힌다. 그러나 최근 주가가 큰 폭으로 조정을 받은 가운데 '
                '인공지능 투자 속도와 메모리 가격의 지속 가능성을 둘러싼 우려도 이어지고 있어 '
                '향후 실적이 시장의 기대를 충족할지가 중요한 변수로 떠올랐다.')
        title = '마이크론, AI 메모리 공급 부족에 기대'
        result = self.render(title, body)[0]
        self.assertEqual(result['headline'], title)
        self.assertEqual(result['summary'], body)

    def test_live_spacex_is_preserved(self):
        body = ('미래에셋증권의 실적 반등에 대한 기대감이 커지고 있다. 올해 3분기에는 스페이스X '
                '투자자산의 평가손실로 실적 악화가 예상되지만 최근 스페이스X의 호실적 발표와 '
                '테슬라와의 합병 논의가 새로운 변수로 떠올랐다. 이에 따라 4분기 미래에셋증권의 '
                '실적 회복 여부에도 관심이 쏠리고 있다.')
        title = '스페이스X, 합병으로 반등 이뤄내나'
        result = self.render(title, body)[0]
        self.assertEqual(result['headline'], title)
        self.assertEqual(result['summary'], body)

    def test_short_third_sentence_is_not_replaced(self):
        # Synthetic preservation case; this is not a captured live snapshot.
        body = '스페이스X가 위성을 발사했다. 위성은 궤도에 진입했다. 임무는 완료됐다.'
        result = self.render('스페이스X, 위성 발사', body + ' 네 번째 문장이다.')[0]
        self.assertEqual(result['summary'], body)
        self.assertEqual(result['headline'], '스페이스X, 위성 발사')

    def test_micron_specific_title_and_tags_preserved(self):
        body = '마이크론은 새 제도를 발표했다. 성과급은 내년부터 지급된다. 지급액은 실적에 연동된다.'
        result = self.render('마이크론, 이익연동 성과급 도입', body)[0]
        self.assertEqual(result['headline'], '마이크론, 이익연동 성과급 도입')
        self.assertEqual(result['summary'], body)
        self.assertEqual(result['tags'], ['original'])

    def test_gallery_removed_in_actual_body_path(self):
        body = '테슬라가 출시를 취소했다. 예약금은 반환된다. 계획도 철회됐다.'
        text = '이미지 확대보기 차량이 전시돼 있다. 사진=로이터 ' + body + ' 네 번째 문장이다.'
        self.assertEqual(self.render('출시 취소', text)[0]['summary'], body)

    def test_link_index_hidden(self):
        self.assertEqual(self.render('기사 주요 내용', '다른 기사 ... 링크 ... 목록 ...'), [])

    def test_quoted_sentence_counts_as_one(self):
        body = '“첫 번째 문장이다.” 두 번째 문장이다. 세 번째 문장이다.'
        self.assertEqual(self.render('구체적인 제목', body + ' 네 번째 문장이다.')[0]['summary'], body)

    def test_decimal_is_not_a_sentence_boundary(self):
        body = '매출이 3.5% 늘었다. 이익도 2.1% 증가했다. 전망은 유지됐다.'
        self.assertEqual(self.render('구체적인 제목', body + ' 네 번째 문장이다.')[0]['summary'], body)

    def test_negation_and_forecast_not_changed_to_confirmed_event(self):
        for body in ('젠슨 황이 엔스케일에 데이터센터 건설을 촉구하지 않았다.',
                     '젠슨 황이 엔스케일에 데이터센터 건설을 촉구할 전망이다.'):
            self.assertEqual(self.render('기사 주요 내용', body), [])

    def test_missing_original_text_hidden(self):
        self.assertEqual(self.render('확인된 제목', ''), [])

    def test_korean_display_does_not_use_us_sentence_filter(self):
        result = {'issue_briefs': [{'headline': '국내 제목', 'summary': '짧은 국내 본문'}]}
        self.assertEqual(news_result._sanitize_news_display_briefs(result, market='국내'), result)


if __name__ == '__main__':
    unittest.main()
