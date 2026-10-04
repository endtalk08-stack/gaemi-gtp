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
    # Robotics / physical-AI materials. Keep R&D itself neutral; only directional
    # phrases such as slowdown or competition carry negative tone.
    ("로봇기술연구", "neutral", ["로봇 기술 연구", "로봇기술 연구"]),
    ("로봇기술연구개발", "neutral", ["로봇 기술 연구개발", "로봇기술 연구개발", "로봇 기술 r&d", "로봇기술 r&d"]),
    ("AI기술개발", "neutral", ["ai 기술 개발", "ai기술 개발"]),
    ("AI연구개발", "neutral", ["ai 연구개발", "ai 연구 개발", "ai r&d"]),
    ("피지컬AI개발", "neutral", ["피지컬 ai 개발", "피지컬ai 개발", "physical ai 개발"]),
    ("휴머노이드개발", "neutral", ["휴머노이드 개발", "휴머노이드 로봇 개발"]),
    ("로봇상용화", "positive", ["로봇 상용화", "로봇 상용화 추진", "로봇 사업화"]),
    ("로봇실증", "neutral", ["로봇 실증", "ai로봇 실증", "ai 로봇 실증"]),
    ("로봇현장투입", "positive", ["로봇 현장 투입", "로봇을 현장에 투입", "산업현장 투입"]),
    ("로봇데이터축적", "positive", ["로봇 데이터 축적", "현장 데이터 축적", "실전 데이터 축적"]),
    ("로봇사업확대", "positive", ["로봇 사업 확대", "로보틱스 사업 확대"]),
    ("핵심부품국산화", "positive", ["핵심부품 국산화", "핵심 부품 국산화", "로봇부품 국산화", "로봇 부품 국산화"]),
    ("성장세둔화", "negative", ["성장세 둔화", "성장 둔화", "성장률 둔화"]),
    ("중국산경쟁", "negative", ["중국산 경쟁", "중국산과 경쟁", "중국 업체와 경쟁", "중국 기업과 경쟁", "중국 로봇과 경쟁"]),
    ("가격경쟁심화", "negative", ["가격 경쟁 심화", "가격경쟁 심화"]),
    ("글로벌경쟁심화", "negative", ["글로벌 경쟁 심화", "글로벌 기술 경쟁 심화", "기업 간 경쟁 고조"]),
    ("수출부진", "negative", ["수출 부진", "수출 감소", "수출액 감소"]),
    ("연구개발부족", "negative", ["연구개발 부족", "r&d 부족", "연구개발 실적이 전무", "r&d 실적이 전무"]),
    ("로봇투자확대", "positive", ["로봇 투자 확대", "로보틱스 투자 확대", "로봇 분야 투자 확대"]),
    ("로봇생산확대", "positive", ["로봇 생산 확대", "로봇 생산량 확대", "로봇 생산능력 확대", "로봇 생산 능력 확대"]),
    ("로봇양산", "positive", ["로봇 양산", "휴머노이드 양산", "양산 체제"]),
    ("로봇수주확대", "positive", ["로봇 수주 확대", "로봇 수주 증가", "로봇 주문 증가"]),
    ("로봇수요증가", "positive", ["로봇 수요 증가", "로봇 수요 확대", "휴머노이드 수요 증가"]),
    ("로봇시장성장", "positive", ["로봇 시장 성장", "로봇시장 성장", "로봇 시장 확대", "로봇시장 확대"]),
    ("로봇시장진출", "neutral", ["로봇 시장 진출", "로봇시장 진출", "로보틱스 시장 진출"]),
    ("로봇사업진출", "neutral", ["로봇 사업 진출", "로보틱스 사업 진출"]),
    ("로봇공급계약", "positive", ["로봇 공급계약", "로봇 공급 계약", "휴머노이드 공급계약", "휴머노이드 공급 계약"]),
    ("로봇협력확대", "positive", ["로봇 협력 확대", "로보틱스 협력 확대", "휴머노이드 협력 확대"]),
    ("로봇자동화확대", "positive", ["로봇 자동화 확대", "로봇자동화 확대", "자동화 로봇 확대"]),
    ("스마트팩토리확대", "positive", ["스마트팩토리 확대", "스마트 팩토리 확대", "스마트공장 확대", "스마트 공장 확대"]),
    ("피지컬AI투자", "positive", ["피지컬 ai 투자", "피지컬ai 투자", "physical ai 투자"]),
    ("피지컬AI협력", "positive", ["피지컬 ai 협력", "피지컬ai 협력", "physical ai 협력"]),
    ("휴머노이드투자", "positive", ["휴머노이드 투자", "휴머노이드 로봇 투자"]),
    ("휴머노이드상용화", "positive", ["휴머노이드 상용화", "휴머노이드 로봇 상용화"]),
    ("자율주행로봇", "neutral", ["자율주행 로봇", "자율 주행 로봇", "amr 로봇", "자율이동로봇"]),
    ("협동로봇", "neutral", ["협동로봇", "협동 로봇", "cobot"]),
    ("산업용로봇", "neutral", ["산업용 로봇", "산업로봇"]),
    ("로봇부품공급망", "neutral", ["로봇 부품 공급망", "로봇부품 공급망", "로봇 핵심부품 공급망"]),
    ("중국산점유율확대", "negative", ["중국산 점유율 확대", "중국 로봇 점유율 확대", "중국 업체 점유율 확대"]),
    ("가격하락압력", "negative", ["가격 하락 압력", "가격하락 압력", "가격 인하 압력"]),
    ("수익성악화", "negative", ["수익성 악화", "수익성 하락", "수익성 저하"]),
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
    ("1분기불확실성", "negative", ["1분기 불확실성", "1분기의 불확실성"]),
    ("2분기불확실성", "negative", ["2분기 불확실성", "2분기의 불확실성"]),
    ("3분기불확실성", "negative", ["3분기 불확실성", "3분기의 불확실성"]),
    ("4분기불확실성", "negative", ["4분기 불확실성", "4분기의 불확실성"]),
    ("내년1분기불확실성", "negative", ["내년 1분기 불확실성", "내년 1분기의 불확실성"]),
    ("불확실성완화", "positive", ["불확실성 완화", "불확실성이 완화", "불확실성 감소"]),
    ("불확실성해소", "positive", ["불확실성 해소", "불확실성이 해소", "불확실성을 해소"]),
    ("배당매력", "positive", ["배당 매력", "배당 매력이", "배당 매력도", "높은 배당 매력", "고배당 매력"]),
    ("고배당선호", "positive", ["고배당 선호", "고배당주 선호", "배당주 선호"]),
    ("우선주매수", "positive", ["우선주 매수", "우선주를 매수", "우선주 매입", "우선주를 담", "우선주 담"]),
    ("배당수요", "positive", ["배당 수요", "배당 투자 수요", "배당 목적 수요"]),
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
    ("투자계획", "neutral", ["투자 계획", "투자계획"]),
    ("전년비2배", "positive", ["전년 대비 2배", "전년대비 2배", "전년비 2배"]),
    ("전년비3배", "positive", ["전년 대비 3배", "전년대비 3배", "전년비 3배"]),
    ("차익실현", "negative", ["차익실현 매물", "차익 실현 매물"]),
    ("급등매물", "negative", ["급등 매물", "급등 후 매물"]),
    ("광통신인프라", "neutral", ["광통신 인프라", "광 통신 인프라"]),
    ("후공정", "neutral", ["후공정", "후공정 장비", "반도체 후공정"]),
    ("업황개선", "positive", ["업황 개선", "업황이 개선", "업황 회복"]),
    ("업황기대", "positive", ["업황 기대", "업황 개선 기대", "업황 회복 기대"]),
    ("가격인상", "negative", ["가격 인상", "가격을 인상", "가격 인상폭"]),
    ("가격인하", "positive", ["가격 인하", "가격을 인하"]),
    ("가격동결", "neutral", ["가격 동결", "가격을 동결"]),
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
    # HBM should surface as a complete material phrase, never as the bare product name.
    ("HBM개발", "neutral", ["hbm 개발", "고대역폭 메모리 개발"]),
    ("HBM개발속도", "positive", ["hbm 개발 속도", "hbm 개발 가속", "hbm 개발 속도를 높", "hbm 개발에 속도"]),
    ("커스텀HBM개발", "neutral", ["커스텀 hbm 개발", "맞춤형 hbm 개발", "custom hbm 개발"]),
    ("HBM양산", "positive", ["hbm 양산", "hbm4 양산", "hbm3e 양산"]),
    ("HBM공급확대", "positive", ["hbm 공급 확대", "hbm 공급량 확대", "hbm 공급을 확대"]),
    ("HBM공급부족", "positive", ["hbm 공급 부족", "hbm 품귀", "hbm 부족"]),
    ("HBM수요급증", "positive", ["hbm 수요 급증", "hbm 수요 폭증", "hbm 수요가 급증"]),
    ("HBM가격상승", "positive", ["hbm 가격 상승", "hbm 가격 강세", "hbm 가격 인상"]),
    ("HBM증설경쟁", "neutral", ["hbm 증설 경쟁", "hbm 생산 확대 경쟁", "hbm 생산능력 확대 경쟁"]),
    ("HBM점유율상승", "positive", ["hbm 점유율 상승", "hbm 점유율 확대"]),
    ("HBM점유율하락", "negative", ["hbm 점유율 하락", "hbm 점유율 감소"]),
    ("HBM인증", "neutral", ["hbm 인증", "hbm 품질 인증", "hbm 품질인증"]),
    ("HBM4개발", "neutral", ["hbm4 개발", "hbm 4 개발"]),
    ("HBM4양산", "positive", ["hbm4 양산", "hbm 4 양산"]),
    ("HBM4적용", "neutral", ["hbm4 적용", "hbm 4 적용", "hbm4를 적용", "hbm4가 적용"]),
    ("차세대HBM", "neutral", ["차세대 hbm", "차세대 고대역폭 메모리"]),
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
        # Toss-style causal summaries: subject + direction/result. These
        # phrases are useful only when the article itself states the full cause.
        ("메모리업황기대", ["메모리 업황 기대", "메모리 업황 회복 기대"]),
        ("외국인매도부담", ["외국인 매도 부담", "외국인 순매도 부담"]),
        ("AI서버부품수혜", ["AI 서버 부품 수혜", "AI서버 부품 수혜"]),
        ("HBM장비주강세", ["HBM 장비주 강세", "HBM장비주 강세"]),
        ("기관순매수효과", ["기관 순매수 효과", "기관 순매수 영향"]),
        ("광통신수요확대", ["광통신 수요 확대", "광통신수요 확대"]),
        ("광통신수요증가", ["광통신 수요 증가", "광통신수요 증가"]),
        ("광통신수요감소", ["광통신 수요 감소", "광통신수요 감소"]),
        ("광통신수요둔화", ["광통신 수요 둔화", "광통신수요 둔화"]),
        ("반도체소부장약세", ["반도체 소부장 약세", "반도체소부장 약세"]),
        ("반도체주강세", ["반도체주 강세", "반도체 주 강세"]),
        ("기술주랠리", ["기술주 랠리", "기술주 상승 랠리"]),
        ("기술주강세", ["기술주 강세"]),
        ("가격경쟁력", ["가격 경쟁력", "가격경쟁력"]),
        ("성장펀더멘털부각", ["성장 펀더멘털 부각", "성장펀더멘털 부각"]),
        ("애저성장전망", ["애저 성장 전망", "Azure 성장 전망"]),
        ("AI인프라확대", ["AI 인프라 확대", "AI인프라 확대"]),
        ("보호예수해제부담", ["보호예수 해제 부담", "락업 해제 부담"]),
        ("중동긴장부담", ["중동 긴장 부담", "중동 긴장감 부담"]),
        ("반독점조사부담", ["반독점 조사 부담", "반독점 규제 조사 부담"]),
        ("기관매수전환", ["기관 매수 전환", "기관 순매수 전환"]),
        ("외국인기관매도", ["외국인·기관 매도", "외국인 기관 매도", "외국인과 기관 매도"]),
        ("반도체업황기대", ["반도체 업황 기대", "반도체 업황 회복 기대"]),
        ("ETF자금순유입", ["ETF 자금 순유입", "ETF자금 순유입"]),
        ("금리인상우려", ["금리 인상 우려", "금리인상 우려"]),
        # Curated high-signal event/result phrases from research-style cause vocab.
        ("영업이익률개선", ["영업이익률 개선", "영업 이익률 개선"]),
        ("영업이익률하락", ["영업이익률 하락", "영업 이익률 하락"]),
        ("영업이익급증", ["영업이익 급증", "영업익 급증"]),
        ("영업이익급감", ["영업이익 급감", "영업익 급감"]),
        ("적자폭축소", ["적자 폭 축소", "적자폭 축소"]),
        ("적자확대", ["적자 확대", "적자폭 확대", "적자 폭 확대"]),
        ("수율개선", ["수율 개선", "수율이 개선"]),
        ("퀄테스트통과", ["퀄테스트 통과", "퀄 테스트 통과"]),
        ("퀄테스트탈락", ["퀄테스트 탈락", "퀄 테스트 탈락"]),
        ("수주잔고최고치", ["수주 잔고 최고치", "수주잔고 최고치", "수주 잔고 사상 최대"]),
        ("수주잔고감소", ["수주 잔고 감소", "수주잔고 감소"]),
        ("단가인상", ["단가 인상", "판매단가 인상"]),
        ("단가인하", ["단가 인하", "단가 인하 요구"]),
        ("출하량증가", ["출하량 증가", "출하량이 증가"]),
        ("출하량감소", ["출하량 감소", "출하량이 감소"]),
        ("FDA승인", ["FDA 승인", "미국 FDA 승인"]),
        ("FDA승인거절", ["FDA 승인 거절", "FDA 승인 반려"]),
        ("품목허가반려", ["품목 허가 반려", "품목허가 반려"]),
        ("임상3상성공", ["임상 3상 성공", "3상 임상 성공"]),
        ("임상실패", ["임상 실패", "임상시험 실패"]),
        ("1차평가변수충족", ["1차 평가변수 충족", "1차 평가 변수 충족"]),
        ("양산개시", ["양산 개시", "양산 시작", "양산 체제 돌입"]),
        ("공장가동중단", ["공장 가동 중단", "생산시설 가동 중단"]),
        ("자사주매입", ["자사주 매입", "자기주식 취득"]),
        ("자사주소각", ["자사주 소각", "자기주식 소각"]),
        ("배당확대", ["배당 확대", "배당 증액"]),
        ("배당축소", ["배당 축소", "배당 감액"]),
        ("가이던스하향", ["가이던스 하향", "실적 가이던스 하향"]),
        ("원가율상승", ["원가율 상승", "원가율이 상승"]),
        ("판관비급증", ["판관비 급증", "판매관리비 급증"]),
        ("재고자산평가손실", ["재고자산 평가손실", "재고 자산 평가손실"]),
        ("계약해지", ["계약 해지", "공급계약 해지"]),
        ("수주취소", ["수주 취소", "수주가 취소"]),
        ("납품연기", ["납품 연기", "납품 지연"]),
        ("품질하자", ["품질 하자", "제품 하자"]),
        ("리콜발생", ["리콜 발생", "리콜을 실시"]),
        ("가동률저하", ["가동률 저하", "가동률이 하락"]),
        ("보호예수해제", ["보호예수 해제", "락업 해제"]),
        ("대주주지분매도", ["대주주 지분 매도", "대주주 지분을 매도"]),
        ("감사의견거절", ["감사의견 거절", "감사 의견 거절"]),
        ("감사의견한정", ["감사의견 한정", "감사 의견 한정"]),
        ("자본잠식", ["자본잠식", "자본 잠식"]),
        ("상장폐지실질심사", ["상장폐지 실질심사", "상장 폐지 실질심사"]),
        ("불성실공시법인지정", ["불성실공시법인 지정", "불성실 공시법인 지정"]),
        ("반대매매물량", ["반대매매 물량", "반대 매매 물량"]),
        ("재료소멸", ["재료 소멸", "재료소멸"]),
        # Deep-granular signals: keep concrete accounting, filing, approval and flow events.
        ("EBITDA증가", ["EBITDA 증가", "에비타 증가"]),
        ("판관비율하락", ["판관비율 하락", "판관비 비율 하락"]),
        ("부채비율감소", ["부채비율 감소", "부채 비율 감소"]),
        ("차입금상환", ["차입금 상환", "차입금을 상환"]),
        ("FCF양수전환", ["FCF 양수 전환", "잉여현금흐름 양수 전환"]),
        ("최대주주장내매수", ["최대주주 장내매수", "최대 주주 장내 매수"]),
        ("임원장내매수", ["임원 장내매수", "임원 장내 매수"]),
        ("신규시설투자", ["신규 시설투자", "신규시설 투자"]),
        ("CE인증획득", ["CE 인증 획득", "CE인증 획득"]),
        ("GMP승인", ["GMP 승인", "GMP 인증 승인"]),
        ("IND승인", ["IND 승인", "임상시험계획 승인"]),
        ("소재국산화", ["소재 국산화"]),
        ("부품국산화", ["부품 국산화"]),
        ("연기금연속순매수", ["연기금 연속 순매수"]),
        ("패시브자금유입", ["패시브 자금 유입"]),
        ("ETF신규편입", ["ETF 신규 편입"]),
        ("공매도잔고감소", ["공매도 잔고 감소"]),
        ("감사보고서제출지연", ["감사보고서 제출 지연"]),
        ("내부회계비적정", ["내부회계관리제도 비적정", "내부회계관리제도 부적정"]),
        ("계속기업불확실성", ["계속기업 가정 불확실성", "계속기업 존속능력 불확실성"]),
        ("불성실공시지정예고", ["불성실공시법인 지정예고", "불성실 공시법인 지정 예고"]),
        ("유상증자납입연기", ["유상증자 납입일 연기", "유증 납입일 연기"]),
        ("전환가액하향조정", ["전환가액 하향 조정", "전환 가격 하향 조정"]),
        ("단기차입금증가", ["단기차입금 증가", "단기 차입금 증가"]),
        ("채무불이행", ["채무불이행", "채무 불이행"]),
        ("신용등급하향", ["신용등급 하향", "신용 등급 하향"]),
        ("특허침해소송", ["특허침해 소송", "특허 침해 소송"]),
        ("손해배상청구소송", ["손해배상 청구소송", "손해 배상 청구 소송"]),
        ("공정위과징금", ["공정위 과징금", "공정거래위원회 과징금"]),
        ("보호예수해제물량", ["보호예수 해제 물량", "락업 해제 물량"]),
        ("대주주장내매도", ["대주주 장내매도", "대주주 장내 매도"]),
        ("임원장내매도", ["임원 장내매도", "임원 장내 매도"]),
        ("공매도잔고증가", ["공매도 잔고 증가"]),
    ]

    # Broad words are useful classification context but weak final summary
    # keywords when a more concrete article phrase exists.
    broad_labels = {"AI", "반도체", "메모리", "시장", "기업", "주식", "증시"}
    # Generic event labels remain available as fallback evidence, but should
    # lose to keywords that explain scale, direction, industry state or result.
    weak_final_labels = {
        "매출발표", "자금조달", "투자계획", "설비투자", "주식발행",
        "실적전망", "지표발표", "신규도입", "시장진출",
        "공급과잉", "가격경쟁", "투자확대", "현금유입", "수요증가", "수요둔화",
        "낸드가격", "메모리가격", "D램가격",
    }
    # These labels are useful internally but are too generic for the three
    # user-facing material slots. Never surface them as final keywords.
    blocked_final_labels = {
        "매출발표", "자금조달",
        "낸드가격", "메모리가격", "D램가격",
        "HBM", "국채금리", "주도주", "성과급", "신제품", "보조금", "광통신", "점유율확대", "고금리", "설비투자", "AI모델",
        "수요증가", "수요둔화",
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

        # Grounded semantic phrase extraction. This is intentionally generic:
        # compose a keyword from wording already present in the article instead
        # of requiring the exact phrase to exist in a dictionary. To avoid
        # promoting another company's event from a broad market article, only
        # use clauses/sentences that explicitly mention the selected stock.
        grounded_texts = (("title", title, 109), ("description", description, 69))
        action_words = (
            "확대", "확충", "강화", "상향", "하향", "증가", "감소", "급증", "급감",
            "상승", "하락", "강세", "약세", "진출", "수출", "수주", "계약", "협력",
            "재편", "개발", "출시", "공개", "도입", "매입", "매도", "인수", "매각",
            "투자", "양산", "생산", "공급", "돌파", "회복", "둔화", "개선", "악화",
        )
        topic_words = (
            "AI", "반도체", "메모리", "데이터센터", "협력망", "공급망", "산업화",
            "수출역량", "생산능력", "점유율", "수요", "공급", "가격", "매출",
            "영업이익", "실적", "가이던스", "투자", "기술", "시장",
        )

        for source_name, source_text, priority in grounded_texts:
            # Headlines are already the article center. Description text is
            # sentence-scoped so a secondary company's event cannot leak into
            # the selected stock's representative keyword.
            segments = [source_text] if source_name == "title" else [
                part.strip() for part in re.split(r"[.!?。]|(?:\s+[·•]\s+)", source_text) if part.strip()
            ]
            for segment in segments:
                segment_lower = segment.lower()
                if not any(alias and alias in segment_lower for alias in aliases):
                    continue

                # Remove the searched company token only from the label source;
                # evidence remains the untouched article text.
                label_source = segment
                for alias in sorted(aliases, key=len, reverse=True):
                    if alias:
                        label_source = re.sub(re.escape(alias), " ", label_source, flags=re.IGNORECASE)

                # Preserve a grounded topic + action phrase, allowing Korean
                # particles or short modifiers between them.
                for topic in topic_words:
                    topic_match = re.search(re.escape(topic), label_source, flags=re.IGNORECASE)
                    if not topic_match:
                        continue
                    tail = label_source[topic_match.end():topic_match.end() + 28]
                    action_match = re.search("|".join(map(re.escape, action_words)), tail)
                    if not action_match:
                        continue
                    action = action_match.group(0)
                    between = tail[:action_match.start()]
                    # Topic/action must be a compact phrase. Long prose bridges are
                    # where false joins such as 가격탄력성...공급 are created.
                    bridge_tokens = re.findall(r"[A-Za-z0-9가-힣]+", between)
                    if len(between.strip()) > 12 or len(bridge_tokens) > 2:
                        continue
                    # Keep at most one short meaningful modifier while dropping
                    # punctuation/particles; the article wording stays grounded.
                    modifier_tokens = re.findall(r"[A-Za-z0-9가-힣]+", between)
                    modifier = ""
                    for token in modifier_tokens:
                        clean_token = re.sub(r"(은|는|이|가|을|를|의|로|으로|에|서|와|과|도|만)$", "", token)
                        if 1 < len(clean_token) <= 10 and clean_token not in {"시장", "관련", "대한", "통해", "위해"}:
                            modifier = clean_token
                            break
                    topic_label = topic.upper() if topic.lower() == "ai" else topic
                    label = f"{topic_label}{modifier}{action}" if modifier else f"{topic_label}{action}"
                    add(label, f"{source_name}-grounded", segment, priority + 2)

                # Concrete achievement/result phrases outrank loose topic+action joins.
                # Examples: "37만6840대로 2위 탈환", "시장점유율 1위 탈환".
                result_patterns = (
                    r"(\d+(?:[.,]\d+)?(?:만|천)?(?:대|개|명|건)?)(?:로|으로)?\s*(\d+위)\s*(탈환|등극|진입|상승)",
                    r"(\d+위)\s*(탈환|등극|진입|상승)",
                )
                for pattern in result_patterns:
                    for match in re.finditer(pattern, label_source):
                        compact_result = re.sub(r"[^A-Za-z0-9가-힣%]", "", match.group(0))
                        if compact_result:
                            add(compact_result, f"{source_name}-grounded-result", segment, priority + 7)

                # Numeric scale is meaningful when attached to a concrete topic
                # in the same stock-anchored sentence: e.g. 데이터센터 4047조.
                scale_pattern = r"(\d+(?:[.,]\d+)?)\s*(조|억|만|%|달러|원)"
                for topic in topic_words:
                    topic_match = re.search(re.escape(topic), label_source, flags=re.IGNORECASE)
                    if not topic_match:
                        continue
                    nearby = label_source[topic_match.end():topic_match.end() + 32]
                    scale_match = re.search(scale_pattern, nearby)
                    if scale_match:
                        amount = re.sub(r"\s+", "", scale_match.group(0))
                        topic_label = topic.upper() if topic.lower() == "ai" else topic
                        add(f"{topic_label}{amount}", f"{source_name}-grounded-scale", segment, priority + 3)

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

            # Prefer the article's completed financing/investment meaning over
            # generic 자금조달/투자 labels.
            if re.search(r"(외부|외부에서|외부로부터).{0,12}(자금|투자금).{0,8}(조달|유치)|(?:외부자금).{0,8}(조달|유치)", compact_source):
                add("외부자금조달", f"{source_name}-sharp", "외부 자금 조달", priority + 2)

            if re.search(r"(대규모|대형|공격적|대대적).{0,10}(투자|설비투자|시설투자)|(?:투자|설비투자|시설투자).{0,10}(대규모|대형)", compact_source):
                add("대규모투자", f"{source_name}-sharp", "대규모 투자", priority + 2)

            investment_amount = re.search(
                r"(\\d+(?:[.,]\\d+)?(?:조|억)원?).{0,10}(투자|설비투자|시설투자)|"
                r"(?:투자|설비투자|시설투자).{0,10}(\\d+(?:[.,]\\d+)?(?:조|억)원?)",
                compact_source,
            )
            if investment_amount:
                amount = next((g for g in investment_amount.groups() if g), "")
                add(f"{amount}투자", f"{source_name}-sharp", investment_amount.group(0), priority + 2)

            # Preserve product/technology + concrete market action from the article itself.
            # These are grounded phrase combinations, not stock-specific keyword mappings.
            compact_plain = re.sub(r"\\s+", "", source_text)
            for match in re.finditer(r"([A-Za-z0-9가-힣]+).{0,8}(?:시장)?점유율.{0,10}(확대|상승|증가|추격)", compact_plain, flags=re.IGNORECASE):
                subject = re.sub(r"[^A-Za-z0-9가-힣]", "", match.group(1))
                if subject and subject.lower() not in aliases:
                    add(f"{subject}점유율{match.group(2)}", f"{source_name}-sharp", match.group(0), priority + 3)

            # Headlines such as "HBM4로 시장 점유율 확대" omit the product
            # immediately before 점유율. Keep the nearest concrete product token.
            for match in re.finditer(r"([A-Za-z]+\\d+[A-Za-z0-9-]*|[A-Za-z]{2,}\\d*).{0,14}(?:시장)?점유율.{0,10}(확대|상승|증가|추격)", source_text, flags=re.IGNORECASE):
                product = match.group(1).upper() if match.group(1).lower().startswith("hbm") else match.group(1)
                add(f"{product}점유율{match.group(2)}", f"{source_name}-sharp", match.group(0), priority + 4)

            # Concrete employment effects should retain the stated scale.
            for match in re.finditer(r"(\\d+(?:[.,]\\d+)?(?:만|천)?명).{0,12}(?:고용|일자리).{0,8}(?:창출|효과|예상|전망)?", source_text):
                amount = re.sub(r"\\s+", "", match.group(1))
                add(f"{amount}고용창출", f"{source_name}-sharp", match.group(0), priority + 2)

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

        # Context combinations for financing/dilution events. Ambiguous nouns
        # such as 유상증자/CB are not directional by themselves; surface only
        # the concrete structure/result stated by the article.
        context_texts = (("title", title, 105), ("description", description, 65))
        for source_name, source_text, priority in context_texts:
            compact = re.sub(r"\s+", "", source_text.lower())

            if "유상증자" in compact or "유증" in compact:
                if "제3자배정" in compact or "3자배정" in compact:
                    add("제3자배정유상증자", f"{source_name}-context", "제3자배정 유상증자", priority)
                    if any(word in compact for word in ("납입완료", "납입성공", "납입확정")):
                        add("제3자배정납입완료", f"{source_name}-context", "제3자배정 유상증자 납입 완료", priority + 3)
                if "주주배정" in compact:
                    add("주주배정유상증자", f"{source_name}-context", "주주배정 유상증자", priority)
                if any(word in compact for word in ("납입일연기", "납입연기")):
                    add("유상증자납입연기", f"{source_name}-context", "유상증자 납입 연기", priority + 3)
                if any(word in compact for word in ("지분희석", "주가희석", "희석우려", "희석부담")):
                    add("유상증자지분희석", f"{source_name}-context", "유상증자 지분 희석", priority + 2)

            cb_present = any(word in compact for word in ("전환사채", "cb발행", "cb "))
            bw_present = any(word in compact for word in ("신주인수권부사채", "bw발행", "bw "))
            if cb_present:
                if any(word in compact for word in ("전환가액하향", "전환가격하향", "리픽싱")):
                    add("CB리픽싱", f"{source_name}-context", "CB 전환가액 하향", priority + 3)
                if any(word in compact for word in ("전환청구권행사", "전환권행사")):
                    add("CB전환청구권행사", f"{source_name}-context", "CB 전환청구권 행사", priority + 2)
            if bw_present and any(word in compact for word in ("신주인수권행사", "행사청구")):
                add("BW신주인수권행사", f"{source_name}-context", "BW 신주인수권 행사", priority + 2)

            if any(word in compact for word in ("보호예수해제", "락업해제")):
                if any(word in compact for word in ("물량", "주식", "오버행", "매물")):
                    add("보호예수해제물량", f"{source_name}-context", "보호예수 해제 물량", priority + 2)

        # Accounting / operating-driver combinations. Preserve the metric,
        # direction and (when stated) magnitude instead of collapsing to a noun.
        driver_texts = (("title", title, 104), ("description", description, 64))
        for source_name, source_text, priority in driver_texts:
            driver_rules = (
                ("영업이익률", "영업이익률"),
                ("매출총이익률", "매출총이익률"),
                ("GPM", "GPM"),
                ("원가율", "원가율"),
                ("판관비율", "판관비율"),
                ("부채비율", "부채비율"),
                ("가동률", "가동률"),
                ("수율", "수율"),
                ("출하량", "출하량"),
                ("판매량", "판매량"),
            )
            direction_map = {
                "증가": "증가", "상승": "상승", "개선": "개선", "확대": "확대",
                "감소": "감소", "하락": "하락", "악화": "악화", "축소": "축소",
                "급증": "급증", "급감": "급감",
            }
            for phrase, label_base in driver_rules:
                pattern = re.escape(phrase) + r".{0,10}?(급증|급감|증가|감소|상승|하락|개선|악화|확대|축소)"
                for match in re.finditer(pattern, source_text, flags=re.IGNORECASE):
                    add(f"{label_base}{direction_map[match.group(1)]}", f"{source_name}-driver", match.group(0), priority)

                pct_pattern = (
                    re.escape(phrase)
                    + r".{0,12}?(\d+(?:\.\d+)?)\s*%\s*(?:p|포인트)?\s*"
                    + r"(증가|감소|상승|하락|개선|악화)"
                )
                for match in re.finditer(pct_pattern, source_text, flags=re.IGNORECASE):
                    value, direction = match.group(1), match.group(2)
                    add(f"{label_base}{value}%{direction}", f"{source_name}-driver", match.group(0), priority + 3)

            # P/Q/C style operating causes frequently used in research notes.
            compact = re.sub(r"\s+", "", source_text)
            pqc_rules = (
                ("단가", ("인상", "상승", "하락", "인하")),
                ("출하량", ("증가", "확대", "감소", "축소")),
                ("판매량", ("증가", "확대", "감소", "축소")),
                ("원가", ("상승", "증가", "하락", "감소")),
                ("고정비", ("절감", "감소", "증가")),
            )
            for base, directions in pqc_rules:
                for direction in directions:
                    if base + direction in compact:
                        add(f"{base}{direction}", f"{source_name}-driver", f"{base} {direction}", priority + 1)

        # Filing / audit / litigation combinations. Keep the concrete
        # regulatory event rather than surfacing generic "소송/감사/공시" nouns.
        risk_texts = (("title", title, 106), ("description", description, 66))
        for source_name, source_text, priority in risk_texts:
            compact = re.sub(r"\s+", "", source_text.lower())

            audit_rules = (
                ("감사보고서제출지연", ("감사보고서제출지연", "감사보고서지연")),
                ("감사의견거절", ("감사의견거절",)),
                ("감사의견한정", ("감사의견한정",)),
                ("내부회계비적정", ("내부회계관리제도비적정", "내부회계관리제도부적정")),
                ("계속기업불확실성", ("계속기업가정불확실성", "계속기업존속능력불확실성")),
                ("불성실공시지정예고", ("불성실공시법인지정예고",)),
                ("불성실공시법인지정", ("불성실공시법인지정",)),
                ("매매거래정지예고", ("매매거래정지예고", "거래정지예고")),
                ("상장폐지실질심사", ("상장폐지실질심사",)),
            )
            for label, phrases in audit_rules:
                if any(p in compact for p in phrases):
                    add(label, f"{source_name}-risk", label, priority + 2)

            litigation_rules = (
                ("특허침해소송", ("특허침해소송", "특허침해소송제기")),
                ("특허무효소송", ("특허무효소송",)),
                ("손해배상청구소송", ("손해배상청구소송", "손해배상소송")),
                ("직무집행정지가처분", ("직무집행정지가처분",)),
                ("검찰압수수색", ("검찰압수수색", "압수수색영장")),
                ("공정위과징금", ("공정위과징금", "공정거래위원회과징금")),
                ("주가조작혐의", ("주가조작혐의", "시세조종혐의")),
            )
            for label, phrases in litigation_rules:
                if any(p in compact for p in phrases):
                    add(label, f"{source_name}-risk", label, priority + 2)

            # Debt/default stress should be explicit; generic borrowing is not enough.
            debt_rules = (
                ("채무불이행", ("채무불이행", "디폴트")),
                ("어음부도", ("어음부도", "수표부도", "어음수표부도")),
                ("당좌거래정지", ("당좌거래정지",)),
                ("신용등급하향", ("신용등급하향", "신용등급강등")),
                ("단기차입금증가", ("단기차입금증가",)),
            )
            for label, phrases in debt_rules:
                if any(p in compact for p in phrases):
                    add(label, f"{source_name}-risk", label, priority + 1)

        # Market-microstructure combinations. Keep actor + action + direction
        # together so generic "수급" or "공매도" nouns never become the reason.
        micro_texts = (("title", title, 105), ("description", description, 65))
        for source_name, source_text, priority in micro_texts:
            compact = re.sub(r"\s+", "", source_text.lower())
            micro_rules = (
                ("연기금연속순매수", ("연기금연속순매수", "연기금연속매수")),
                ("패시브자금유입", ("패시브자금유입", "패시브펀드자금유입")),
                ("프로그램순매수", ("프로그램순매수", "프로그램매수우위")),
                ("대차잔고감소", ("대차잔고감소",)),
                ("대차잔고증가", ("대차잔고증가",)),
                ("공매도잔고감소", ("공매도잔고감소",)),
                ("공매도잔고증가", ("공매도잔고증가",)),
                ("공매도숏커버", ("공매도숏커버", "숏커버링", "쇼트커버링")),
                ("대주주장내매수", ("대주주장내매수", "최대주주장내매수")),
                ("대주주장내매도", ("대주주장내매도", "최대주주장내매도")),
                ("임원장내매수", ("임원장내매수",)),
                ("임원장내매도", ("임원장내매도",)),
                ("시간외대량매매", ("시간외대량매매", "블록딜")),
                ("반대매매실행", ("반대매매실행", "반대매매물량")),
            )
            for label, phrases in micro_rules:
                if any(p in compact for p in phrases):
                    add(label, f"{source_name}-micro", label, priority + 2)

            # Index/ETF inclusion is useful only with the concrete destination.
            index_rules = (
                ("MSCI편입", ("msci편입", "msci지수편입")),
                ("코스피200편입", ("코스피200편입", "kospi200편입")),
                ("ETF신규편입", ("etf신규편입", "etf편입")),
            )
            for label, phrases in index_rules:
                if any(p in compact for p in phrases):
                    add(label, f"{source_name}-micro", label, priority + 1)

        # Bio / approval / supply-chain milestone combinations. Prefer a
        # completed milestone (approval/pass/designation) over a bare technology noun.
        milestone_texts = (("title", title, 106), ("description", description, 66))
        for source_name, source_text, priority in milestone_texts:
            compact = re.sub(r"\s+", "", source_text.lower())
            milestone_rules = (
                ("FDA승인", ("fda승인", "fda품목허가승인")),
                ("FDA승인거절", ("fda승인거절", "fda승인반려")),
                ("IND승인", ("ind승인", "임상시험계획승인")),
                ("NDA신청", ("nda신청", "fda신약허가신청")),
                ("임상3상성공", ("임상3상성공", "3상임상성공")),
                ("1차평가변수충족", ("1차평가변수충족", "1차평가지표충족")),
                ("CE인증획득", ("ce인증획득", "ce인증취득")),
                ("GMP승인", ("gmp승인", "gmp인증승인")),
                ("퀄테스트통과", ("퀄테스트통과", "품질테스트통과")),
                ("퀄테스트탈락", ("퀄테스트탈락", "품질테스트탈락")),
                ("벤더등록", ("벤더등록", "vendor등록", "공급업체등록")),
                ("Tier1공급사지정", ("tier1공급사지정", "tier1벤더지정")),
                ("소재국산화", ("소재국산화",)),
                ("부품국산화", ("부품국산화",)),
                ("AEC-Q200인증", ("aec-q200인증", "aecq200인증")),
            )
            for label, phrases in milestone_rules:
                if any(p in compact for p in phrases):
                    add(label, f"{source_name}-milestone", label, priority + 2)

            # Keep customer qualification concrete when the customer is stated.
            customer_tokens = ("엔비디아", "nvidia", "애플", "apple", "테슬라", "tesla", "삼성전자", "sk하이닉스")
            if any(customer in compact for customer in customer_tokens):
                if "퀄테스트통과" in compact or "품질테스트통과" in compact:
                    add("고객사퀄테스트통과", f"{source_name}-milestone", "고객사 퀄테스트 통과", priority + 3)
                if any(word in compact for word in ("공급망진입", "벤더등록", "공급사지정")):
                    add("고객사공급망진입", f"{source_name}-milestone", "고객사 공급망 진입", priority + 3)

        # Dynamic earnings facts: keep the financial item attached to its
        # actual amount so high-value facts do not collapse into generic "매출발표".
        # Korean headlines often omit "원" ("영업익 108조 전망"), so amount-only
        # earnings forecasts need their own grounded pattern.
        amount_pattern = r"\d+(?:[.,]\d+)?\s*(?:조(?:\s*\d+(?:[.,]\d+)?\s*억)?|억|만)?\s*원"
        earnings_texts = (("title", title, 98), ("description", description, 58))
        forecast_amount_pattern = r"(?<![\d.])(\d+(?:[.,]\d+)?\s*(?:조(?:\s*\d+(?:[.,]\d+)?\s*억)?|억))\s*(?:원)?"
        forecast_words = r"(전망|예상|추정|관측|내다봐|내다봤|기대)"
        for source_name, source_text, priority in earnings_texts:
            # e.g. "3분기 영업익 108조 전망", "영업이익 100조 시대 연다"
            metric_forecast = (
                r"(영업이익|영업익|매출|순이익)\s*(?:은|는|이|가|약|총|첫)?.{0,18}?"
                + forecast_amount_pattern + r".{0,10}?" + forecast_words
            )
            for match in re.finditer(metric_forecast, source_text):
                metric = "영업이익" if match.group(1) == "영업익" else match.group(1)
                amount = re.sub(r"\s+", "", match.group(2))
                add(f"{metric}{amount}전망", f"{source_name}-earnings", match.group(0), priority + 3)

            # Headline shorthand where the metric is implied by nearby earnings context:
            # "108조 전망", "100조 시대 연다". Keep the article wording; do not invent a metric.
            if re.search(r"(실적|영업이익|영업익|매출|순이익)", source_text):
                for match in re.finditer(forecast_amount_pattern + r".{0,8}?" + forecast_words, source_text):
                    amount = re.sub(r"\s+", "", match.group(1))
                    add(f"{amount}전망", f"{source_name}-earnings", match.group(0), priority + 2)
                for match in re.finditer(forecast_amount_pattern + r"\s*(?:시대|시대가)\s*(?:연다|열린다|진입)", source_text):
                    amount = re.sub(r"\s+", "", match.group(1))
                    add(f"{amount}시대", f"{source_name}-earnings", match.group(0), priority + 2)

        for source_name, source_text, priority in earnings_texts:
            for metric in ("영업이익", "매출", "순이익"):
                metric_pattern = re.escape(metric) + r"\s*(?:은|는|이|가|을|를|도|약|총)?\s*(" + amount_pattern + r")"
                for match in re.finditer(metric_pattern, source_text):
                    amount = re.sub(r"\s+", "", match.group(1))
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
        # Negation guard: a phrase mentioned only to deny/dismiss it must not
        # become a user-facing cause keyword (e.g. "어닝쇼크가 아니다").
        negation_tails = ("아니다", "아니라", "아닌", "없다", "없어", "없었다", "면했다", "피했다")
        def is_negated_phrase(text_lower, phrase):
            start = text_lower.find(phrase.lower())
            if start < 0:
                return False
            tail = text_lower[start + len(phrase):start + len(phrase) + 18]
            return any(token in tail for token in negation_tails)

        for label, phrases in summary_rules:
            matched = next(
                (p for p in phrases if p.lower() in title_lower and not is_negated_phrase(title_lower, p)),
                "",
            )
            if matched:
                add(label, "title", matched, 100)

        # Existing signal dictionaries remain useful as supporting vocabulary,
        # but title matches outrank description-only matches.
        # score_stock_news() already refined the shared DETAIL_KEYWORD_RULES
        # into movement_signals. Reuse that result here so newly added shared
        # keywords reach article_keywords without running the expensive matcher
        # a second time for every article.
        # movement_signals are evidence for scoring/classification only.
        # Do not promote them directly into user-facing article keywords:
        # generic evidence such as product/category/context words can be useful
        # internally without explaining why the stock may move.

        # 2) Description supplements the headline; it never replaces the
        # headline as the article's center.
        for label, phrases in summary_rules:
            if label in seen:
                continue
            matched = next(
                (p for p in phrases if p.lower() in desc_lower and not is_negated_phrase(desc_lower, p)),
                "",
            )
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

        # Keep extraction permissive, then reject only obvious malformed joins.
        # This preserves rich novel phrases/numbers while preventing connective
        # endings from becoming user-facing keywords.
        malformed_connectives = (
            "하고", "하며", "하면서", "있으며", "했으며", "됐으며", "되었으며",
            "이어", "통해", "그리고", "또한",
        )
        candidates = [
            row for row in candidates
            if not any(token in row["label"] for token in malformed_connectives)
        ]
        # Broad topic + trading-action joins are usually nearby market wording,
        # not the selected company's concrete event. Reject them late instead
        # of weakening extraction of legitimate technology/market phrases.
        candidates = [
            row for row in candidates
            if row["label"] not in {"기술매수", "기술매도", "시장매수", "시장매도"}
        ]
        # A bare generic noun plus a number (가격1만, 시장10억, 투자5만...) is
        # not self-explanatory. Keep numeric facts only when the label names a
        # concrete metric/object such as 영업이익185조, 데이터센터4047조원.
        vague_numeric_prefixes = ("가격", "시장", "투자", "기술", "공급", "수요")
        candidates = [
            row for row in candidates
            if not (
                row["label"].startswith(vague_numeric_prefixes)
                and re.fullmatch(r"(?:가격|시장|투자|기술|공급|수요)\d+(?:[.,]\d+)?(?:조원?|억원?|만원?|천원?|원|달러|%)?", row["label"])
            )
        ]

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
