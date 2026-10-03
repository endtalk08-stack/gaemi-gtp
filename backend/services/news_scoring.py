"""Explainable scoring for stock-news flow analysis.

This module does not collect news. It scores the normalized records produced by
news_feed so the central "왜?" flow can rank evidence without changing the
existing news panel. For the central keyword view, broad movement labels are
refined back to concrete phrases that are actually present in title+description.
"""

import datetime
from collections import Counter
from zoneinfo import ZoneInfo

from .news_feed import STOCK_UNIVERSE
from email.utils import parsedate_to_datetime
from kiwipiepy import Kiwi


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
    "외국인매도": [("외국인순매도", ["외국인 순매도"]), ("외국인매도", ["외국인 매도", "외인 매도"])],
    "기관매도": [("기관순매도", ["기관 순매도"]), ("기관매도", ["기관 매도"])],
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
    ("설비투자축소", "negative", ["설비투자 축소", "설비 투자 축소"]),
    ("공급부족", "positive", ["공급 부족"]),
    ("판매증가", "positive", ["판매 증가"]),
    ("판매감소", "negative", ["판매 감소"]),
    ("유럽판매감소", "negative", ["유럽 판매 감소"]),
    ("반발매수세", "positive", ["반발 매수세", "반발매수"]),
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
    ("연속영업손실", "negative", ["연속 영업손실", "연속 영업 손실", "영업손실 지속"]),
    ("적자지속", "negative", ["적자 지속", "적자가 지속"]),
    ("적자전환", "negative", ["적자 전환", "적자로 전환"]),
    ("흑자전환", "positive", ["흑자 전환", "흑자로 전환"]),
    ("영업이익감소", "negative", ["영업이익 감소", "영업 이익 감소", "영업이익이 감소"]),
    ("반도체업종비중", "neutral", ["반도체 업종 비중", "반도체업종 비중"]),
    ("시장모멘텀약화", "negative", ["시장 모멘텀 약화", "시장 모멘텀이 약화"]),
    ("매출사상최대", "positive", ["매출 사상 최대", "사상 최대 매출", "역대 최대 매출"]),
    ("분기매출증가", "positive", ["분기 매출 증가", "분기매출 증가"]),
    ("순매수상위", "positive", ["순매수 1위", "순매수1위", "순매수 2위", "순매수2위", "순매수 3위", "순매수3위"]),
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
    ("매도세", "negative", ["매도세", "매도세가"]),
    ("매수세", "positive", ["매수세", "매수세가"]),
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
    ("외국인매수", "positive", ["외국인 매수", "외국인 순매수", "외인 매수"]),
    ("기관매수", "positive", ["기관 매수", "기관 순매수"]),
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
                tone = "negative" if label in {"금리부담", "유가부담", "환율부담", "시장약세", "반도체주약세", "외국인매도", "기관매도", "실적악화", "전망하향"} else "positive"
                refined.append({"label": label, "tone": tone})
                seen.add(label)

    for label, tone, phrases in DETAIL_KEYWORD_RULES:
        if label not in seen and any(phrase.lower() in text for phrase in phrases):
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
        article_keywords = item.get("article_keywords") or []
        article_keyword_details = item.get("article_keyword_details") or []
        keywords = []
        keyword_tones = {}
        if len(article_keywords) == 3:
            detail_tones = {
                str(detail.get("label") or "").strip(): str(detail.get("tone") or "neutral").strip()
                for detail in article_keyword_details
            }
            for label in article_keywords:
                label = str(label or "").strip()
                if label and label not in STORYBOARD_EXCLUDED_KEYWORDS and label not in keywords:
                    keywords.append(label)
                    tone = detail_tones.get(label, "neutral")
                    keyword_tones[label] = tone if tone in ("positive", "negative", "neutral") else "neutral"
        else:
            signals = item.get("movement_signals") or []
            for signal in signals:
                label = str(signal.get("label") or "").strip()
                tone = str(signal.get("tone") or "neutral").strip()
                if label and label not in STORYBOARD_EXCLUDED_KEYWORDS and label not in keywords:
                    keywords.append(label)
                    keyword_tones[label] = tone if tone in ("positive", "negative", "neutral") else "neutral"
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

def build_connected_keyword_test(items, stock_name, max_keywords=3):
    """Extract up to three noun keywords from title + description with Kiwi."""
    import re

    aliases = {
        re.sub(r"\\s+", "", str(alias or "").strip()).lower()
        for alias in _stock_aliases(stock_name)
        if str(alias or "").strip()
    }
    kiwi = Kiwi()
    results = []

    for item in items or []:
        title = str(item.get("title") or "").strip()
        description = str(item.get("description") or "").strip()
        text = f"{title} {description}".strip()
        if not text:
            continue

        counts = Counter()
        first_position = {}
        for token in kiwi.tokenize(text):
            if not str(token.tag or "").startswith("N"):
                continue
            word = str(token.form or "").strip()
            if len(word) < 2:
                continue

            compact = re.sub(r"\\s+", "", word).lower()
            if any(compact == alias or compact in alias or alias in compact for alias in aliases):
                continue

            counts[word] += 1
            first_position.setdefault(word, int(token.start))

        ranked = sorted(
            counts,
            key=lambda word: (-counts[word], first_position.get(word, 10**9), -len(word), word),
        )

        selected = []
        for word in ranked[:max_keywords]:
            selected.append({
                "label": word,
                "source": "kiwi-noun",
                "evidence": word,
                "priority": counts[word],
                "support": counts[word],
            })

        keyword_labels = [row["label"] for row in selected]
        results.append({
            "title": title,
            "description": description,
            "candidate_keywords": ranked[:10],
            "keywords": keyword_labels,
            "keyword_details": selected,
            "enough_evidence": bool(keyword_labels),
            "status": "PASS" if keyword_labels else "SKIP",
        })

    return {"stock": stock_name, "articles": results}
