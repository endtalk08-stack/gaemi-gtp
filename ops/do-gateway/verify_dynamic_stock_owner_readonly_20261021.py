"""Read-only DigitalOcean deployed stock-event identity smoke. No APIs or DB writes."""
import hashlib
from pathlib import Path
from backend.analysis.news.scoring import build_connected_keyword_test

live = Path("/opt/gaemigtp-news/app/backend/analysis/news/scoring.py").read_bytes()
expected = "aac7507e51274b8318efc2272e339632564e68af"
actual = hashlib.sha1(f"blob {len(live)}\\0".encode().replace(b"\\0", b"\0") + live).hexdigest()
assert actual == expected, f"Deployed scoring file mismatch: {actual}"
print("DO_SCORING_BLOB_VERIFIED=" + actual, flush=True)

def get(name, title, description):
    return build_connected_keyword_test([{
        "title":title, "description":description
    }], name)["articles"][0]

kr = get("HT로보틱스",
         "HT로보틱스 거래량 2559만주…로봇·ESS 양산 일정 관심",
         "HT로보틱스의 ESS 관련 양산 일정이 주목받고 있다.")
assert kr["relation_type"] == "direct" and kr["event_owner"] == "HT로보틱스", kr

us = get("Orion Quantum", "Orion Quantum signs supply agreement",
         "Orion Quantum signed a supply contract.")
assert us["relation_type"] == "direct" and us["event_owner"] == "Orion Quantum", us

other = get("HT로보틱스", "삼성전자 매출 확대, HT로보틱스는 동향 점검",
            "삼성전자가 매출 증가를 발표했다. HT로보틱스는 별도 소식이 없었다.")
assert other["relation_type"] == "indirect" and other["event_owner"] == "삼성전자", other
print("DO_KR_US_OWNER_SMOKE_PASS_NO_API_NO_AI_NO_DB", flush=True)
