"""Price-move headlines for the US trading-value TOP20 (no AI, fixed sentences).

Every minute during the regular session (gaemigtp-us-move-news.timer) the live
Kiwoom change rates of the TOP20 are compared with the previous check:

  crossed +2/+5/+10%      -> "엔비디아가 상승률 5%를 돌파했어요"
  crossed -2/-5/-10%      -> "테슬라가 하락률 5%를 돌파했어요"
  back under +2% after 2% -> "엔비디아가 상승폭을 줄여 2% 아래로 내려왔어요"
  back above -2% after -2%-> "테슬라가 하락폭을 줄여 -2% 위로 회복했어요"
  sign change after ±1%   -> "애플이 하락 전환했어요" / "상승 전환했어요"
Sentences are 해요체 so they can be read aloud on broadcast.

Each event is published at most once per stock per day, with a 0.3%p margin so
a price hovering on a line does not repeat it. Output: R2
news/stocks/us/MOVEFEED.json (a key the deployed uploader already accepts).
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

from backend.haeyo import subject
from backend.us_news_ai_daily import RANKING_URL, upload_json, us_trading_day, read_state, write_state

NEW_YORK = ZoneInfo("America/New_York")
STATE_PATH = Path("/var/lib/gaemigtp-news/us-move-news-state.json")
OBJECT_KEY = "news/stocks/us/MOVEFEED.json"
LEVELS = (2.0, 5.0, 10.0)
MARGIN = 0.3
KEEP_ITEMS = 120


def live_top20(opener=None):
    """Live Kiwoom ranking only: a stale fallback file must never produce a move headline."""
    import ssl
    import urllib.request
    request = urllib.request.Request(RANKING_URL, headers={"Origin": "https://gaemigtp-main.pages.dev"})
    opener = opener or urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ssl._create_unverified_context()))
    with opener.open(request, timeout=20) as response:
        items = json.load(response).get("items") or []
    return [{"symbol": str(i.get("symbol") or "").upper(), "name": str(i.get("name") or "").strip(),
             "change_pct": i.get("change_pct")} for i in items[:20] if i.get("symbol") and i.get("name")]


def in_session(now):
    local = now.astimezone(NEW_YORK)
    return us_trading_day(now) is not None and dt.time(9, 31) <= local.time() < dt.time(16, 0)


def events(name, prev, cur, done):
    """Headlines for one stock between two checks. `done` holds today's fired event keys."""
    out = []
    who = subject(name)

    def fire(key, text):
        if key not in done:
            done.add(key)
            out.append((key, text))
    for level in LEVELS:
        if cur >= level and prev < level:
            fire("up%g" % level, "%s 상승률 %g%%를 돌파했어요" % (who, level))
        if cur <= -level and prev > -level:
            fire("down%g" % level, "%s 하락률 %g%%를 돌파했어요" % (who, level))
    first = LEVELS[0]
    if "up%g" % first in done and prev >= first and cur < first - MARGIN:
        fire("fade_up", "%s 상승폭을 줄여 %g%% 아래로 내려왔어요" % (who, first))
    if "down%g" % first in done and prev <= -first and cur > -first + MARGIN:
        fire("fade_down", "%s 하락폭을 줄여 -%g%% 위로 회복했어요" % (who, first))
    if prev >= 1.0 and cur < -MARGIN:
        fire("turn_down", "%s 하락 전환했어요" % who)
    if prev <= -1.0 and cur > MARGIN:
        fire("turn_up", "%s 상승 전환했어요" % who)
    return out


def run(now=None, *, top20=live_top20, upload=upload_json, state_path=STATE_PATH):
    now = now or dt.datetime.now(dt.timezone.utc)
    if not in_session(now):
        return {"status": "closed"}
    day = now.astimezone(NEW_YORK).date().isoformat()
    state = read_state(state_path)
    if state.get("day") != day:
        state = {"day": day, "last": {}, "fired": {}, "items": state.get("items") or []}
    new = []
    for stock in top20():
        symbol, pct = stock["symbol"], stock.get("change_pct")
        if type(pct) not in (int, float):
            continue
        prev = state["last"].get(symbol)
        state["last"][symbol] = pct
        if prev is None:
            continue          # first sight today: no move to report yet
        done = set(state["fired"].get(symbol, []))
        for key, text in events(stock["name"], prev, pct, done):
            new.append({"id": "%s-%s-%s" % (day.replace("-", ""), symbol, key), "symbol": symbol,
                        "title": text, "published_at": now.isoformat()})
        state["fired"][symbol] = sorted(done)
    if new:
        state["items"] = (new + state["items"])[:KEEP_ITEMS]
        upload({"ok": True, "generated_at": now.isoformat(), "items": state["items"]}, OBJECT_KEY)
        print("[us-move-news] published %s" % ", ".join(i["title"] for i in new), flush=True)
    write_state(state, state_path)
    return {"status": "published" if new else "unchanged", "new": len(new)}


def main():
    try:
        run()
    except Exception as exc:
        print("[us-move-news] failed=" + type(exc).__name__, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
