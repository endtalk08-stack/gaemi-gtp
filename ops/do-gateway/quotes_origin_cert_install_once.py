"""Install only the PUBLIC Cloudflare origin certificate; private key stays on DO."""
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
import os
certificate="-----BEGIN CERTIFICATE-----\nMIIDGzCCAsGgAwIBAgIUJg6ilrOcjacn4Hx+ObGOzp0jU9QwCgYIKoZIzj0EAwIw\ngY8xCzAJBgNVBAYTAlVTMRMwEQYDVQQIEwpDYWxpZm9ybmlhMRYwFAYDVQQHEw1T\nYW4gRnJhbmNpc2NvMRkwFwYDVQQKExBDbG91ZEZsYXJlLCBJbmMuMTgwNgYDVQQL\nEy9DbG91ZEZsYXJlIE9yaWdpbiBTU0wgRUNDIENlcnRpZmljYXRlIEF1dGhvcml0\neTAeFw0yNjExMDkyMTU2MDBaFw0yNzExMDkyMTU2MDBaMGIxGTAXBgNVBAoTEENs\nb3VkRmxhcmUsIEluYy4xHTAbBgNVBAsTFENsb3VkRmxhcmUgT3JpZ2luIENBMSYw\nJAYDVQQDEx1DbG91ZEZsYXJlIE9yaWdpbiBDZXJ0aWZpY2F0ZTBZMBMGByqGSM49\nAgEGCCqGSM49AwEHA0IABBX/jGGiR9dmsA+FmcBC5lNu4vkub/jWhpNAaK49lU2Z\nEwDeY9aPhIHWKna3LyJORuo+fvF8B9VEqJbdX9HeJT6jggElMIIBITAOBgNVHQ8B\nAf8EBAMCBaAwHQYDVR0lBBYwFAYIKwYBBQUHAwIGCCsGAQUFBwMBMAwGA1UdEwEB\n/wQCMAAwHQYDVR0OBBYEFGGUlpp+GbRef6dBWcHEuMkJn6f9MB8GA1UdIwQYMBaA\nFIUwXTsqcNTt1ZJnB/3rObQaDjinMEQGCCsGAQUFBwEBBDgwNjA0BggrBgEFBQcw\nAYYoaHR0cDovL29jc3AuY2xvdWRmbGFyZS5jb20vb3JpZ2luX2VjY19jYTAeBgNV\nHREEFzAVghNxdW90ZXMuZ2FlbWlndHAuY29tMDwGA1UdHwQ1MDMwMaAvoC2GK2h0\ndHA6Ly9jcmwuY2xvdWRmbGFyZS5jb20vb3JpZ2luX2VjY19jYS5jcmwwCgYIKoZI\nzj0EAwIDSAAwRQIgBdrAXJxQOmYGABEikZS40G4XvWD0TpN6G+s1LJvaDRgCIQDN\nzoNaZH62gBo0ehMIz7p5Pgp49+gXGMZiMS05k35AWQ==\n-----END CERTIFICATE-----\n"
directory=Path("/var/lib/gaemigtp-news")
key_path=directory/"quotes-origin.key"
cert_path=directory/"quotes-origin.crt"
if not key_path.is_file() or key_path.is_symlink() or cert_path.is_symlink():
    raise SystemExit("invalid_origin_cert_state")
key=serialization.load_pem_private_key(key_path.read_bytes(),password=None)
parsed=x509.load_pem_x509_certificate(certificate.encode())
if key.public_key().public_numbers()!=parsed.public_key().public_numbers():
    raise SystemExit("origin_certificate_key_mismatch")
if "quotes.gaemigtp.com" not in parsed.extensions.get_extension_for_class(
        x509.SubjectAlternativeName).value.get_values_for_type(x509.DNSName):
    raise SystemExit("origin_cert_hostname_mismatch")
fd=os.open(str(cert_path),os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
with os.fdopen(fd,"wb") as out:
    out.write(certificate.encode())
    out.flush()
    os.fsync(out.fileno())
print("GAEMI_ORIGIN_TLS_CERT_INSTALLED=quotes.gaemigtp.com")
