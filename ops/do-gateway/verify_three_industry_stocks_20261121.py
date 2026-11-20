"""Read one production-origin heatmap response without running collection jobs."""
import http.client
import json
import ssl
from pathlib import Path

CERT = Path("/var/lib/gaemigtp-news/quotes-origin.crt")


def main():
    result = {}
    connection = http.client.HTTPSConnection("127.0.0.1", 443, context=ssl._create_unverified_context(), timeout=18)
    try:
        connection.connect()
        certificate = CERT.read_text(encoding="ascii").split("-----END CERTIFICATE-----", 1)[0]
        expected = ssl.PEM_cert_to_DER_cert(certificate + "-----END CERTIFICATE-----")
        if connection.sock.getpeercert(binary_form=True) != expected:
            raise ssl.SSLError("local_quote_origin_certificate_mismatch")
        connection.request("GET", "/market/us-industries?include_stocks=1&view=heatmap", headers={"Host": "quotes.gaemigtp.com"})
        response = connection.getresponse()
        result["http_status"] = response.status
        data = json.load(response)
        result.update(
            view=data.get("view"), heatmap_ready=data.get("heatmap_ready"),
            heatmap_missing=data.get("heatmap_missing"), error=data.get("error"),
            total_groups=len(data.get("items", [])),
            stocks_by_group={row["key"]: [stock["symbol"] for stock in row.get("stocks", [])]
                             for row in data.get("items", [])},
        )
        for row in data.get("items", []):
            if row.get("key") == "internet_platforms":
                result["platform"] = {
                    name: row.get(name) for name in (
                        "source", "fetched_at", "change_pct", "member_symbols", "mapping_status"
                    )
                }
                result["platform"]["leaders"] = [
                    {name: stock.get(name) for name in ("symbol", "market_cap_usd", "change_pct")}
                    for stock in row.get("stocks", [])
                ]
                break
    except (OSError, ValueError, http.client.HTTPException) as exc:
        result["probe_error"] = type(exc).__name__
    finally:
        connection.close()
    ranking_connection = http.client.HTTPConnection("127.0.0.1", 8765, timeout=5)
    try:
        ranking_connection.request("GET", "/market/trading-value?market=us")
        rank_response = ranking_connection.getresponse()
        result["top20_count"] = len(json.load(rank_response).get("items", []))
    except (OSError, ValueError, http.client.HTTPException) as exc:
        result["top20_error"] = type(exc).__name__
    finally:
        ranking_connection.close()
    print("THREE_INDUSTRY_STOCKS_RESULT=" + json.dumps(result, allow_nan=False), flush=True)


if __name__ == "__main__":
    main()
