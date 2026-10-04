"""Explainable scoring for stock-news flow analysis.

This module does not collect news. It scores the normalized records produced by
news_feed so the central "왜?" flow can rank evidence without changing the
existing news panel. For the central keyword view, broad movement labels are
refined back to concrete phrases that are actually present in title+description.
"""

import datetime
import re
from functools import lru_cache
from collections import Counter
from zoneinfo import ZoneInfo

from .news_feed import STOCK_UNIVERSE
from email.utils import parsedate_to_datetime


STRONG_EVIDENCE_WORDS = (
    "공시", "실적", "매출", "영업이익", "순이익", "eps", "가이던스",
    "계약", "수주", "공급계약", "납품", "배당", "자사주", "목표주가",
)

# Central chat should show concrete evidence keywords, not replace them with a
# broader interpretation. The panel/news classifier itself remains untouched.
CONCRETE_SIGNAL_RULES = {
    "실적상회": [
        ("매출상회", ["매출 상회"]),
        ("어닝서프라이즈", ["어닝 서프라이즈"]),
        ("가이던스상향", ["가이던스 상향"]),
        ("전망상향", ["전망 상향"]),
        ("실적개선", ["실적 개선"]),
        ("호실적", ["호실적"]),
        ("실적상회", ["실적 상회"]),
    ],
    "메모리가격": [("D램가격", ["d램 가격", "dram 가격"]), ("낸드가격", ["낸드 가격"]), ("메모리가격", ["메모리 가격"])],
    "AI메모리": [("HBM수요", ["hbm 수요"]), ("HBM", ["hbm", "고대역폭 메모리"]), ("AI메모리", ["ai 메모리"])],
    "수주·계약": [("대형수주", ["대형 수주"]), ("BESS공급계약", ["bess 공급계약", "bess 공급 계약"]), ("방산계약", ["방산 계약"]), ("공급계약", ["공급계약", "공급 계약"]), ("납품계약", ["납품 계약"]), ("단일판매", ["단일판매"]), ("수주", ["수주"])],
    "주주환원": [("자사주소각", ["자사주 소각"]), ("자사주매입", ["자사주 매입"]), ("자사주취득", ["자사주 취득"]), ("배당확대", ["배당 확대"]), ("배당증가", ["배당 증가"])],
    "차익실현": [("차익실현", ["차익실현", "차익 실현"]), ("매물출회", ["매물 출회"])],
    "실적악화": [("어닝쇼크", ["어닝 쇼크"]), ("가이던스하향", ["가이던스 하향"]), ("전망하향", ["전망 하향"]), ("실적부진", ["실적 부진"]), ("실적악화", ["실적 악화"])],
    "금리부담": [("고금리", ["고금리"]), ("금리상승", ["금리 상승"]), ("금리부담", ["금리 부담"])],
    "유가부담": [("원유가격상승", ["원유 가격 상승"]), ("유가상승", ["유가 상승"]), ("유가부담", ["유가 부담"])],
    "환율부담": [("달러강세", ["달러 강세"]), ("원달러상승", ["원달러 상승"]), ("환율부담", ["환율 부담"])],
    "시장약세": [("코스피약세", ["코스피 약세"]), ("코스닥약세", ["코스닥 약세"]), ("증시약세", ["증시 약세"]), ("시장약세", ["시장 약세"])],
    "지정학적리스크": [("중동긴장", ["중동 긴장"]), ("전쟁", ["전쟁"]), ("분쟁", ["분쟁"])],
    "규제·소송": [("규제강화", ["규제 강화"]), ("제재", ["제재"]), ("소송", ["소송"]), ("리콜", ["리콜"])],
}

# First-pass shared material dictionary built from real KR/US news examples.
# Company/product/project proper nouns are intentionally excluded; this list is
# for reusable investment meaning. Tone is only assigned where the phrase itself
# has a clear direction. Neutral entries are kept as evidence, not forced bullish/bearish.
DETAIL_KEYWORD_RULES = [
    ("거래량호조", "positive", ["거래량 호조"]),
    ("목표가상향", "positive", ["목표가 상향", "목표주가 상향"]),
    ("목표가하향", "negative", ["목표가 하향", "목표주가 하향"]),
    ("비중확대", "positive", ["비중 확대"]),
    ("매수의견", "positive", ["매수 의견", "매수의견"]),
    ("의견상향", "positive", ["의견 상향", "투자의견 상향"]),
    ("의견하향", "negative", ["의견 하향", "투자의견 하향"]),
    ("밸류매력", "neutral", ["밸류 매력", "밸류에이션 매력"]),
    ("실적기대", "positive", ["실적 기대"]),
    ("실적전망", "neutral", ["실적 전망"]),
    ("매출발표", "neutral", ["매출 발표", "실적 발표", "분기 매출", "분기 실적"]),
    ("매출증가", "positive", ["매출 증가", "매출 상승"]),
    ("매출급증", "positive", ["매출 급증", "매출 폭증"]),
    ("수요급증", "positive", ["수요 급증", "수요 급등", "수요 폭증"]),
    ("설비투자재개", "positive", ["설비투자 재개", "설비 투자 재개"]),
    ("설비투자확대", "positive", ["설비투자 확대", "설비 투자 확대"]),
    ("생산능력확대", "positive", ["생산능력 확대", "생산 능력 확대", "생산설비 확대", "생산시설 확대"]),
    ("장기공급계약", "positive", ["장기 공급계약", "장기 공급 계약", "장기계약"]),
    ("금리상승부담", "negative", ["금리 상승 부담", "고금리 부담"]),
    ("글로벌변동성", "negative", ["글로벌 변동성", "글로벌 시장 변동성"]),
    ("반도체투자심리", "neutral", ["반도체 투자심리", "반도체 투자 심리"]),
    ("설비투자축소", "negative", ["설비투자 축소", "설비 투자 축소"]),
    ("공급부족", "positive", ["공급 부족"]),
    ("판매증가", "positive", ["판매 증가"]),
    ("판매감소", "negative", ["판매 감소"]),
    ("유럽판매감소", "negative", ["유럽 판매 감소"]),
    ("코스닥강세", "positive", ["코스닥 강세"]),
    ("반도체주약세", "negative", ["반도체주 약세", "반도체주가 약세"]),
    ("반도체강세", "positive", ["반도체 강세"]),
    ("AI주반등", "positive", ["ai주 반등", "ai 주 반등"]),
    ("AI속도조절", "neutral", ["ai 속도조절", "ai 속도 조절"]),
    ("점유율추격", "positive", ["점유율 추격", "점유율을 추격", "턱밑 추격"]),
    ("점유율격차", "neutral", ["점유율 격차", "격차 축소", "격차를 축소", "격차 좁혀", "격차를 좁혀"]),
    ("수요증가", "positive", ["수요 증가", "수요 확대"]),
    ("수요둔화", "negative", ["수요 둔화", "수요 감소"]),
    ("초기수요", "neutral", ["초기 수요"]),
    ("방공수요", "positive", ["방공 수요"]),
    ("강관수요", "positive", ["강관 수요"]),
    ("메모리투자", "positive", ["메모리 투자"]),
    ("매출인식", "positive", ["매출 인식"]),
    ("소각기대", "positive", ["소각 기대"]),
    ("지분율상승", "positive", ["지분율 상승"]),
    ("금융지원", "positive", ["금융 지원"]),
    ("정부지원", "positive", ["정부 지원"]),
    ("원전협력", "positive", ["원전 협력"]),
    ("AI공동개발", "positive", ["ai 공동개발", "ai 공동 개발"]),
    ("기술협력", "positive", ["기술 협력"]),
    ("전략적협력", "positive", ["전략적 협력"]),
    ("잠수함수출", "positive", ["잠수함 수출"]),
    ("해군수주", "positive", ["해군 수주"]),
    ("수주경쟁", "neutral", ["수주 경쟁"]),
    ("사업자선정", "positive", ["사업자 선정"]),
    ("CEO이탈", "negative", ["ceo 이탈", "ceo 사임"]),
    ("임시CEO", "neutral", ["임시 ceo"]),
    ("지분희석", "negative", ["지분 희석"]),
    ("주식발행", "neutral", ["주식 발행"]),
    ("ATM증자", "negative", ["atm 증자", "at-the-market"]),
    ("보고서제출지연", "negative", ["보고서 제출 지연", "보고서 지연"]),
    ("나스닥경고", "negative", ["나스닥 경고"]),
    ("상장규정", "neutral", ["상장 규정"]),
    ("국채금리상승", "negative", ["국채금리 상승", "국채 금리 상승"]),
    ("국채금리하락", "positive", ["국채금리 하락", "국채 금리 하락"]),
    ("국채금리", "neutral", ["국채금리", "국채 금리"]),
    ("물가둔화", "positive", ["물가 둔화", "물가가 둔화", "물가 둔화세", "인플레이션 둔화"]),
    ("물가상승", "negative", ["물가 상승", "물가가 상승", "물가 상승세", "인플레이션 상승"]),
    ("인플레이션", "neutral", ["인플레이션"]),
    ("디플레이션", "negative", ["디플레이션"]),
    ("금리인하 기대", "positive", ["금리 인하 기대", "금리인하 기대", "금리 인하 가능성", "금리인하 가능성"]),
    ("구인건수", "neutral", ["구인 건수", "구인건수"]),
    ("중동대화", "positive", ["중동 대화"]),
    ("긴장완화", "positive", ["긴장 완화"]),
    # Industry/technology/context tags: useful for later KR-US linkage, but neutral by themselves.
    ("AI반도체", "neutral", ["ai 반도체"]),
    ("AI인프라", "neutral", ["ai 인프라"]),
    ("AI생태계", "neutral", ["ai 생태계"]),
    ("AI속도조절론", "neutral", ["ai 속도조절론", "ai 속도 조절론", "ai 투자 속도조절", "ai 투자 속도 조절"]),
    ("ALD", "neutral", ["ald"]),
    ("LMR배터리", "neutral", ["lmr 배터리"]),
    ("전공정장비", "neutral", ["전공정 장비"]),
    ("BESS", "neutral", ["bess"]),
    ("LNG운반선", "neutral", ["lng 운반선", "lng선"]),
    ("고선가선박", "neutral", ["고선가 선박"]),
    ("맞춤형칩", "neutral", ["맞춤형 칩", "커스텀 칩", "custom chip"]),
    ("가스관건설", "neutral", ["가스관 건설"]),
    ("연료전지", "neutral", ["연료전지"]),
    ("우라늄채굴", "neutral", ["우라늄 채굴"]),
    ("기업보안", "neutral", ["기업 보안"]),
    ("클라우드", "neutral", ["클라우드"]),
    ("전투기사업", "neutral", ["전투기 사업"]),
    ("우주정거장", "neutral", ["우주정거장", "우주 정거장", "iss"]),
    ("우주인귀환", "neutral", ["우주인 귀환", "우주비행사 귀환", "우주 비행사 귀환"]),
    ("유인우주비행", "neutral", ["유인 우주비행", "유인 우주 비행"]),
    ("로켓발사", "neutral", ["로켓 발사"]),
    ("위성발사", "neutral", ["위성 발사"]),
    ("발사성공", "positive", ["발사 성공", "발사에 성공"]),
    ("발사실패", "negative", ["발사 실패", "발사에 실패"]),
    ("우주계약", "neutral", ["우주 계약", "우주사업 계약", "우주 사업 계약"]),
    ("피지컬AI", "neutral", ["피지컬 ai", "physical ai"]),
    ("자율주행AI", "neutral", ["자율주행 ai", "자율 주행 ai"]),
    ("자율주행데이터셋", "neutral", ["자율주행 데이터셋", "자율 주행 데이터셋", "주행 데이터셋", "주행 데이터 세트"]),
    ("AI에이전트", "neutral", ["ai 에이전트", "ai agent", "ai 비서"]),
    ("AI검색", "neutral", ["ai 검색", "ai 기반 검색"]),
    ("AI추론", "neutral", ["ai 추론", "추론 ai", "추론 모델"]),
    ("AI학습", "neutral", ["ai 학습", "ai 훈련", "학습 데이터"]),
    ("AI데이터센터", "neutral", ["ai 데이터센터", "ai 데이터 센터"]),
    ("AI로봇", "neutral", ["ai 로봇", "로봇 ai"]),
    ("휴머노이드", "neutral", ["휴머노이드"]),
    ("AI모델", "neutral", ["ai 모델", "인공지능 모델"]),
    ("주행데이터", "neutral", ["주행 데이터"]),
    ("자체알고리즘", "neutral", ["자체 알고리즘"]),
    ("AI판매상담", "neutral", ["ai 판매 상담", "ai 판매상담", "ai 판매 상담원", "ai 상담원"]),
    ("AI쇼핑", "neutral", ["ai 쇼핑", "ai 기반 쇼핑"]),
    ("쇼핑개편", "neutral", ["쇼핑 개편", "쇼핑 경험 개편", "쇼핑 검색 개편"]),
    ("상품정보개편", "neutral", ["상품정보 개편", "상품 정보 개편", "상품정보 바꾼", "상품 정보 바꾼"]),
    ("기술경쟁", "neutral", ["기술 경쟁", "기술력 경쟁"]),
    ("알고리즘경쟁", "neutral", ["알고리즘 경쟁"]),
    ("기술공개", "neutral", ["기술 공개", "기술을 공개", "공개한 기술"]),
    ("데이터공개", "neutral", ["데이터 공개", "데이터를 공개", "공개한 주행 데이터"]),
    ("서비스출시", "neutral", ["서비스 출시", "서비스를 출시", "서비스 공개"]),
    ("신규출시", "neutral", ["신규 출시", "새로 출시"]),
    ("신작출시", "neutral", ["신작 출시", "신작을 출시", "신작 공개"]),
    ("콘텐츠업데이트", "neutral", ["콘텐츠 업데이트", "업데이트를 선보", "업데이트 선보"]),
    ("신규캐릭터", "neutral", ["신규 캐릭터", "새 캐릭터"]),
    ("협업콘텐츠", "neutral", ["협업 콘텐츠", "협력 콘텐츠", "콜라보 콘텐츠"]),
    ("매출상위권", "positive", ["매출 순위 상위권", "매출 상위권"]),
    ("순위상승", "positive", ["순위 상승", "순위가 상승"]),
    ("순위하락", "negative", ["순위 하락", "순위가 하락"]),
    ("사전예약", "neutral", ["사전 예약", "사전예약"]),
    ("정식출시", "neutral", ["정식 출시", "정식으로 출시"]),
    ("신규도입", "neutral", ["신규 도입", "새로 도입", "도입한다", "도입했다"]),
    ("사업확대", "positive", ["사업 확대", "사업을 확대", "사업 확장"]),
    ("시장진출", "neutral", ["시장 진출", "시장에 진출"]),
    ("투자확대", "positive", ["투자 확대", "투자를 확대", "투자 늘려", "투자를 늘려"]),
    ("전망치상회", "positive", ["시장 전망치 상회", "시장 예상치 상회", "컨센서스 상회", "예상치 상회", "예상치를 웃돌"]),
    ("전망치하회", "negative", ["시장 전망치 하회", "시장 예상치 하회", "컨센서스 하회", "예상치 하회", "예상치를 밑돌"]),
    ("반도체호실적", "positive", ["반도체 호실적", "반도체 업계 호실적"]),
    ("성과급", "neutral", ["성과급", "성과급 지급"]),
    ("사상최대실적", "positive", ["사상 최대 실적", "사상최대 실적", "사상최대실적"]),
    ("HBM부족", "positive", ["hbm 부족", "hbm 공급 부족"]),
    ("데이터센터투자", "positive", ["데이터센터 투자", "데이터 센터 투자"]),
    ("성과급충당금", "neutral", ["성과급 충당금", "성과급충당금"]),
    ("영업이익예상", "neutral", ["영업이익 예상", "영업 이익 예상"]),
    ("수익성개선", "positive", ["수익성 개선", "수익성이 개선"]),
    ("주도권장악", "positive", ["주도권 장악", "주도권을 장악"]),
    ("반도체호황", "positive", ["반도체 호황", "반도체 업황 호황"]),
    ("보상규모확대", "neutral", ["보상 규모 확대", "보상규모 확대"]),
    ("상승사이클", "positive", ["상승 사이클", "상승사이클"]),
    ("DGX스파크출시", "neutral", ["dgx 스파크 출시", "dgx spark 출시", "dgx 스파크 이달 출시"]),
    ("메모리64GB탑재", "neutral", ["메모리 64gb 탑재", "64gb 메모리 탑재"]),
    ("개인AI컴퓨팅확대", "positive", ["개인 ai 컴퓨팅", "개인용 ai 컴퓨팅", "개인 ai 연산"]),
    ("슈퍼지능TF출범", "neutral", ["슈퍼지능 tf 출범", "슈퍼 지능 tf 출범", "si tf 출범"]),
    ("AI규제검토", "neutral", ["ai 규제 검토", "ai 규제 보고서", "ai 규제·안전 보고서", "ai 규제 안전 보고서"]),
    ("AI안전정책강화", "neutral", ["ai 안전 정책", "ai 안전 강화", "ai 안전 보고서"]),
    ("HBM공급부족", "positive", ["hbm 공급 부족", "hbm이 부족", "hbm 부족"]),
    ("데이터센터투자확대", "positive", ["데이터센터 투자 확대", "데이터 센터 투자 확대", "데이터센터 투자가 계속 늘", "데이터센터 투자 계속 늘"]),
    ("AI반도체수요증가", "positive", ["ai 반도체 수요 증가", "ai반도체 수요 증가", "ai 반도체 수요가 늘", "ai반도체 수요가 늘"]),
    ("AI투자급증", "positive", ["ai 투자 급증", "ai 투자가 급증", "ai 투자 폭발"]),
    ("AI인프라투자확대", "positive", ["ai 인프라 투자 확대", "ai 인프라 투자가 확대", "ai 인프라 투자 증가"]),
    ("GPU수요증가", "positive", ["gpu 수요 증가", "gpu 수요가 증가", "gpu 수요 확대", "gpu 수요가 늘"]),
    ("실적성장기대", "positive", ["실적 성장 기대", "실적 성장이 기대", "실적 성장 가능성"]),
    ("AI시장성장", "positive", ["ai 시장 성장", "ai 시장이 성장", "ai 시장 성장세"]),
    ("메모리물량선계약", "positive", ["메모리 물량 선계약", "메모리 물량을 선계약", "물량 75% 이미 계약", "물량의 75% 이미 계약"]),
    ("공급물량확보", "positive", ["공급 물량 확보", "공급물량 확보", "물량을 미리 확보"]),
    ("메모리공급경쟁", "neutral", ["메모리 공급 경쟁", "메모리 공급망 경쟁", "메모리 공급을 미리 묶"]),
    ("해외생산확대", "positive", ["해외 생산 확대", "해외생산 확대", "현지 생산 확대", "현지생산 확대"]),
    ("판매촉진강화", "positive", ["판매 촉진", "판매촉진", "판촉 강화", "파격 판촉", "프로모션 강화", "캐시백 판촉", "저금리 판촉"]),
    ("안정적실적흐름", "positive", ["안정적 실적 흐름", "안정적인 실적 흐름", "실적 흐름 안정"]),
    ("주주환원확대", "positive", ["주주환원 확대", "주주 환원 확대", "주주환원을 확대", "주주 환원을 확대"]),
    ("외국인매수세", "positive", ["외국인 매수세", "외인 매수세", "외국인 순매수", "외인 순매수"]),
    ("점유율확대", "positive", ["시장 점유율 확대", "점유율 확대", "점유율을 확대"]),
    ("가격인하압박", "negative", ["가격 인하 압박", "가격인하 압박", "가격 인하 압력"]),
    ("마케팅비용증가", "negative", ["마케팅 비용 증가", "마케팅비 증가", "판촉 비용 증가"]),

    ("연속영업손실", "negative", ["연속 영업손실", "연속 영업 손실", "영업손실 지속"]),
    ("적자지속", "negative", ["적자 지속", "적자가 지속"]),
    ("적자전환", "negative", ["적자 전환", "적자로 전환"]),
    ("흑자전환", "positive", ["흑자 전환", "흑자로 전환"]),
    ("영업이익감소", "negative", ["영업이익 감소", "영업 이익 감소", "영업이익이 감소"]),
    ("반도체업종비중", "neutral", ["반도체 업종 비중", "반도체업종 비중"]),
    ("시장모멘텀약화", "negative", ["시장 모멘텀 약화", "시장 모멘텀이 약화"]),
    ("매출사상최대", "positive", ["매출 사상 최대", "사상 최대 매출", "역대 최대 매출"]),
    ("분기매출증가", "positive", ["분기 매출 증가", "분기매출 증가"]),
    ("역대급실적", "positive", ["역대급 실적", "역대급실적"]),
    ("AI주도권", "neutral", ["ai 주도권", "ai주도권"]),
    ("메모리주도권", "neutral", ["메모리 주도권", "메모리주도권"]),
    ("설비투자", "neutral", ["설비투자", "설비 투자"]),
    ("투자계획", "neutral", ["투자 계획", "투자계획"]),
    ("전년비2배", "positive", ["전년 대비 2배", "전년대비 2배", "전년비 2배"]),
    ("전년비3배", "positive", ["전년 대비 3배", "전년대비 3배", "전년비 3배"]),
    ("차익실현", "negative", ["차익실현 매물", "차익 실현 매물"]),
    ("급등매물", "negative", ["급등 매물", "급등 후 매물"]),
    ("광통신", "neutral", ["광통신", "광 통신"]),
    ("광통신인프라", "neutral", ["광통신 인프라", "광 통신 인프라"]),
    ("후공정", "neutral", ["후공정", "후공정 장비", "반도체 후공정"]),
    ("업황개선", "positive", ["업황 개선", "업황이 개선", "업황 회복"]),
    ("업황기대", "positive", ["업황 기대", "업황 개선 기대", "업황 회복 기대"]),
    ("가격인상", "negative", ["가격 인상", "가격을 인상", "가격 인상폭"]),
    ("가격인하", "positive", ["가격 인하", "가격을 인하"]),
    ("가격동결", "neutral", ["가격 동결", "가격을 동결"]),
    ("신제품", "neutral", ["신제품", "새 제품", "새로운 제품"]),
    ("신제품출시", "positive", ["신제품 출시", "신제품을 출시", "새 제품 출시"]),
    ("데이터저장장치", "neutral", ["데이터 저장장치", "데이터 저장 장치"]),
    ("메모리부품", "neutral", ["메모리 부품"]),
    ("강한수요", "positive", ["강한 수요", "수요가 강", "견조한 수요"]),
    ("수요회복", "positive", ["수요 회복", "수요가 회복"]),
    ("선호종목", "positive", ["선호 종목", "선호종목", "선호 종목으로 선정"]),
    ("신중론", "negative", ["신중론", "투자 신중론", "ai 신중론"]),
    ("금리반등", "negative", ["금리 반등", "금리가 반등"]),
    ("국채반등", "neutral", ["국채 반등", "국채가 반등"]),
    ("유가반등", "negative", ["유가 반등", "유가가 반등"]),
    ("금리인상부담", "negative", ["금리 인상 부담", "금리인상 부담"]),
    ("위험자산선호", "positive", ["위험자산 선호", "위험 자산 선호"]),
    ("안전자산선호", "negative", ["안전자산 선호", "안전 자산 선호"]),
    ("시가총액증가", "positive", ["시가총액 증가", "시총 증가"]),
    ("시가총액증발", "negative", ["시가총액 증발", "시총 증발"]),
    ("공급확대", "positive", ["공급 확대", "공급을 확대"]),
    ("공급감소", "negative", ["공급 감소", "공급이 감소"]),
    ("재고증가", "negative", ["재고 증가", "재고가 증가"]),
    ("재고감소", "positive", ["재고 감소", "재고가 감소"]),
    ("생산확대", "positive", ["생산 확대", "생산을 확대"]),
    ("생산감소", "negative", ["생산 감소", "생산이 감소"]),
    ("점유율상승", "positive", ["점유율 상승", "점유율이 상승"]),
    ("점유율하락", "negative", ["점유율 하락", "점유율이 하락"]),
    ("사상최고가", "positive", ["사상 최고가", "주가 사상 최고", "역대 최고가"]),
    ("사상최저가", "negative", ["사상 최저가", "주가 사상 최저", "역대 최저가"]),
    ("신공장건설", "positive", ["신공장 건설", "신 공장 건설", "새 공장 건설"]),
    ("첨단산업", "neutral", ["첨단 산업", "첨단산업"]),
    ("매출부진", "negative", ["매출 부진", "매출이 부진"]),
    ("지표발표", "neutral", ["지표 발표", "경제지표 발표", "경제 지표 발표"]),
    ("고용지표", "neutral", ["고용 지표", "고용지표"]),
    ("연준연설", "neutral", ["연준 연설", "연준 의장 연설", "연준 위원 연설"]),
    ("무역흑자", "positive", ["무역 흑자", "무역수지 흑자"]),
    ("달러매도", "neutral", ["달러 매도", "달러를 매도"]),
    ("반도체수출", "positive", ["반도체 수출", "반도체 수출액"]),
    ("고용둔화", "neutral", ["고용 둔화", "고용이 둔화"]),
    ("금리동결기대", "neutral", ["금리 동결 기대", "동결 기대", "금리 동결 가능성", "금리동결 가능성"]),
    ("수익률하락", "positive", ["수익률 하락", "수익률이 하락"]),
    ("유럽판매반등", "positive", ["유럽 판매 반등", "유럽 판매가 반등"]),
    ("랠리부담", "negative", ["랠리 부담", "랠리에 부담"]),
    ("매출성장세", "positive", ["매출 성장세", "매출 성장세가"]),
    ("가격경쟁", "negative", ["가격 경쟁", "가격경쟁"]),
    ("광고추세", "neutral", ["광고 추세", "광고 시장 추세"]),
    ("제미니4", "neutral", ["제미니 4", "제미니4", "gemini 4"]),
    ("발사계획", "neutral", ["발사 계획", "발사를 계획"]),
    ("수주잔고", "positive", ["수주 잔고", "수주잔고"]),
    ("최대계약", "positive", ["최대 계약", "사상 최대 계약", "역대 최대 계약"]),
    ("스타십", "neutral", ["스타십", "starship"]),
    ("AI위성", "neutral", ["ai 위성", "ai위성", "인공지능 위성"]),
    ("비트코인상승", "positive", ["비트코인 상승", "비트코인이 상승"]),
    ("가상자산주", "neutral", ["가상자산주", "가상자산 관련주", "암호화폐 관련주"]),
    ("커버리지개시", "neutral", ["커버리지 개시", "분석을 개시", "분석 개시"]),
    ("테슬라인도량", "neutral", ["테슬라 인도량", "tesla deliveries"]),
    ("엔비디아자사주", "positive", ["엔비디아 자사주", "nvidia 자사주", "엔비디아 자사주 매입"]),
    ("마이크론실적", "neutral", ["마이크론 실적", "micron 실적"]),
    ("브로드컴대출", "neutral", ["브로드컴 대출", "broadcom 대출"]),
    # Curated reusable candidates: market/theme/material vocabulary.
    ("자금조달", "neutral", ["자금 조달", "자금조달"]),
    ("AI칩수요", "positive", ["ai 칩 수요", "ai칩 수요"]),
    ("지분확대", "positive", ["지분 확대", "지분을 확대"]),
    ("기술주랠리", "positive", ["기술주 랠리"]),
    ("기술주강세", "positive", ["기술주 강세"]),
    ("금리동결", "neutral", ["금리 동결"]),
    ("앱스토어매출", "neutral", ["앱스토어 매출", "앱 스토어 매출"]),
    ("유럽강세", "positive", ["유럽 강세", "유럽증시 강세", "유럽 증시 강세"]),
    ("실적호조전망", "positive", ["실적 호조 전망", "호실적 전망"]),
    ("AI지출", "neutral", ["ai 지출"]),
    ("장비점유율", "neutral", ["장비 점유율"]),
    ("증설수혜", "positive", ["증설 수혜"]),
    ("미국태양광", "neutral", ["미국 태양광"]),
    ("솔라허브", "neutral", ["솔라 허브", "solar hub"]),
    ("최저수입가격", "neutral", ["최저 수입 가격", "최저수입가격"]),
    ("광통신수요", "positive", ["광통신 수요", "광 통신 수요"]),
    ("코스피강세", "positive", ["코스피 강세"]),
    ("나스닥강세", "positive", ["나스닥 강세"]),
    ("나스닥약세", "negative", ["나스닥 약세"]),
    ("AI열풍", "positive", ["ai 열풍"]),
    ("기업가치", "neutral", ["기업 가치", "기업가치"]),
    ("사상최고", "positive", ["사상 최고", "역대 최고"]),
    ("HBM품귀", "positive", ["hbm 품귀"]),
    ("장기호황", "positive", ["장기 호황"]),
    ("슈퍼사이클", "positive", ["슈퍼사이클", "슈퍼 사이클"]),
    ("공급자우위", "positive", ["공급자 우위", "공급자우위"]),
    ("상승국면", "positive", ["상승 국면"]),
    ("하락국면", "negative", ["하락 국면"]),
    ("메모리부족", "positive", ["메모리 부족"]),
    ("반도체업황개선", "positive", ["반도체 업황 개선", "반도체 업황 회복"]),
    ("상승동력", "positive", ["상승 동력"]),
    ("인공지능투자", "positive", ["인공지능 투자"]),
    ("악재호재혼조", "neutral", ["악재 호재 혼조", "호재 악재 혼조", "호재와 악재", "악재와 호재"]),
    ("부품계약", "positive", ["부품 계약"]),
    ("대규모데이터", "neutral", ["대규모 데이터"]),
    ("양자암호", "neutral", ["양자 암호", "양자암호"]),
    ("양자랩", "neutral", ["양자 랩", "양자랩", "quantum lab"]),
    ("양자컴퓨팅", "neutral", ["양자 컴퓨팅", "양자컴퓨팅"]),
    ("황화리튬", "neutral", ["황화리튬", "황화 리튬"]),
    ("대미투자", "positive", ["대미 투자", "미국 투자", "미국 내 투자"]),
    ("미국진출", "positive", ["미국 진출", "미국 시장 진출"]),
    ("수주기회", "positive", ["수주 기회", "수주 기회 확대"]),
    ("한미투자", "positive", ["한미 투자", "한·미 투자"]),
    # Expanded reusable news-material vocabulary: earnings / business / industry / policy / momentum.
    ("반도체랠리", "positive", ["반도체 랠리", "반도체주 랠리", "반도체주 급등", "칩주 랠리"]),
    ("깜짝실적", "positive", ["깜짝 실적", "어닝 서프라이즈", "기대 이상의 실적", "예상을 뛰어넘는 실적"]),
    ("판도변화", "neutral", ["판도 변화", "판도변화", "지각 변동", "지각변동", "시장 재편", "경쟁 구도 변화", "경쟁구도 변화"]),
    ("사업인수", "neutral", ["사업 인수", "사업부 인수", "기업 인수", "인수합병", "m&a"]),
    ("규제강화", "negative", ["규제 강화", "규제 확대", "규제 압박", "제재 강화", "규제 도입"]),
    ("수출호조", "positive", ["수출 호조", "수출 증가", "수출 급증", "수출 확대", "역대 최대 수출", "사상 최대 수출"]),
    ("잠정실적발표", "neutral", ["잠정 실적 발표", "잠정실적 발표", "잠정 실적", "잠정실적", "잠정 영업이익", "잠정 매출"]),
    ("분기최대실적", "positive", ["분기 최대 실적", "분기 사상 최대 실적", "분기 역대 최대 실적", "분기 최대 매출", "분기 최대 영업이익"]),
    ("실적상향", "positive", ["실적 상향", "실적 전망 상향", "이익 전망 상향"]),
    ("실적하향", "negative", ["실적 하향", "실적 전망 하향", "이익 전망 하향"]),
    ("컨센서스상회", "positive", ["컨센서스 상회", "시장 예상치 상회", "시장 전망치 상회", "예상치 상회"]),
    ("컨센서스하회", "negative", ["컨센서스 하회", "시장 예상치 하회", "시장 전망치 하회", "예상치 하회"]),
    ("대규모수주", "positive", ["대규모 수주", "대형 수주", "대규모 계약"]),
    ("신규수주", "positive", ["신규 수주", "새 수주"]),
    ("독점공급", "positive", ["독점 공급", "단독 공급", "독점 납품"]),
    ("신규고객", "positive", ["신규 고객", "새 고객", "신규 고객사"]),
    ("신사업진출", "positive", ["신사업 진출", "신규 사업 진출", "새 사업 진출"]),
    ("사업매각", "neutral", ["사업 매각", "사업부 매각"]),
    ("지분인수", "neutral", ["지분 인수", "지분을 인수"]),
    ("합작법인", "neutral", ["합작 법인", "합작법인", "조인트벤처", "joint venture"]),
    ("업황반등", "positive", ["업황 반등", "업황이 반등"]),
    ("공급과잉", "negative", ["공급 과잉", "과잉 공급"]),
    ("가격상승", "positive", ["가격 상승", "가격이 상승"]),
    ("가격하락", "negative", ["가격 하락", "가격이 하락"]),
    ("재고조정", "neutral", ["재고 조정", "재고조정"]),
    ("산업재편", "neutral", ["산업 재편", "산업재편", "업계 재편"]),
    ("규제완화", "positive", ["규제 완화", "규제를 완화"]),
    ("정책수혜", "positive", ["정책 수혜", "정책 수혜주", "정책 혜택"]),
    ("보조금", "positive", ["보조금", "보조금 지원"]),
    ("세제혜택", "positive", ["세제 혜택", "세금 혜택", "세액 공제"]),
    ("관세인상", "negative", ["관세 인상", "관세를 인상"]),
    ("관세완화", "positive", ["관세 완화", "관세를 완화", "관세 인하"]),
    ("수출규제", "negative", ["수출 규제", "수출 통제"]),
    ("규제리스크", "negative", ["규제 리스크", "규제 위험"]),
    ("기관매수", "positive", ["기관 매수", "기관 순매수", "기관 매수세"]),
    ("신고가", "positive", ["신고가", "52주 신고가", "연중 신고가"]),
    ("급등", "positive", ["급등", "주가 급등"]),
    ("랠리", "positive", ["랠리", "주가 랠리"]),
    ("주도주", "positive", ["주도주", "시장 주도주", "증시 주도주"]),
    # AI risk/development and political-policy context. Person-name context stays neutral;
    # concrete tariff/regulation/policy effects continue to be captured by directional rules above.
    ("AI위협", "negative", ["ai 위협", "ai 리스크", "ai 위험", "ai 대체 위협", "ai가 위협"]),
    ("AI점검", "neutral", ["ai 점검", "ai 안전 점검", "ai 시스템 점검", "ai 위험 점검"]),
    ("AI개발", "neutral", ["ai 개발", "ai 기술 개발", "ai 모델 개발", "자체 ai 개발"]),
    ("AI수혜", "positive", ["ai 수혜", "ai 수혜주", "ai 혜택"]),
    ("AI투자축소", "negative", ["ai 투자 축소", "ai 투자 감소", "ai 투자 감축"]),
    ("AI규제강화", "negative", ["ai 규제 강화", "ai 규제 확대", "ai 규제 압박"]),
    ("AI규제완화", "positive", ["ai 규제 완화", "ai 규제 완화 기대"]),
    ("트럼프관세", "neutral", ["트럼프 관세", "트럼프발 관세", "트럼프의 관세"]),
    ("트럼프규제", "neutral", ["트럼프 규제", "트럼프발 규제", "트럼프의 규제"]),
    ("트럼프정책", "neutral", ["트럼프 정책", "트럼프발 정책", "트럼프의 정책"]),
    ("트럼프발언", "neutral", ["트럼프 발언", "트럼프의 발언", "트럼프가 발언", "트럼프 언급"]),

]


def _parse_date(value):
    """Parse RSS/ISO timestamps consistently for scoring and storyboard output."""
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        date = parsedate_to_datetime(raw)
    except Exception:
        try:
            date = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except Exception:
            return None
    if date.tzinfo is None:
        date = date.replace(tzinfo=datetime.timezone.utc)
    return date.astimezone(datetime.timezone.utc)


def _freshness_score(item):
    date = _parse_date(item.get("pub_date") or item.get("published_at"))
    if not date:
        return 0
    hours = max(0.0, (datetime.datetime.now(datetime.timezone.utc) - date).total_seconds() / 3600)
    if hours <= 12: return 15
    if hours <= 24: return 12
    if hours <= 72: return 8
    if hours <= 120: return 4
    return 2


def _stock_aliases(stock_name):
    stock = str(stock_name or "").strip().lower()
    aliases = [stock]
    for stocks in STOCK_UNIVERSE.values():
        for name, values in stocks.items():
            if str(name).strip().lower() == stock:
                aliases.extend(str(value).strip().lower() for value in values)
                break
    return list(dict.fromkeys(alias for alias in aliases if alias))


def _direct_score(item, stock_name):
    title = str(item.get("title") or "").lower()
    return 35 if any(alias in title for alias in _stock_aliases(stock_name)) else 0


def _context_relevance_score(item, stock_name):
    title = str(item.get("title") or "").lower()
    description = str(item.get("description") or "").lower()
    aliases = _stock_aliases(stock_name)
    if not aliases:
        return 0

    title_hits = sum(title.count(alias) for alias in aliases)
    body_hits = sum(description.count(alias) for alias in aliases)

    # 제목 직접 언급은 중앙 핵심기사의 강한 신호로 사용한다.
    # 본문에만 등장한 기사는 점수를 낮게 주되 더보기에서는 보존한다.
    if title_hits:
        return 25 + min(10, max(0, title_hits - 1) * 5)
    if body_hits:
        return min(12, body_hits * 4)
    return 0


def _material_score(item):
    text = f"{item.get('title') or ''} {item.get('description') or ''}".lower()
    matches = sum(word.lower() in text for word in STRONG_EVIDENCE_WORDS)
    return min(20, matches * 5)


def _concrete_signal_label(item, label):
    text = f"{item.get('title') or ''} {item.get('description') or ''}".lower()
    for concrete_label, phrases in CONCRETE_SIGNAL_RULES.get(str(label or ""), []):
        if any(phrase.lower() in text for phrase in phrases):
            return concrete_label
    return str(label or "").strip()


_DETAIL_PARTICLES = ("으로", "에서", "이", "가", "은", "는", "을", "를", "의", "에", "로", "와", "과")
_DETAIL_SHORT_MODIFIERS = frozenset(("매우", "크게", "계속", "꾸준히", "빠르게", "급격히", "대폭"))


def _detail_token_variants(token):
    """Return the token itself plus the same token with one Korean particle removed."""
    clean = str(token or "").strip().lower()
    if not clean:
        return ()
    variants = [clean]
    for particle in _DETAIL_PARTICLES:
        if clean.endswith(particle) and len(clean) > len(particle):
            variants.append(clean[:-len(particle)])
            break
    return tuple(variants)


@lru_cache(maxsize=1024)
def _detail_phrase_parts(phrase):
    """Prepare static phrase tokens once; article matching itself uses no regex."""
    return tuple(part for part in str(phrase or "").strip().lower().split() if part)


def _detail_phrase_matches(text, phrase, words=None, word_variants=None):
    """Match phrase tokens in order, reusing article tokenization across the shared dictionary."""
    haystack = str(text or "").lower()
    needle = str(phrase or "").strip().lower()
    if not needle:
        return False
    if needle in haystack:
        return True

    expected = _detail_phrase_parts(needle)
    if len(expected) < 2:
        return False

    if words is None:
        words = tuple(part for part in haystack.split() if part)
    if word_variants is None:
        word_variants = tuple(_detail_token_variants(part) for part in words)
    expected_variants = tuple(_detail_token_variants(part) for part in expected)
    for start in range(len(words)):
        word_index = start
        matched = True
        for variants in expected_variants:
            while word_index < len(words) and words[word_index] in _DETAIL_SHORT_MODIFIERS:
                word_index += 1
            if word_index >= len(words):
                matched = False
                break
            actual_variants = word_variants[word_index]
            if not any(left == right for left in actual_variants for right in variants):
                matched = False
                break
            word_index += 1
        if matched:
            return True
    return False


def _refine_movement_signals(item):
    text = f"{item.get('title') or ''} {item.get('description') or ''}".lower()
    refined, seen = [], set()
    for raw in item.get("movement_signals") or []:
        signal = dict(raw)
        label = _concrete_signal_label(item, signal.get("label"))
        if label and label not in seen:
            signal["label"] = label
            refined.append(signal)
            seen.add(label)

    # Title + description are the article's evidence boundary. If a concrete
    # signal is explicitly present there, keep it even when feed-level
    # movement_signals did not carry that label through.
    for group_rules in CONCRETE_SIGNAL_RULES.values():
        for label, phrases in group_rules:
            if label not in seen and any(phrase.lower() in text for phrase in phrases):
                tone = "negative" if label in {"금리부담", "유가부담", "환율부담", "시장약세", "반도체주약세", "실적악화", "전망하향"} else "positive"
                refined.append({"label": label, "tone": tone})
                seen.add(label)

    # Tokenize the article once. DETAIL_KEYWORD_RULES can keep growing without
    # paying the same split/particle-normalization cost again for every phrase.
    detail_words = tuple(part for part in text.split() if part)
    detail_word_variants = tuple(_detail_token_variants(part) for part in detail_words)
    for label, tone, phrases in DETAIL_KEYWORD_RULES:
        if label not in seen and any(
            _detail_phrase_matches(text, phrase, detail_words, detail_word_variants)
            for phrase in phrases
        ):
            refined.append({"label": label, "tone": tone})
            seen.add(label)
    return refined


def _signal_score(item):
    return min(20, len(item.get("movement_signals") or []) * 5)


def _classification_score(item):
    issue_count = len(item.get("issues") or [])
    theme_count = len(item.get("themes") or [])
    stock_count = len(item.get("related_stocks") or [])
    return min(10, issue_count * 2 + theme_count * 2 + min(stock_count, 2))


STORYBOARD_EXCLUDED_KEYWORDS = {"적당한"}

# Representative storyboard keywords should describe what happened, not merely
# what the article is about. These fragments reward action/change/result labels
# while leaving the full keyword dictionary intact for classification.
STORYBOARD_EVENT_FRAGMENTS = (
    "상승", "하락", "증가", "감소", "확대", "축소", "급증", "급감", "급등", "급락",
    "반등", "강세", "약세", "돌파", "최고", "최저", "호실적", "부진", "서프라이즈",
    "상회", "하회", "개선", "악화", "전환", "종료", "재개", "중단", "부족", "품귀",
    "투자", "조달", "증설", "생산", "판매", "수요", "공급", "매입", "매도", "순매수",
    "수주", "계약", "선정", "출시", "진출", "인수", "합병", "협력", "지원", "발행",
    "소각", "경고", "소송", "발표", "귀환", "발사", "수출", "건설", "인하", "인상",
)


def _storyboard_representative(item):
    """Pick one concrete event/action from title + description evidence."""
    title = str(item.get("title") or "").lower()
    description = str(item.get("description") or "").lower()
    combined = f"{title} {description}".strip()
    candidates = []

    # The article-level extractor already reads title + description together.
    # Use those grounded results first instead of letting broad movement/topic
    # signals decide the storyboard before the article evidence is considered.
    detail_by_label = {
        str(detail.get("label") or "").strip(): detail
        for detail in item.get("article_keyword_details") or []
        if str(detail.get("label") or "").strip()
    }
    for index, raw_label in enumerate(item.get("article_keywords") or []):
        label = str(raw_label or "").strip()
        if not label or label in STORYBOARD_EXCLUDED_KEYWORDS:
            continue
        normalized = label.lower().replace(" ", "")
        detail = detail_by_label.get(label, {})
        source = str(detail.get("source") or "")
        evidence = str(detail.get("evidence") or "").lower()
        is_event = any(fragment.lower() in normalized for fragment in STORYBOARD_EVENT_FRAGMENTS)
        # Entity/title-copy candidates must never beat a real event. The
        # storyboard is intentionally event-only at this stage.
        if not is_event:
            continue
        score = 120
        if source.startswith("title"):
            score += 35
        elif source.startswith("description"):
            score += 25
        if evidence and evidence in combined:
            score += 20
        score += min(len(normalized), 12)
        candidates.append((score, -index, label, str(detail.get("tone") or "neutral").strip()))

    if candidates:
        _, _, label, tone = max(candidates)
        return label, tone if tone in ("positive", "negative", "neutral") else "neutral"

    # Fallback only: preserve the existing movement-signal path for articles
    # where the article-level extractor did not produce enough evidence.
    fallback = []
    for index, signal in enumerate(item.get("movement_signals") or []):
        label = str(signal.get("label") or "").strip()
        if not label or label in STORYBOARD_EXCLUDED_KEYWORDS:
            continue
        normalized = label.lower().replace(" ", "")
        score = 0
        if any(fragment.lower() in normalized for fragment in STORYBOARD_EVENT_FRAGMENTS):
            score += 100
        label_text = label.lower()
        if label_text in title or label_text.replace(" ", "") in title.replace(" ", ""):
            score += 20
        elif label_text in description or label_text.replace(" ", "") in description.replace(" ", ""):
            score += 10
        score += min(len(normalized), 12)
        fallback.append((score, -index, label, str(signal.get("tone") or "neutral").strip()))

    if fallback:
        _, _, label, tone = max(fallback)
        return label, tone if tone in ("positive", "negative", "neutral") else "neutral"
    return None, "neutral"


def attach_storyboard_representatives(items, display_timezone="Asia/Seoul"):
    """Attach one representative event keyword to each selected article."""
    try:
        tz = ZoneInfo(str(display_timezone or "Asia/Seoul"))
    except Exception:
        tz = datetime.timezone.utc

    attached = []
    for raw in items or []:
        item = dict(raw)
        representative, tone = _storyboard_representative(item)
        dt = _parse_date(item.get("pub_date") or item.get("published_at"))
        item["storyboard_keyword"] = representative or ""
        item["storyboard_keyword_tone"] = tone if tone in ("positive", "negative", "neutral") else "neutral"
        item["storyboard_time"] = dt.astimezone(tz).strftime("%H:%M") if dt else ""
        attached.append(item)
    return attached


def select_today_storyboard_news(items, limit=3, display_timezone="Asia/Seoul"):
    """Select today's keyword-bearing article bundles without changing news scoring."""
    try:
        tz = ZoneInfo(str(display_timezone or "Asia/Seoul"))
    except Exception:
        tz = datetime.timezone.utc

    today = datetime.datetime.now(tz).date()
    candidates = []
    for item in items or []:
        dt = _parse_date(item.get("pub_date") or item.get("published_at"))
        if not dt or dt.astimezone(tz).date() != today:
            continue
        if not item.get("storyboard_keyword"):
            continue
        candidates.append((dt, item))

    candidates.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in candidates[:max(1, int(limit))]]


def build_keyword_storyboard(items, merge_minutes=30, display_timezone="Asia/Seoul"):
    """Build a compact time-ordered keyword flow without changing article display.

    News timestamps are stored in UTC. Convert them only for presentation so the
    storyboard uses the market's local clock instead of silently showing UTC.
    """
    try:
        tz = ZoneInfo(str(display_timezone or "Asia/Seoul"))
    except Exception:
        tz = datetime.timezone.utc

    events = []
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=24)
    for item in items or []:
        dt = _parse_date(item.get("pub_date") or item.get("published_at"))
        if not dt or dt < cutoff:
            continue
        keywords = []
        keyword_tones = {}
        representative, representative_tone = _storyboard_representative(item)
        if representative:
            keywords.append(representative)
            keyword_tones[representative] = representative_tone
        if not dt or not keywords:
            continue
        local_dt = dt.astimezone(tz)
        events.append({
            "time": local_dt.strftime("%H:%M"),
            "timestamp": local_dt.isoformat(),
            "keywords": keywords,
            "keyword_tones": keyword_tones,
        })

    events.sort(key=lambda event: event["timestamp"])
    merged = []
    for event in events:
        if not merged:
            merged.append(event)
            continue

        previous = merged[-1]
        prev_dt = _parse_date(previous["timestamp"])
        cur_dt = _parse_date(event["timestamp"])
        def related(a, b):
            a = str(a or "").replace("#", "").replace(" ", "")
            b = str(b or "").replace("#", "").replace(" ", "")
            if not a or not b:
                return False
            if a == b:
                return True
            # 같은 핵심어를 포함한 세부 표현도 같은 흐름으로 묶는다.
            if len(a) >= 2 and len(b) >= 2 and (a in b or b in a):
                return True
            return False

        related_topic = any(
            related(left, right)
            for left in previous["keywords"]
            for right in event["keywords"]
        )
        within_window = prev_dt and cur_dt and (cur_dt - prev_dt).total_seconds() <= merge_minutes * 60

        if within_window and related_topic:
            for keyword in event["keywords"]:
                if keyword not in previous["keywords"]:
                    previous["keywords"].append(keyword)
                    previous.setdefault("keyword_tones", {})[keyword] = event.get("keyword_tones", {}).get(keyword, "neutral")
            previous["timestamp"] = event["timestamp"]
            previous["time"] = event["time"]
        else:
            merged.append(event)

    compact = []
    seen_keywords = set()
    for event in reversed(merged):
        fresh = [k for k in event["keywords"] if k not in seen_keywords]
        if not fresh:
            continue
        event["keywords"] = fresh
        event["keyword_tones"] = {k: event.get("keyword_tones", {}).get(k, "neutral") for k in fresh}
        compact.append(event)
        seen_keywords.update(fresh)
        if len(compact) >= 3:
            break
    compact.reverse()
    return compact


def score_stock_news(items, stock_name):
    scored = []
    for raw in items or []:
        item = dict(raw)
        item["movement_signals"] = _refine_movement_signals(item)
        breakdown = {
            "direct_stock": _direct_score(item, stock_name), "context_relevance": _context_relevance_score(item, stock_name),
            "material_strength": _material_score(item),
            "movement_signal": _signal_score(item), "freshness": _freshness_score(item),
            "classification_context": _classification_score(item),
        }
        relevance = max(0, min(int(item.get("relevance_score") or 0), 10))
        breakdown["investment_relevance"] = relevance
        item["flow_score_breakdown"] = breakdown
        item["flow_score"] = sum(breakdown.values())
        scored.append(item)
    scored.sort(key=lambda item: (item.get("flow_score", 0), item.get("pub_date", "")), reverse=True)

    # Stock-news analysis/display uses Korean-language articles only.
    # Collection and the existing relevance/material scoring stay unchanged.
    def has_korean_text(item):
        text = f"{item.get('title') or ''} {item.get('description') or ''}"
        return any("\uac00" <= char <= "\ud7a3" for char in text)

    return [item for item in scored if has_korean_text(item)]


def summarize_stock_flow(items):
    signal_counts, signal_scores, signal_tones = Counter(), Counter(), {}
    issue_counts, theme_counts = Counter(), Counter()
    positive_count = negative_count = 0
    positive_score = negative_score = 0.0
    for item in items or []:
        article_score = max(1, int(item.get("flow_score") or 0))
        signals = item.get("movement_signals") or []
        per_signal_score = article_score / max(1, len(signals))
        for signal in signals:
            label = str(signal.get("label") or "").strip()
            tone = str(signal.get("tone") or "").strip()
            if label:
                signal_counts[label] += 1
                signal_scores[label] += per_signal_score
                if tone in ("positive", "negative", "neutral"): signal_tones[label] = tone
            if tone == "positive": positive_count += 1; positive_score += per_signal_score
            elif tone == "negative": negative_count += 1; negative_score += per_signal_score
        issue_counts.update(item.get("issues") or [])
        theme_counts.update(item.get("themes") or [])
    directional_total = positive_score + negative_score
    balance = (positive_score - negative_score) / directional_total if directional_total else 0.0
    direction = "neutral" if directional_total == 0 else "positive" if balance >= 0.18 else "negative" if balance <= -0.18 else "mixed"
    ranked_signals = sorted(signal_counts, key=lambda label: (signal_scores[label], signal_counts[label], label), reverse=True)
    top_signals = [{"label": label, "tone": signal_tones.get(label, "neutral"), "count": signal_counts[label], "evidence_score": round(signal_scores[label], 1)} for label in ranked_signals[:5]]
    return {
        "article_count": len(items or []), "direction": direction, "direction_balance": round(balance, 3),
        "positive_signal_count": positive_count, "negative_signal_count": negative_count,
        "positive_evidence_score": round(positive_score, 1), "negative_evidence_score": round(negative_score, 1),
        "top_signals": top_signals,
        "top_positive_signals": [s for s in top_signals if s["tone"] == "positive"][:3],
        "top_negative_signals": [s for s in top_signals if s["tone"] == "negative"][:3],
        "top_issues": [{"label": label, "count": count} for label, count in issue_counts.most_common(5)],
        "top_themes": [{"label": label, "count": count} for label, count in theme_counts.most_common(5)],
    }

def _related_stock_entities(item):
    text = f"{item.get('title') or ''} {item.get('description') or ''}".lower()
    entities = []
    for market_stocks in STOCK_UNIVERSE.values():
        for canonical_name, aliases in market_stocks.items():
            names = [canonical_name, *(aliases or [])]
            if any(str(name or "").strip().lower() in text for name in names if str(name or "").strip()):
                entities.append(canonical_name)
    return list(dict.fromkeys(entities))


def build_connected_keyword_test(items, stock_name, max_keywords=3):
    """Test-only: build article-summary keyword candidates, then keep three."""
    import re

    # Reusable expressions are helpers only. They must not decide the whole
    # article by themselves; title evidence stays the strongest signal.
    summary_rules = [
        ("목표가상향", ["목표가 상향", "목표주가 상향"]),
        ("목표가하향", ["목표가 하향", "목표주가 하향"]),
        ("매수의견", ["매수 의견", "매수의견", "'매수' 상향", '"매수" 상향']),
        ("투자의견상향", ["투자의견 상향", "의견 상향"]),
        ("투자의견하향", ["투자의견 하향", "의견 하향"]),
        ("가격상승", ["가격 상승", "가격 급등", "가격이 상승", "가격이 급등"]),
        ("가격하락", ["가격 하락", "가격 급락", "가격이 하락", "가격이 급락"]),
        ("물량증가", ["물량 증가", "출하량 증가", "판매량 증가"]),
        ("물량감소", ["물량 감소", "출하량 감소", "판매량 감소"]),
        ("수요증가", ["수요 증가", "수요 확대", "수요 급증"]),
        ("수요둔화", ["수요 둔화", "수요 감소"]),
        ("성장가속", ["성장 가속", "성장세 가속"]),
        ("투자확대", ["투자 확대", "투자를 확대"]),
        ("현금유입", ["현금 유입"]),
        ("안전성확인", ["안전성 확인", "안전성을 확인"]),
        ("실적프리뷰", ["실적 프리뷰"]),
        ("투자심리악화", ["투자심리 악화", "투자 심리 악화", "투자심리가 부정적"]),
        ("내부자매수", ["내부자 매수", "내부 임원", "임원 매입", "이사 매입"]),
        ("매입종료", ["매입 종료", "매입 마무리", "매입을 마무리", "매입 완료", "매입을 완료"]),
        ("사업매각", ["사업 매각"]),
        ("사업분사", ["사업 분사", "분사"]),
        ("발사계약", ["발사 계약"]),
        ("3상데이터", ["3상 데이터", "3상 임상", "3상 임상시험"]),
    ]

    # Broad words are useful classification context but weak final summary
    # keywords when a more concrete article phrase exists.
    broad_labels = {"AI", "반도체", "메모리", "시장", "기업", "주식", "증시"}
    # Generic event labels remain available as fallback evidence, but should
    # lose to keywords that explain scale, direction, industry state or result.
    weak_final_labels = {
        "매출발표", "자금조달", "투자계획", "설비투자", "주식발행",
        "실적전망", "지표발표", "신규도입", "시장진출",
        "공급과잉", "가격경쟁", "투자확대", "현금유입",
        "낸드가격", "메모리가격", "D램가격",
    }
    # These labels are useful internally but are too generic for the three
    # user-facing material slots. Never surface them as final keywords.
    blocked_final_labels = {
        "매출발표", "자금조달",
        "낸드가격", "메모리가격", "D램가격",
    }
    aliases = _stock_aliases(stock_name)
    results = []

    for item in items or []:
        title = str(item.get("title") or "").strip()
        description = str(item.get("description") or "").strip()
        if not title:
            continue

        title_lower = title.lower()
        desc_lower = description.lower()
        full_lower = f"{title_lower} {desc_lower}".strip()
        candidates = []
        seen = set()
        stock_entities = _related_stock_entities(item)

        def add(label, source, evidence, priority):
            clean = re.sub(r"\s+", "", str(label or "").strip())
            if not clean or clean in seen or clean.lower() in aliases:
                return
            seen.add(clean)
            candidates.append({
                "label": clean,
                "source": source,
                "evidence": str(evidence or "").strip(),
                "priority": priority,
            })

        # Sharp compound material keywords. Prefer "why it matters" over a
        # generic event word when the article itself supplies the evidence.
        sharp_texts = (("title", title, 103), ("description", description, 63))
        for source_name, source_text, priority in sharp_texts:
            compact_source = re.sub(r"\\s+", "", source_text.lower())

            # Scale + financing: 대규모 자금조달 / 10조 자금조달.
            if "자금조달" in compact_source or "자금조달" in compact_source.replace("·", ""):
                if re.search(r"(대규모|대형|역대최대|사상최대)", compact_source):
                    add("대규모자금조달", f"{source_name}-sharp", "대규모 자금조달", priority)
                financing_amount = re.search(r"(\\d+(?:[.,]\\d+)?(?:조|억)원?).{0,10}자금조달|자금조달.{0,10}(\\d+(?:[.,]\\d+)?(?:조|억)원?)", compact_source)
                if financing_amount:
                    amount = next((g for g in financing_amount.groups() if g), "")
                    add(f"{amount}자금조달", f"{source_name}-sharp", financing_amount.group(0), priority + 1)

            # Capacity expansion is more explanatory than generic 투자/증설.
            if re.search(r"(생산능력|생산캐파|생산capacity|캐파).{0,12}(확대|증가|확충|증설)", compact_source):
                add("생산능력확대", f"{source_name}-sharp", "생산능력 확대", priority)

            # Industry/product + cycle state: e.g. 낸드시장호황, 메모리시장호황.
            industry_aliases = (
                ("낸드", ("낸드", "nand")),
                ("메모리", ("메모리",)),
                ("D램", ("d램", "dram")),
                ("HBM", ("hbm",)),
                ("반도체", ("반도체",)),
            )
            # Expansion/capacity competition is a sharper causal material than
            # standalone 증설/투자. Keep the industry name when evidence supports it.
            for industry, aliases_for_industry in industry_aliases:
                if not any(alias in compact_source for alias in aliases_for_industry):
                    continue
                if re.search(r"(증설|생산능력확대|생산능력증가|캐파확대).{0,18}(경쟁|잇따라|확대)|(?:경쟁).{0,18}(증설|생산능력확대)", compact_source):
                    add(f"{industry}증설경쟁", f"{source_name}-sharp", f"{industry} 증설 경쟁", priority + 1)

            state_rules = (
                ("시장호황", ("시장호황", "시장 호황", "호황", "최고 상승폭", "상승폭")),
                ("업황개선", ("업황개선", "업황 개선", "업황회복", "업황 회복")),
                ("수요급증", ("수요급증", "수요 급증", "수요폭증", "수요 폭증")),
                ("공급과잉우려", ("공급과잉우려", "공급 과잉 우려", "공급과잉 우려", "공급 과잉을 우려")),
                ("공급과잉", ("공급과잉", "공급 과잉")),
            )
            for industry, aliases_for_industry in industry_aliases:
                if not any(alias in compact_source for alias in aliases_for_industry):
                    continue
                for state_label, state_phrases in state_rules:
                    if any(re.sub(r"\\s+", "", phrase.lower()) in compact_source for phrase in state_phrases):
                        add(f"{industry}{state_label}", f"{source_name}-sharp", f"{industry}{state_label}", priority)
                        break

        # Dynamic earnings facts: keep the financial item attached to its
        # actual amount so high-value facts do not collapse into generic "매출발표".
        amount_pattern = r"\\d+(?:[.,]\\d+)?\\s*(?:조(?:\\s*\\d+(?:[.,]\\d+)?\\s*억)?|억|만)?\\s*원"
        earnings_texts = (("title", title, 98), ("description", description, 58))
        for source_name, source_text, priority in earnings_texts:
            for metric in ("영업이익", "매출", "순이익"):
                metric_pattern = re.escape(metric) + r"\\s*(?:은|는|이|가|을|를|도|약|총)?\\s*(" + amount_pattern + r")"
                for match in re.finditer(metric_pattern, source_text):
                    amount = re.sub(r"\\s+", "", match.group(1))
                    tail = source_text[match.end():match.end() + 18]
                    event = ""
                    if re.search(r"(돌파|넘어|넘었|상회)", tail):
                        event = "돌파"
                    elif re.search(r"(최대|최고|신기록)", source_text[max(0, match.start() - 18):match.end() + 18]):
                        event = "최대"
                    add(f"{metric}{amount}{event}", f"{source_name}-earnings", match.group(0), priority)

        # Dynamic investor-flow facts from news evidence. This is a news
        # material keyword only; it does not replace the supply/trading dataset.
        flow_amount_pattern = r"\\d+(?:[.,]\\d+)?\\s*(?:조(?:\\s*\\d+(?:[.,]\\d+)?\\s*억)?|억|만)?\\s*원?"
        flow_texts = (("title", title, 99), ("description", description, 59))
        for source_name, source_text, priority in flow_texts:
            compact_text = re.sub(r"\\s+", "", source_text)
            for actor in ("외국인", "기관", "개인"):
                # e.g. 외국인 한달새 17조 팔아 / 기관 2조 순매수
                flow_pattern = (
                    re.escape(actor)
                    + r".{0,18}?(" + flow_amount_pattern + r").{0,12}?"
                    + r"(순매수|순매도|매수|매도|사들여|사들였|팔아|팔았)"
                )
                for match in re.finditer(flow_pattern, source_text):
                    amount = re.sub(r"\\s+", "", match.group(1))
                    action_raw = match.group(2)
                    action = {
                        "사들여": "매수", "사들였": "매수",
                        "팔아": "매도", "팔았": "매도",
                    }.get(action_raw, action_raw)
                    add(f"{actor}{amount}{action}", f"{source_name}-flow", match.group(0), priority)

                # Preserve the article's stated record horizon instead of
                # exaggerating "연중 최저" into "역대 최저".
                stake_patterns = [
                    (r"외국인지분율.{0,16}?(연중|역대|사상)\\s*(최저|최고)", lambda m: f"외국인지분율{m.group(1)}{m.group(2)}"),
                    (r"외국인지분율.{0,16}?(\\d+)\\s*년(?:래|만의)?\\s*(최저|최고)", lambda m: f"외국인지분율{m.group(1)}년{m.group(2)}"),
                    (r"외국인.{0,8}?지분(?:율)?.{0,16}?(연중|역대|사상)\\s*(최저|최고)", lambda m: f"외국인지분율{m.group(1)}{m.group(2)}"),
                    (r"외국인.{0,8}?지분(?:율)?.{0,16}?(\\d+)\\s*년(?:래|만의)?\\s*(최저|최고)", lambda m: f"외국인지분율{m.group(1)}년{m.group(2)}"),
                ]
                if actor == "외국인":
                    for pattern, label_builder in stake_patterns:
                        for match in re.finditer(pattern, compact_text):
                            add(label_builder(match), f"{source_name}-stake", match.group(0), priority + 1)

                # e.g. 외국인 10일 연속 매도
                streak_pattern = re.escape(actor) + r".{0,12}?(\\d+)\\s*일\\s*연속\\s*(순매수|순매도|매수|매도)"
                for match in re.finditer(streak_pattern, source_text):
                    add(f"{actor}{match.group(1)}일연속{match.group(2)}", f"{source_name}-flow-streak", match.group(0), priority)

        # 1) Title-first: reusable meaning phrases found in the headline.
        for label, phrases in summary_rules:
            matched = next((p for p in phrases if p.lower() in title_lower), "")
            if matched:
                add(label, "title", matched, 100)

        # Existing signal dictionaries remain useful as supporting vocabulary,
        # but title matches outrank description-only matches.
        # score_stock_news() already refined the shared DETAIL_KEYWORD_RULES
        # into movement_signals. Reuse that result here so newly added shared
        # keywords reach article_keywords without running the expensive matcher
        # a second time for every article.
        for signal in item.get("movement_signals") or []:
            label = str(signal.get("label") or "").strip()
            if not label or label in broad_labels:
                continue
            compact = label.replace(" ", "")
            if compact.lower() in title_lower.replace(" ", ""):
                add(label, "title-signal", label, 90)
            elif compact.lower() in desc_lower.replace(" ", ""):
                add(label, "description-signal", label, 45)
            else:
                add(label, "shared-signal", label, 50)

        # 2) Description supplements the headline; it never replaces the
        # headline as the article's center.
        for label, phrases in summary_rules:
            if label in seen:
                continue
            matched = next((p for p in phrases if p.lower() in desc_lower), "")
            if matched:
                add(label, "description", matched, 55)

        # Do not promote quoted headline copy or standalone product/entity names
        # into storyboard keywords. They describe what the article is about,
        # while the storyboard should explain what happened.

        for phase in re.findall(r"(?<!\d)([123])상(?:\s*임상(?:시험)?)?", title):
            add(f"{phase}상데이터", "title-entity", f"{phase}상", 80)

        # Test-only: keep concrete Korean event phrases from the headline.
        # This supplements reusable rules without adding stock-specific terms.
        korean_event_patterns = [
            r"([가-힣A-Za-z0-9]+(?:팹|공장))\s*(착공|준공|증설)",
            r"([가-힣A-Za-z0-9]+(?:메모리|제품|기술))\s*(공개|출시|개발)",
            r"([A-Za-z0-9가-힣]+)\s*(양산|생산)",
        ]
        for pattern in korean_event_patterns:
            for match in re.finditer(pattern, title):
                subject, event = match.groups()
                add(f"{subject}{event}", "title-event", match.group(0), 84)

        # Keep headline scale only when it belongs to a concrete corporate event.
        event_scale_words = ("매입", "인수", "계약", "수주", "투자", "매각", "증자")
        if any(word in title for word in event_scale_words):
            for amount in re.findall(r"(?<![\d.])(?:\d+(?:[.,]\d+)*)\s*(?:조원|억원|만원|달러)", title):
                add(amount, "title-scale", amount, 76)

        # A final keyword should explain article content, not merely repeat the
        # searched stock or its own price move.
        candidates = [
            row for row in candidates
            if row["label"] not in broad_labels
            and row["label"] not in blocked_final_labels
            and row["label"] not in {"주가상승", "주가하락", "급등", "급락"}
        ]
        # If the article has sharper evidence, generic labels such as
        # 매출발표/자금조달 must not consume one of the final three slots.
        has_sharp_candidate = any(
            row["source"].endswith(("-sharp", "-earnings", "-flow", "-stake", "-flow-streak"))
            or row["priority"] >= 98
            for row in candidates
        )
        if has_sharp_candidate:
            candidates = [row for row in candidates if row["label"] not in weak_final_labels]

        candidates.sort(
            key=lambda row: (
                row["label"] in weak_final_labels,
                -row["priority"],
                row["source"],
                row["label"],
            )
        )

        selected = []
        for row in candidates:
            label = row["label"]
            overlap_index = next(
                (
                    index for index, old in enumerate(selected)
                    if label in old["label"] or old["label"] in label
                ),
                None,
            )
            if overlap_index is not None:
                old = selected[overlap_index]
                if old["label"] in label and len(label) > len(old["label"]):
                    selected[overlap_index] = row
                continue
            selected.append(row)
            if len(selected) >= max_keywords:
                break

        # One grounded event is enough for the storyboard. Requiring all
        # max_keywords candidates here discarded good single-event results and
        # forced the display back to the old movement-signal path.
        enough = len(selected) > 0
        results.append({
            "title": title,
            "description": description,
            "candidate_keywords": [row["label"] for row in candidates],
            "keywords": [row["label"] for row in selected] if enough else [],
            "keyword_details": selected if enough else [],
            "stock_entities": stock_entities,
            "enough_evidence": enough,
            "status": "PASS" if enough else "SKIP",
        })

    return {"stock": stock_name, "articles": results}
