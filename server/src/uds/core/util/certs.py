import secrets
import random
from datetime import datetime, timedelta
import ipaddress
import typing

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

def selfSignedCert(ip: str) -> typing.Tuple[str, str, str]:
    key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend(),
        )
    # Create a random password for private key
    password = secrets.token_urlsafe(32)

    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, ip)])
    san = x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address(ip))])

    basic_contraints = x509.BasicConstraints(ca=True, path_length=0)
    now = datetime.utcnow()
    cert = (
        x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)  # self signed
            .public_key(key.public_key())
            .serial_number(random.SystemRandom().randint(0, 1<<64))
            .not_valid_before(now)
            .not_valid_after(now + timedelta(days=10*365))
            .add_extension(basic_contraints, False)
            .add_extension(san, False)
            .sign(key, hashes.SHA256(), default_backend())
    )
    
    return (
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.BestAvailableEncryption(password.encode())
        ).decode(),
        cert.public_bytes(encoding=serialization.Encoding.PEM).decode(),
        password
    )
