"""Read-only: which KIS REST call returns the KOSPI 200 futures / night futures last price (no orders)."""
import json, pathlib, urllib.error, urllib.parse, urllib.request
env = {}
for line in pathlib.Path("/var/lib/gaemigtp-news/kis.env").read_text().splitlines():
    if "=" in line:
        k, v = line.split("=", 1); env[k.strip()] = v.strip()
BASE = "https://openapi.koreainvestment.com:9443"
def call(req):
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.load(exc)
        except Exception:
            return exc.code, None
status, tok = call(urllib.request.Request(BASE + "/oauth2/tokenP", method="POST",
    data=json.dumps({"grant_type": "client_credentials", "appkey": env["KIS_APP_KEY"], "appsecret": env["KIS_APP_SECRET"]}).encode(),
    headers={"Content-Type": "application/json"}))
token = (tok or {}).get("access_token")
print("TOKEN status=%s %s" % (status, "ok" if token else (tok or {}).get("error_description")), flush=True)
if not token:
    raise SystemExit(1)
def price(mrkt, code, tr="FHMIF10000000"):
    q = urllib.parse.urlencode({"FID_COND_MRKT_DIV_CODE": mrkt, "FID_INPUT_ISCD": code})
    s, d = call(urllib.request.Request(BASE + "/uapi/domestic-futureoption/v1/quotations/inquire-price?" + q,
        headers={"authorization": "Bearer " + token, "appkey": env["KIS_APP_KEY"], "appsecret": env["KIS_APP_SECRET"],
                 "tr_id": tr, "custtype": "P", "Content-Type": "application/json"}))
    o = (d or {}).get("output1") or {}
    keep = {k: o.get(k) for k in ("hts_kor_isnm", "futs_prpr", "futs_prdy_ctrt", "futs_prdy_vrss", "futs_sdpr", "stck_bsop_date", "futs_last_tr_date") if o.get(k) not in (None, "")}
    print("PRICE mrkt=%s code=%s http=%s rt=%s msg=%s %s" % (mrkt, code, s, (d or {}).get("rt_cd"), (d or {}).get("msg1"), json.dumps(keep, ensure_ascii=False)), flush=True)
for mrkt in ("F", "CM", "JF"):
    for code in ("101W9000", "101W09", "101W12", "A01612"):
        price(mrkt, code)
