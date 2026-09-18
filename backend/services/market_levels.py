"""Volume-profile and price-level formatting helpers.

These helpers contain no network/UI state, so they are kept separate from
the main analysis orchestrator to make future data sources easier to add.
"""

import math

# 종목별 활성 매물대 상태. 현재가가 움직였다는 이유만으로 매물대가 순간 이동하지 않게 한다.
_VP_STATE = {}

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

        # 현재가를 기준으로 매물대를 매번 새로 선택하지 않는다.
        # 한 번 잡힌 생존/악성 매물대는 현재가가 그 사이에서 움직이는 동안 유지하고,
        # 실제로 상단/하단을 돌파(이탈)했을 때만 다음 구간으로 이동한다.
        zones_sorted = sorted(zones, key=lambda z: z["lower"])
        effective_price = float(current_price) if current_price is not None else rows[-1][2]
        state_key = str(state_key or "__default__")

        # 매물대 경계가 달라진 경우에만 상태를 초기화한다.
        zone_signature = tuple(
            (round(z["lower"], 8), round(z["upper"], 8))
            for z in zones_sorted
        )
        state = _VP_STATE.get(state_key)

        if not state or state.get("signature") != zone_signature:
            below_candidates = [i for i, z in enumerate(zones_sorted) if z["upper"] < effective_price]
            above_candidates = [i for i, z in enumerate(zones_sorted) if z["lower"] > effective_price]

            support_idx = below_candidates[-1] if below_candidates else None
            resistance_idx = above_candidates[0] if above_candidates else None

            # 시작 시 현재가가 매물대 내부에 있으면 그 구간의 양옆을 잡는다.
            if support_idx is None or resistance_idx is None:
                inside_idx = next(
                    (i for i, z in enumerate(zones_sorted)
                     if z["lower"] <= effective_price <= z["upper"]),
                    None
                )
                if inside_idx is not None:
                    if support_idx is None and inside_idx > 0:
                        support_idx = inside_idx - 1
                    if resistance_idx is None and inside_idx + 1 < len(zones_sorted):
                        resistance_idx = inside_idx + 1
                    # 양옆 매물대가 하나도 없는 끝 구간이면 해당 구간을 사용한다.
                    if support_idx is None:
                        support_idx = inside_idx
                    if resistance_idx is None:
                        resistance_idx = inside_idx

            state = {
                "signature": zone_signature,
                "support_idx": support_idx,
                "resistance_idx": resistance_idx,
            }
            _VP_STATE[state_key] = state
        else:
            support_idx = state.get("support_idx")
            resistance_idx = state.get("resistance_idx")

            # 악성 매물대 상단을 실제로 넘은 경우에만 다음 위 매물대로 이동한다.
            while resistance_idx is not None and resistance_idx < len(zones_sorted):
                if effective_price <= zones_sorted[resistance_idx]["upper"]:
                    break
                support_idx = resistance_idx
                resistance_idx += 1

            if resistance_idx is not None and resistance_idx >= len(zones_sorted):
                resistance_idx = None

            # 생존 매물대 하단을 실제로 깬 경우에만 다음 아래 매물대로 이동한다.
            while support_idx is not None and support_idx >= 0:
                if effective_price >= zones_sorted[support_idx]["lower"]:
                    break
                resistance_idx = support_idx
                support_idx -= 1

            if support_idx is not None and support_idx < 0:
                support_idx = None

            state["support_idx"] = support_idx
            state["resistance_idx"] = resistance_idx

        support = (
            zones_sorted[state.get("support_idx")]
            if state.get("support_idx") is not None
            and 0 <= state.get("support_idx") < len(zones_sorted)
            else None
        )
        resistance = (
            zones_sorted[state.get("resistance_idx")]
            if state.get("resistance_idx") is not None
            and 0 <= state.get("resistance_idx") < len(zones_sorted)
            else None
        )

        # 화면에는 POC를 노출하지 않는다. POC는 내부 계산값으로만 유지한다.
        return {
            "current_price": effective_price,
            "poc": levels[profile.index(peak)],
            "zones": zones_sorted,
            "above": above,
            "below": below,
            "inside": inside,
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

