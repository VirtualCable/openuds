import secrets
import random
import datetime
import tempfile
import ipaddress
import typing
import ssl
import os
import contextlib

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
    now = datetime.datetime.utcnow()
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)  # self signed, its Issuer DN must match its Subject DN.
        .public_key(key.public_key())
        .serial_number(random.SystemRandom().randint(0, 1 << 64))
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=10 * 365))
        .add_extension(basic_contraints, False)
        .add_extension(san, False)
        .sign(key, hashes.SHA256(), default_backend())
    )

    return (
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.BestAvailableEncryption(
                password.encode()
            ),
        ).decode(),
        cert.public_bytes(encoding=serialization.Encoding.PEM).decode(),
        password,
    )


def sslContext(ip: str) -> typing.Tuple[ssl.SSLContext, str, str]:
    """Returns an ssl context an the certificate & password for an ip

    Args:
        ip (str): Ip for subject name

    Returns:
        typing.Tuple[ssl.SSLContext, str, str]: ssl context, certificate file and password
    """
    # First, create server cert and key on temp dir
    tmpdir = tempfile.gettempdir()
    cert, key, password = selfSignedCert('127.0.0.1')
    cert_file = f'{tmpdir}/tmp_cert.pem'
    with open(cert_file, 'w') as f:
        f.write(key)
        f.write(cert)
    # Create SSL context
    ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_ctx.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1
    ssl_ctx.load_cert_chain(certfile=f'{tmpdir}/tmp_cert.pem', password=password)
    ssl_ctx.check_hostname = False
    ssl_ctx.set_ciphers('ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384')

    return ssl_ctx, cert_file, password

@contextlib.contextmanager
def ssl_context(ip: str) -> typing.Generator[typing.Tuple[ssl.SSLContext, str], None, None]:
    """Returns an ssl context for an ip

    Args:
        ip (str): Ip for subject name

    Returns:
        ssl.SSLContext: ssl context
    """
    # First, create server cert and key on temp dir
    ssl_ctx, cert_file, password = sslContext(ip)

    yield ssl_ctx, cert_file

    # Remove cert file
    os.remove(cert_file)
