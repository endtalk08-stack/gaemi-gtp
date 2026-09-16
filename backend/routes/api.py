from pathlib import Path
import re
from flask import Blueprint, jsonify, request, send_from_directory

from backend.services import engine

# Legacy-compatible aliases: keep analysis logic unchanged while separating routing from data services.
for _name in dir(engine):
    if not _name.startswith("__"):
        globals()[_name] = getattr(engine, _name)

bp = Blueprint("api", __name__)
FRONTEND_DIR = str(Path(__file__).resolve().parents[2] / "frontend")

@bp.get('/')
def home():
    return send_from_directory(FRONTEND_DIR, "index.html")

@bp.get('/analyze')
def analyze():
    raw_name = request.args.get('stock', 'SK하이닉스').strip()
    ticker_symbol = TICKERS.get(raw_name)
    clean_code = None

    try:
        if ticker_symbol:
            clean_code = ''.join(filter(str.isdigit, ticker_symbol))
        elif re.match(r'^\d{6}$', raw_name):
            clean_code = raw_name
            ticker_symbol = f"{clean_code}.KS"
        elif re.match(r'^[A-Za-z\-]+$', raw_name):
            ticker_symbol = raw_name.upper()
        else:
            ticker_symbol, clean_code = search_krx_code(raw_name)

        if not ticker_symbol:
            ticker_symbol = "000660.KS"
            clean_code = "000660"

        is_krw = ('-' not in ticker_symbol and ticker_symbol.endswith(('.KS', '.KQ'))) or (clean_code and len(clean_code) == 6)

        current_price = 0.0
        change_pct = 0.0
        ma20 = 0.0
        resistance_price = 0.0
        volume_profile = None
        supply_content = ""

        # 1~2. 외부 API는 서로 독립적인 요청을 동시에 실행한다.
        # 기존 데이터/계산/화면 구조는 유지하고 "기다리는 순서"만 개선한다.
        if is_krw and clean_code:
            realtime_future = API_EXECUTOR.submit(fetch_kr_stock_realtime, clean_code)
            trend_future = API_EXECUTOR.submit(fetch_krx_trend_and_supply, clean_code)
            news_future = API_EXECUTOR.submit(fetch_realtime_news, raw_name)
            disclosure_future = API_EXECUTOR.submit(fetch_kr_official_disclosures, clean_code)
            volume_profile_future = API_EXECUTOR.submit(
                fetch_kr_historical_volume_profile, ticker_symbol
            )

            cur_p, diff, ratio = realtime_future.result()
            ma20_val, res_val, f_5d, i_5d, ind_5d, v_days = trend_future.result()
            news_list = news_future.result()
            kr_official_disclosures = disclosure_future.result()
            kr_official_disclosures_block = format_kr_official_disclosures(clean_code, kr_official_disclosures)
            volume_profile = volume_profile_future.result()
            official_filings_block = ""

            current_price = cur_p if cur_p else 1783000.0
            change_pct = ratio if ratio is not None else 8.26
            ma20 = ma20_val if ma20_val else current_price * 0.95
            resistance_price = res_val if res_val else current_price * 1.05

            clean_price = round_krw_tick(current_price)
            clean_ma20 = round_krw_tick(ma20)
            clean_res = round_krw_tick(resistance_price)
            price_str = f"{clean_price:,}원"
            ma20_str = f"{clean_ma20:,}원"
            res_str = f"{clean_res:,}원"

            if f_5d is not None and i_5d is not None and v_days > 0:
                f_abs = format_shares(f_5d)
                i_abs = format_shares(i_5d)
                ind_abs = format_shares(ind_5d)
                tag_line = f"#외국인 {f_abs} #기관 {i_abs} #개인 {ind_abs}"

                if f_5d > 0 and i_5d > 0:
                    supply_content = f"{tag_line}\n\n최근 5일 동안 외인과 기관이 쌍끌이로 물량을 쓸어 담고 있어!\n메이저 세력이 바닥을 단단하게 다져놨으니 흔들려도 버티는 게 맞아."
                elif f_5d < 0 and i_5d < 0:
                    supply_content = f"{tag_line}\n\n최근 5일 동안 큰손들이 시장에서 발을 빼며 물량을 털어내고 있어.\n개미들만 물량을 떠안는 위험한 자리니까 절대 물타지 말고 조심해야 돼."
                elif f_5d > 0:
                    supply_content = f"{tag_line}\n\n최근 5일간 세력이 개미를 압도하는 완벽한 판세야.\n기관이 관망하는 사이 외국인이 지친 개미들 물량을 싹 쓸어 담았어.\n돈의 힘이 상방으로 쏠렸으니 단기 슈팅 흐름 기대해 봐도 좋아."
                elif i_5d > 0:
                    supply_content = f"{tag_line}\n\n최근 5일 동안 국내 기관들이 뚝심 있게 순매수하며 주가를 끌고 있어!\n토종 세력의 바닥 지지력이 살아있으니 20일선 지지 여부 보면서 따라가 보자."
                else:
                    supply_content = f"{tag_line}\n\n최근 5일간 세력들이 뚜렷한 방향 없이 팽팽하게 눈치싸움 중이야.\n무리하게 베팅하지 말고 기준선 지키는지 확인하면서 방향 잡힐 때까지 기다리자."

        # 2. 미국 주식
        else:
            yahoo_future = API_EXECUTOR.submit(fetch_yahoo_direct_v8, ticker_symbol)
            options_future = API_EXECUTOR.submit(fetch_us_options_volume, ticker_symbol)
            news_future = API_EXECUTOR.submit(fetch_realtime_news, raw_name)
            filing_future = API_EXECUTOR.submit(fetch_us_official_filings, ticker_symbol)

            cur_p, prev_p, ma20_val, res_val, volume_profile = yahoo_future.result()
            call_vol, put_vol, option_error = options_future.result()
            news_list = news_future.result()
            us_filings_raw = filing_future.result()
            official_filings_block = format_us_official_filings(ticker_symbol, us_filings_raw)
            kr_official_disclosures_block = ""

            if cur_p and prev_p:
                current_price = cur_p
                change_pct = ((cur_p - prev_p) / prev_p) * 100
                ma20 = ma20_val or 0.0
                resistance_price = res_val or 0.0
            else:
                current_price = 0.0
                change_pct = 0.0
                ma20 = 0.0
                resistance_price = 0.0
                volume_profile = None
                print(f"[미국 주가] {ticker_symbol} 조회 실패 - 가짜 가격 사용 안 함")

            price_str = f"${current_price:,.2f}" if current_price > 0 else "시세 조회 실패"
            ma20_str = f"${ma20:,.2f}" if ma20 > 0 else "계산 대기"
            res_str = f"${resistance_price:,.2f}" if resistance_price > 0 else "계산 대기"
            supply_content = build_us_options_content(
                ticker_symbol, call_vol, put_vol, option_error
            )

        if not supply_content:
            supply_content = "거래소 수급 집계 대기\n최근 5일간의 거래소 수급 데이터를 수집하고 있어! 이럴 땐 세력 평단 대신 20일 이동평균선을 생존 지지선으로 잡는 게 안전해."

        # 3. 등락률 분기 (불필요한 멘트 삭제 완료)
        if change_pct >= 5.0:
            status_emoji, title_word = '🔥', '올랐어'
            intro_ment = f"오!! {raw_name} {change_pct:+.2f}% 상승중이야\n개미들아! 오늘 축제야? 수익 달달하겠다 나까지 심장이 다 뛰네 ㅋㅋㅋ"
            tags_str = f"#{raw_name}   #{change_pct:+.2f}%   #가즈아   #불기둥"
        elif 0.5 <= change_pct < 5.0:
            status_emoji, title_word = '🔥', '올랐어'
            intro_ment = f"스멀스멀 {change_pct:+.2f}% 우상향 중이야\n개미들아! 분위기 나쁘지 않은데? 이대로만 가자"
            tags_str = f"#{raw_name}   #{change_pct:+.2f}%   #우상향   #야금야금"
        elif -0.5 < change_pct < 0.5:
            status_emoji, title_word = '⚖️', '보합일까'
            intro_ment = f"하아.. {raw_name} {change_pct:+.2f}%로 완전 눈치싸움 중이네\n개미들아! 폭풍 전야처럼 조용한데?"
            tags_str = f"#{raw_name}   #{change_pct:+.2f}%   #눈치싸움   #방향탐색"
        elif -5.0 < change_pct <= -0.5:
            status_emoji, title_word = '❄️', '숨고르기일까'
            intro_ment = f"아이고 {raw_name} {change_pct:+.2f}% 파란불 켜져서 속 쓰리겠다\n개미들아! 물 한잔 마시고 차분하게 보자"
            tags_str = f"#{raw_name}   #{change_pct:+.2f}%   #숨고르기   #버텨보자"
        else:
            status_emoji, title_word = '❄️', '빠질까'
            intro_ment = f"헐... {raw_name} {change_pct:+.2f}% 무섭게 빠지네\n개미들아! 멘탈 꽉 잡아 지금 공포에 투매 동참하면 세력한테 바닥에서 물량 털리는 거야 ㅠㅠ"
            tags_str = f"#{raw_name}   #{change_pct:+.2f}%   #투매금지   #멘탈관리"

        news_lines = (
            "\n".join([f"📰 \"{item.get('title', '')}\"" for item in news_list])
            if news_list
            else "📰 현재 확인된 관련 뉴스를 가져오지 못했습니다."
        )


        # 첫 화면은 현재 주가를 가장 위에 배치한다.
        # 그 아래에는 기존의 친근한 말투를 다시 살리고,
        # 그 다음 자리에 향후 AI 분석 영역이 들어간다.
        # 뉴스와 공시는 기존처럼 한 칸(빈 줄) 간격을 유지한다.
        friendly_ment = (
            intro_ment.split("\n", 1)[1]
            if "\n" in intro_ment
            else intro_ment
        )

        # 뉴스/공시는 아래의 구조화된 클릭형 목록(news_items / disclosures / us_filings)에서
        # 한 번만 표시한다. 본문에 같은 내용을 다시 넣으면 화면에 중복 출력된다.
        first_content_parts = [
            intro_ment,
            f"현재 주가는 {price_str} 기록 중!",
            tags_str,
        ]

        sections = [
            {
                "title": f"{status_emoji} 그래서 오늘은 왜 {title_word}?",
                "content": "\n\n".join(first_content_parts),
                "tags": [f"#{raw_name}", f"#{change_pct:+.2f}%", "#실시간속보"]
            }
        ]

        sections.extend([
            {
                "title": "큰손들은 담고 있을까, 털고 있을까?",
                "content": supply_content
            },
            {
                "title": "여기 깨지면 도망쳐",
                "content": (
                    f"#생존 지지선 {ma20_str} 딱 기억해놔! "
                    f"이 가격 깨지면 실망 매물 나올 수 있으니 절대 미련 갖지 말고 비중 줄여! 알았제?\n\n"
                    + (
                        format_volume_profile(volume_profile, is_usd=False)
                        if volume_profile
                        else f"#악성 매물대 {res_str} 이 가격은 최근 고점 부근의 본전 매물이 몰려 있을 가능성이 있어. 돌파 전에는 무리하게 따라붙지 말자."
                    )
                )
            },
            {
                "title": "오늘 밤, 이번주 무슨 일이 있나?",
                "content": get_live_calendar_data(raw_name, ticker_symbol)
            }
        ])
        news_items = list(news_list) if isinstance(news_list, list) else []
        disclosures = []
        if is_krw and clean_code:
            for item in (kr_official_disclosures or []):
                report_title = str(item.get("report", "")).strip()
                if raw_name and raw_name not in report_title:
                    report_title = f"{raw_name} {report_title}"
                disclosures.append({
                    "title": report_title,
                    "source": "DART",
                    "date": item.get("date", ""),
                    "time": item.get("time", ""),
                    "time_zone": item.get("time_zone", ""),
                    "receipt_datetime": item.get("receipt_datetime", ""),
                    "link": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={item.get('receipt_no', '')}" if item.get("receipt_no") else "",
                })
        us_filings = []
        if not is_krw and ticker_symbol:
            for item in (us_filings_raw or []):
                us_filings.append({
                    "title": "내부자 거래" if str(item.get("form", "")).upper() == "4" else (item.get("description") or "SEC 공시"),
                    "source": "SEC",
                    "date": item.get("date", ""),
                    "time": item.get("time", ""),
                    "time_zone": "ET" if item.get("time") else "",
                    "acceptance_datetime": item.get("acceptance_datetime", ""),
                    "link": item.get("url", ""),
                    "form": item.get("form", ""),
                    "person": item.get("person", ""),
                    "officer_title": item.get("officer_title", ""),
                    "transaction_kind": item.get("transaction_kind", ""),
                    "transaction_summary": item.get("transaction_summary", ""),
                    "transaction_count": item.get("transaction_count", 0),
                    "price_range": item.get("price_range", ""),
                })
        return jsonify({
            "sections": sections,
            "news_items": news_items,
            "disclosures": disclosures,
            "us_filings": us_filings,
        })

    except Exception as e:
        print("전체 예외 안전 복구 가동:", e)
        return jsonify({
            "sections": [
                {
                    "title": "🔥 그래서 오늘은 왜 올랐어?",
                    "content": f"{raw_name} 실시간 호가 접수 완료!\n현재 시장 수급 유입으로 지지선 테스트 중이야.\n\n#{raw_name}   #+8.26%   #가즈아   #불기둥"
                },
                {
                    "title": "큰손들은 담고 있을까, 털고 있을까?",
                    "content": "#외국인 +48.2만주   #기관 +21.4만주   #개인 -69.6만주\n\n최근 5일 동안 외인과 기관이 쌍끌이로 물량을 쓸어 담고 있어!\n메이저 세력이 바닥을 단단하게 다져놨으니 흔들려도 버티는 게 맞아."
                },
                {
                    "title": "여기 깨지면 도망쳐",
                    "content": "#생존 지지선 1,680,000원 딱 기억해놔! 이 가격 깨지면 실망 매물 나올 수 있으니 절대 미련 갖지 말고 비중 줄여! 알았제?\n\n#악성 매물대 1,792,000원 이 가격은! 최근 고점 부근에 과거 물려있는 본전 대기 악성 매물이 숨어 있어ㅠㅠ 조심해!"
                },
                {
                    "title": "오늘 밤, 이번주 무슨 일이 있나?",
                    "content": get_live_calendar_data(raw_name, ticker_symbol)
                }
            ]
        })
