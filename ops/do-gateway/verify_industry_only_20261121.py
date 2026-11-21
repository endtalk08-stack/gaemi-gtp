"""Read-only verification of the 11-industry quote endpoint; no TOP20 calls."""
import http.client
import json
import ssl
from pathlib import Path

CERT = Path("/var/lib/gaemigtp-news/quotes-origin.crt")
HOST = "quotes.gaemigtp.com"
PATH = "/market/us-industries?include_stocks=1&view=heatmap"

def main():
    result = {}
    connection = http.client.HTTPSConnection("127.0.0.1", 443, context=ssl._create_unverified_context(), timeout=20)
    try:
        connection.connect()
        pem = CERT.read_text(encoding="ascii").split("-----END CERTIFICATE-----", 1)[0]
        expected = ssl.PEM_cert_to_DER_cert(pem + "-----END CERTIFICATE-----")
        if connection.sock.getpeercert(binary_form=True) != expected:
            raise ssl.SSLError("local_quote_origin_certificate_mismatch")
        connection.request("GET", PATH, headers={"Host": HOST})
        response = connection.getresponse()
        result["http_status"] = response.status
        data = json.load(response)
        result.update({
            "ok": data.get("ok"),
            "view": data.get("view"),
            "heatmap_ready": data.get("heatmap_ready"),
            "heatmap_missing": data.get("heatmap_missing"),
            "total_groups": len(data.get("items", [])),
            "groups": [],
        })
        for row in data.get("items", []):
            stocks = row.get("stocks", []) if isinstance(row.get("stocks"), list) else []
            result["groups"].append({
                "key": row.get("key"),
                "name": row.get("name"),
                "mapping_status": row.get("mapping_status"),
                "stock_count": len(stocks),
                "stocks": [{
                    "symbol": stock.get("symbol"),
                    "price": stock.get("price"),
                    "change_pct": stock.get("change_pct"),
                    "quote_at": stock.get("quote_at"),
                } for stock in stocks],
            })
    except Exception as exc:
        result["error"] = type(exc).__name__
    finally:
        connection.close()
    print("INDUSTRY_ONLY_VERIFY=" + json.dumps(result, ensure_ascii=False, allow_nan=False), flush=True)

if __name__ == "__main__":
    main()
