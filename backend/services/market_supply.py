import re

from .market_levels import format_shares
from ..providers.market_supply import fetch_kr_supply_rows, fetch_us_option_rows


def fetch_kr_supply_summary(code_six):
    """최근 5개 수급 원천 행을 외국인/기관/개인 순매수로 가공한다."""
    rows = fetch_kr_supply_rows(code_six)
    if not rows:
        return None, None, None, 0

    sum_foreign = 0
    sum_inst = 0
    sum_indiv = 0
    valid_days = 0

    for row in rows[:5]:
        frgn = row.get("foreignerPureBuyQuant") or 0
        insti = row.get("organPureBuyQuant") or row.get("institutionPureBuyQuant") or 0
        indiv = row.get("individualPureBuyQuant") or 0

        sum_foreign += int(str(frgn).replace(",", ""))
        sum_inst += int(str(insti).replace(",", ""))
        sum_indiv += int(str(indiv).replace(",", ""))
        valid_days += 1

    if sum_indiv == 0 and (sum_foreign != 0 or sum_inst != 0):
        sum_indiv = -(sum_foreign + sum_inst)

    return sum_foreign, sum_inst, sum_indiv, valid_days


def build_kr_supply_content(foreign_5d, institution_5d, individual_5d, valid_days):
    if foreign_5d is None or institution_5d is None or valid_days <= 0:
        return ""

    tag_line = (
        f"#외국인 {format_shares(foreign_5d)} "
        f"#기관 {format_shares(institution_5d)} "
        f"#개인 {format_shares(individual_5d)}"
    )

    if foreign_5d > 0 and institution_5d > 0:
        return f"{tag_line}\n\n최근 5일 외놈 기관 쌍끌이 무엇…\n괜히 기분 좋아짐."
    if foreign_5d < 0 and institution_5d < 0:
        return f"{tag_line}\n\n최근 5일 외놈 기관 다 빠지네\n다들 조용히 눈치 보는중."
    if foreign_5d > 0:
        return f"{tag_line}\n\n최근 5일간 기관은 쉬고 외놈 혼자 열일 중\n수급 폼 미쳤다ㅋㅋ"
    if institution_5d > 0:
        return f"{tag_line}\n\n최근 5일 외인은 조용한데 기관이 열일하네\n수급 팝콘 각."
    return f"{tag_line}\n\n최근 5일 수급 완전 핑퐁 게임\n팽팽한 눈치 싸움."


def fetch_us_options_volume(ticker_symbol):
    rows, option_error = fetch_us_option_rows(ticker_symbol)
    call_vol = 0
    put_vol = 0

    for row in rows:
        if not isinstance(row, dict):
            continue
        options = row.get("options") or []
        if isinstance(options, dict):
            options = [options]

        for opt in options:
            if not isinstance(opt, dict):
                continue
            contract = str(
                opt.get("option")
                or opt.get("contractSymbol")
                or opt.get("symbol")
                or ""
            ).upper()
            volume = opt.get("volume", 0)
            if isinstance(volume, str):
                volume = volume.replace(",", "").strip()
            try:
                volume = int(float(volume or 0))
            except Exception:
                volume = 0

            side = ""
            match = re.search(r"\d{6}([CP])", contract) if contract else None
            if match:
                side = match.group(1)
            else:
                side = str(opt.get("type") or opt.get("optionType") or "").upper()

            if side in ("C", "CALL"):
                call_vol += volume
            elif side in ("P", "PUT"):
                put_vol += volume

    print(f"[미국 옵션] {str(ticker_symbol).upper().strip()} / CALL={call_vol} PUT={put_vol}")
    return call_vol, put_vol, option_error


def build_us_options_content(ticker_symbol, call_vol, put_vol, option_error):
    if call_vol > 0:
        pc_ratio = put_vol / call_vol
        c_str = f"{call_vol/10000:.1f}만건" if call_vol >= 10000 else f"{call_vol:,}건"
        p_str = f"{put_vol/10000:.1f}만건" if put_vol >= 10000 else f"{put_vol:,}건"
        tag_line = f"#콜 {c_str}   #풋 {p_str}   #비율 {pc_ratio:.2f}"
        if pc_ratio <= 0.7:
            return (
                f"{tag_line}\n\nCBOE Options Volume\n\n"
                "현재 옵션 거래량이 상방 쪽으로 기울어 있어!\n"
                "콜옵션 거래량이 풋옵션보다 많아 상승 쪽 베팅이 상대적으로 강한 구간이야."
            )
        if pc_ratio >= 1.1:
            return (
                f"{tag_line}\n\nCBOE Options Volume\n\n"
                "현재 옵션 거래량이 하방 쪽으로 기울어 있어!\n"
                "풋옵션 거래량이 콜옵션을 넘어 하락 방어 수요가 상대적으로 강한 구간이야."
            )
        return (
            f"{tag_line}\n\nCBOE Options Volume\n\n"
            "현재 옵션 시장이 팽팽하게 눈치싸움 중이야.\n"
            "콜과 풋 거래량이 크게 벌어지지 않아 방향성을 조금 더 확인할 필요가 있어."
        )
    if option_error:
        return f"{ticker_symbol} 조회 실패 HTTP {option_error}"
    return f"{ticker_symbol} 조회 성공 거래량 0"
