"""One-time CSR for a Cloudflare-verified HTTPS origin; private key stays on DO."""
import os
from pathlib import Path
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

hostname = "quotes.gaemigtp.com"
directory = Path("/var/lib/gaemigtp-news")
key_path = directory / "quotes-origin.key"
if not directory.is_dir() or directory.is_symlink():
    raise SystemExit("invalid_cert_directory")
if key_path.exists() or key_path.is_symlink():
    raise SystemExit("existing_cert_key_abort")
key = ec.generate_private_key(ec.SECP256R1())
key_bytes = key.private_bytes(
    serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption())
fd = os.open(str(key_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "wb") as out:
    out.write(key_bytes)
    out.flush()
    os.fsync(out.fileno())
csr = (x509.CertificateSigningRequestBuilder()
       .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostname)]))
       .add_extension(x509.SubjectAlternativeName([x509.DNSName(hostname)]), critical=False)
       .sign(key, hashes.SHA256()))
print("GAEMI_QUOTE_CSR_BEGIN")
print(csr.public_bytes(serialization.Encoding.PEM).decode().strip())
print("GAEMI_QUOTE_CSR_END")
print("GAEMI_ORIGIN_PRIVATE_KEY_ON_DO_ONLY=1")
