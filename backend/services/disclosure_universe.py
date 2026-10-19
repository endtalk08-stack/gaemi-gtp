"""Fixed 2026-10-19 public disclosure universe: exactly 20 KR and 20 US.

The ranking list is user-selected and not dynamically recalculated.
DART corporation codes and SEC registrant CIKs are not exchange ticker strings.
This module is data only: importing it does not fetch disclosures, schedule work,
write Neon, alter Render or make network calls.

Sources for newly added identifiers:
KR: SK Square 01596425 (bizsearch.io.kr), Samsung Electro 00126371 and
Samsung Life 00126256 (listbase.org), Hana Financial 00547583
(englishdart.fss.or.kr), SK Inc 00181712 (DART archive crosswalk).
US: SpaceX 0001181412, SK hynix 0002120882, Walmart 0000104169,
JPMorgan 0000019617, Visa 0001403161 (sec.gov EDGAR).
All entries must be rechecked against the regulator before live cutover.
"""
import re

KR_COMPANIES = {
    "005930": ("삼성전자", "00126380"),
    "000660": ("SK하이닉스", "00164779"),
    "402340": ("SK스퀘어", "01596425"),
    "373220": ("LG에너지솔루션", "01515323"),
    "009150": ("삼성전기", "00126371"),
    "005380": ("현대차", "00164742"),
    "207940": ("삼성바이오로직스", "00877059"),
    "105560": ("KB금융", "00688996"),
    "032830": ("삼성생명", "00126256"),
    "006400": ("삼성SDI", "00126362"),
    "012450": ("한화에어로스페이스", "00126566"),
    "028260": ("삼성물산", "00149655"),
    "068270": ("셀트리온", "00413046"),
    "000270": ("기아", "00106641"),
    "055550": ("신한지주", "00382199"),
    "034020": ("두산에너빌리티", "00159616"),
    "329180": ("HD현대중공업", "01390344"),
    "086790": ("하나금융지주", "00547583"),
    "034730": ("SK", "00181712"),
    "012330": ("현대모비스", "00164788"),
}

US_COMPANIES = {
    "NVDA": ("엔비디아", "0001045810"),
    "AAPL": ("애플", "0000320193"),
    "GOOGL": ("알파벳", "0001652044"),
    "MSFT": ("마이크로소프트", "0000789019"),
    "AMZN": ("아마존", "0001018724"),
    "TSM": ("TSMC", "0001046179"),
    "SPCX": ("SpaceX", "0001181412"),
    "META": ("메타", "0001326801"),
    "AVGO": ("브로드컴", "0001730168"),
    "TSLA": ("테슬라", "0001318605"),
    "BRK.B": ("버크셔 해서웨이", "0001067983"),
    "LLY": ("일라이 릴리", "0000059478"),
    "SKHY": ("SK하이닉스 미국 ADS", "0002120882"),
    "MU": ("마이크론", "0000723125"),
    "WMT": ("월마트", "0000104169"),
    "JPM": ("JP모건", "0000019617"),
    "AMD": ("AMD", "0000002488"),
    "V": ("비자", "0001403161"),
    "XOM": ("엑슨모빌", "0000034088"),
    "ASML": ("ASML", "0000937966"),
}

US_ALIASES = {"GOOG": "GOOGL"}


def disclosure_identity(market, symbol):
    """Fail closed on unknown market/ticker. No speculative substitutions."""
    market = str(market or "").upper().strip()
    symbol = str(symbol or "").upper().strip()
    if market == "US":
        symbol = US_ALIASES.get(symbol, symbol)
        record = US_COMPANIES.get(symbol)
    elif market == "KR":
        record = KR_COMPANIES.get(symbol) if re.fullmatch(r"[0-9]{6}", symbol) else None
    else:
        record = None
    if record is None:
        raise ValueError("stock_outside_fixed_disclosure_universe")
    return market, symbol, record[0], record[1]


def validate_universe():
    assert len(KR_COMPANIES) == len(US_COMPANIES) == 20
    assert all(re.fullmatch(r"[0-9]{6}", s) and re.fullmatch(r"[0-9]{8}", code)
               for s, (_, code) in KR_COMPANIES.items())
    assert all(re.fullmatch(r"[A-Z.]{1,10}", s) and re.fullmatch(r"[0-9]{10}", cik)
               for s, (_, cik) in US_COMPANIES.items())
    assert len({code for _, code in KR_COMPANIES.values()}) == 20
    assert len({cik for _, cik in US_COMPANIES.values()}) == 20
    return True
