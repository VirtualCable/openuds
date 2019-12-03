import secrets
import random
import typing

from OpenSSL import crypto

def selfSignedCert(ip: str) -> typing.Tuple[str, str, str]:
    # create a key pair
    keyPair = crypto.PKey()
    keyPair.generate_key(crypto.TYPE_RSA, 2048)

    # create a self-signed cert
    cert = crypto.X509()
    cert.get_subject().C = "ES"
    cert.get_subject().ST = "Madrid"
    cert.get_subject().L = "Madrid"
    cert.get_subject().O = "UDS Cert"
    cert.get_subject().OU = "UDS Cert"
    cert.get_subject().CN = ip
    cert.get_subject().subjectAltName = ip
    cert.set_serial_number(random.SystemRandom().randint(0, 2<<32))  # Random serial, don't matter
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(10*365*24*60*60)
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(keyPair)
    cert.sign(keyPair, 'sha256')

    # Create a random password for private key
    password = secrets.token_urlsafe(32)

    return (
        crypto.dump_privatekey(crypto.FILETYPE_PEM, keyPair, cipher='blowfish',  passphrase=password.encode()).decode(),
        crypto.dump_certificate(crypto.FILETYPE_PEM, cert).decode(),
        password
    )
