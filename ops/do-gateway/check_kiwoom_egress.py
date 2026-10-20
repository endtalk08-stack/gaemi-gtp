"""One-shot read-only DigitalOcean public egress IP check (no Kiwoom calls)."""
import ipaddress
import urllib.request

expected = ipaddress.IPv4Address("168.144.131.211")
try:
    req = urllib.request.Request("https://api.ipify.org", headers={"User-Agent": "gaemi-do-egress-check/1.0"})
    with urllib.request.urlopen(req, timeout=6) as res:
        actual = ipaddress.IPv4Address(res.read(64).decode("ascii").strip())
except Exception:
    print("DIGITALOCEAN_EGRESS_CHECK_FAILED")
else:
    print("DIGITALOCEAN_EGRESS_IP=" + str(actual))
    print("DIGITALOCEAN_EGRESS_MATCHES_KIWOOM_IP=" + str(actual == expected).lower())
