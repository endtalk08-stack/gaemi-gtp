import threading
import time
from backend.services import engine

_WARMUP_TICKERS_KR = ["005930.KS", "000660.KS"]
_WARMUP_TICKERS_US = ["NVDA", "TSLA", "AAPL"]

def _gaemigtp_warmup_cache():
    try:
        time.sleep(1.0)
        if engine.OPENDART_API_KEY:
            engine.fetch_dart_corp_map()
        time.sleep(20.0)
        for code in _WARMUP_TICKERS_KR:
            try:
                clean_code = ''.join(filter(str.isdigit, code))
                if clean_code:
                    engine.fetch_kr_official_disclosures(clean_code)
            except Exception as e:
                print(f"[워밍업] DART {code} 건너뜀: {type(e).__name__}: {e}")
        for ticker in _WARMUP_TICKERS_US:
            try:
                engine.fetch_us_official_filings(ticker)
            except Exception as e:
                print(f"[워밍업] SEC {ticker} 건너뜀: {type(e).__name__}: {e}")
        print("[워밍업] DART/SEC 백그라운드 초기 캐시 준비 완료")
    except Exception as e:
        print(f"[워밍업] 전체 건너뜀: {type(e).__name__}: {e}")

def start():
    # Import 시 요청을 막지 않고 백그라운드에서 한 번만 시작한다.
    try:
        if any(t.name == "gaemigtp-cache-warmup" and t.is_alive() for t in threading.enumerate()):
            return
        threading.Thread(target=_gaemigtp_warmup_cache, name="gaemigtp-cache-warmup", daemon=True).start()
    except Exception as e:
        print(f"[워밍업] 스레드 시작 실패: {type(e).__name__}: {e}")
