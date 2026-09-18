"""Volume-profile and price-level formatting helpers.

These helpers contain no network/UI state, so they are kept separate from
the main analysis orchestrator to make future data sources easier to add.
"""

import math


def calculate_volume_profile_levels(highs, lows, closes, volumes, bins=24, current_price=None, state_key=None):
    """
    최근 60거래일 OHLCV를 가격 구간별로 묶어 거래량 집중 구간을 찾는다.
    일봉 데이터만 있으므로 각 봉의 거래량을 고가~저가 구간에 균등 배분하는
    '근사형 Volume Profile'이다. 실제 체결 틱 데이터라고 과장하지 않는다.
    """
    try:
        rows = []
        for h, l, c, v in zip(highs[-60:], lows[-60:], closes[-60:], volumes[-60:]):
            # Yahoo OHLCV에는 간헐적으로 None이 섞일 수 있다.
            # 하나의 잘못된 봉 때문에 전체 Volume Profile 계산을 실패시키지 않는다.
            if any(x is None for x in (h, l, c, v)):
                continue
            try:
                h, l, c, v = float(h), float(l), float(c), float(v)
            except (TypeError, ValueError):
                continue
            if all(math.isfinite(x) for x in (h, l, c, v)) and h > 0 and l > 0 and h >= l and c > 0 and v > 0:
                rows.append((h, l, c, v))

        if len(rows) < 20:
            return None

        min_price = min(x[1] for x in rows)
        max_price = max(x[0] for x in rows)
        # 호출자가 실시간 현재가를 넘겨주면 그 값을 사용한다.
        # 넘겨주지 않은 경우에만 마지막 완료 일봉 종가를 사용한다.
        if current_price is None:
            current_price = rows[-1][2]
        else:
            try:
                current_price = float(current_price)
            except (TypeError, ValueError):
                current_price = rows[-1][2]

        if max_price <= min_price:
            return None

        bin_size = (max_price - min_price) / bins
        profile = [0.0] * bins

        for high, low, close, volume in rows:
            start_bin = max(0, min(bins - 1, int((low - min_price) / bin_size)))
            end_bin = max(0, min(bins - 1, int((high - min_price) / bin_size)))
            count = max(1, end_bin - start_bin + 1)
            allocated = volume / count
            for idx in range(start_bin, end_bin + 1):
                profile[idx] += allocated

        peak = max(profile)
        if peak <= 0:
            return None

        levels = []
        for idx, volume in enumerate(profile):
            lower = min_price + idx * bin_size
            upper = lower + bin_size
            levels.append({
                "idx": idx,
                "lower": lower,
                "upper": upper,
                "center": (lower + upper) / 2,
                "volume": volume,
                "relative": volume / peak,
            })

        # POC의 55% 이상 거래량이면서 서로 붙어 있는 가격대를 하나의 집중구간으로 묶는다.
        strong = {x["idx"] for x in levels if x["relative"] >= 0.55}
        clusters = []
        for idx in sorted(strong):
            if not clusters or idx > clusters[-1][-1] + 1:
                clusters.append([idx])
            else:
                clusters[-1].append(idx)

        zones = []
        for cluster in clusters:
            items = [levels[i] for i in cluster]
            total_volume = sum(x["volume"] for x in items)
            center = (
                sum(x["center"] * x["volume"] for x in items) / total_volume
                if total_volume else items[len(items) // 2]["center"]
            )
            zones.append({
                "lower": items[0]["lower"],
                "upper": items[-1]["upper"],
                "center": center,
                "volume": total_volume,
                "strength": max(x["relative"] for x in items),
            })

        if not zones:
            poc = levels[profile.index(peak)]
            zones = [{
                "lower": poc["lower"],
                "upper": poc["upper"],
                "center": poc["center"],
                "volume": poc["volume"],
                "strength": poc["relative"],
            }]

        # 기존 계산 방식: 현재가를 기준으로 바로 위/아래의 매물대를 선택한다.
        # 현재가가 움직이면 그 시점의 위/아래 매물대를 다시 계산한다.
        above = sorted(
            [z for z in zones if z["lower"] > current_price],
            key=lambda z: z["lower"]
        )
        below = sorted(
            [z for z in zones if z["upper"] < current_price],
            key=lambda z: z["upper"],
            reverse=True
        )
        inside = [
            z for z in zones
            if z["lower"] <= current_price <= z["upper"]
        ]

        # 화면에는 POC를 노출하지 않는다. POC는 내부 계산값으로만 유지한다.
        return {
            "current_price": current_price,
            "poc": levels[profile.index(peak)],
            "zones": zones,
            "above": above[0] if above else None,
            "below": below[0] if below else None,
            "inside": inside[0] if inside else None,
            "days": len(rows),
        }
    except Exception as e:
        print(f"[Volume Profile] 계산 예외: {type(e).__name__}: {e}")
        return None

def format_volume_profile(profile, is_usd=True):
    if not profile:
        return ""

    inside = profile.get("inside")
    above = profile.get("above")
    below = profile.get("below")

    lines = []

    # 사용자 화면에는 최근 60거래일 가격+거래량 Volume Profile에서
    # 선택한 지지 1개와 저항 1개만 표시한다. POC는 내부 계산값으로만 유지한다.
    support_zone = below or inside
    if support_zone:
        support_price = support_zone.get("lower", support_zone.get("center"))
        if support_price:
            lines.append(f"생존 매물대 ${support_price:,.2f}" if is_usd else f"생존 매물대 {round_krw_tick(support_price):,}원")

    resistance_zone = above or inside
    if resistance_zone:
        resistance_price = resistance_zone.get("upper", resistance_zone.get("center"))
        if resistance_price:
            lines.append(f"악성 매물대 ${resistance_price:,.2f}" if is_usd else f"악성 매물대 {round_krw_tick(resistance_price):,}원")

    return "\n".join(lines)

def format_shares(n):
    if n is None: return "0주"
    sign = "+" if n > 0 else ""
    if abs(n) >= 10000:
        return f"{sign}{n / 10000:,.1f}만주"
    return f"{sign}{n:,}주"

def round_krw_tick(price):
    if price is None: return 0
    try:
        p = float(price)
        if math.isnan(p) or math.isinf(p) or p <= 0: return 0
        if p >= 500_000: return int(p // 1000) * 1000
        elif p >= 100_000: return int(p // 500) * 500
        elif p >= 50_000: return int(p // 100) * 100
        elif p >= 10_000: return int(p // 50) * 50
        else: return int(p // 10) * 10
    except Exception:
        return 0

