"""Read-only, MU-only company narrative preview from the existing Kiwoom/Neon registry.

The Micron descriptive copy is editorial material based on Micron's public
corporate profile; related companies are returned only when their recorded
sector exactly matches MU. No new provider calls, no AI calls, no DB writes.
"""
import os

MICRON_SOURCE = "https://www.micron.com/about/company/corporate-profile"
MICRON_INTRO = {
    "paragraphs": [
        "마이크론 테크놀로지(Micron Technology)는 미국의 메모리 반도체 전문 기업이에요. 컴퓨터와 스마트폰, 데이터센터, AI 서버에 필요한 메모리와 저장장치를 개발하고 생산합니다.",
        "쉽게 말해, 컴퓨터가 데이터를 빠르게 처리하고 기억할 수 있도록 돕는 핵심 반도체를 만드는 회사예요.",
    ],
    "highlights": [
        {
            "title": "DRAM·NAND 메모리",
            "description": "DRAM은 데이터를 빠르게 읽고 쓰는 데 쓰이고, NAND는 전원이 꺼져도 데이터를 보관하는 저장장치에 활용돼요.",
        },
        {
            "title": "AI 서버용 고대역폭 메모리(HBM)",
            "description": "AI 가속기가 많은 데이터를 빠르게 처리하도록 돕는 HBM 제품도 개발하고 있어요.",
        },
        {
            "title": "다양한 고객 시장",
            "description": "데이터센터뿐 아니라 PC, 모바일 기기, 자동차 등에도 메모리와 저장 제품을 공급합니다.",
        },
    ],
}


def read_company_intro_preview(symbol):
    """Preview only for MU. Returns a factual narrative plus exact-sector peers."""
    if str(symbol or "").strip().upper() != "MU":
        return None
    dsn = os.environ.get("NEWS_DATABASE_URL", "").strip()
    if not dsn:
        raise RuntimeError("company_registry_unavailable")

    import psycopg
    with psycopg.connect(dsn, connect_timeout=4) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT display_name, sector FROM public.market_instruments
                   WHERE market='US' AND symbol='MU' AND is_active IS DISTINCT FROM FALSE
                   LIMIT 1"""
            )
            target = cur.fetchone()
            if not target or not target[1]:
                raise RuntimeError("company_sector_not_found")
            name, sector = target
            cur.execute(
                """SELECT symbol, display_name FROM public.market_instruments
                   WHERE market='US' AND sector=%s AND symbol<>'MU'
                     AND is_active IS DISTINCT FROM FALSE
                   ORDER BY symbol LIMIT 20""",
                (sector,),
            )
            peers = [
                {"symbol": str(row[0]), "name": str(row[1])}
                for row in cur.fetchall()
            ]
    return {
        "symbol": "MU",
        "name": str(name),
        "paragraphs": MICRON_INTRO["paragraphs"],
        "highlights": MICRON_INTRO["highlights"],
        "related": peers,
        "source_url": MICRON_SOURCE,
        "related_basis": "키움 종목 업종 분류와 일치하는 기존 DB 종목",
    }
