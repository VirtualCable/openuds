import base64
import argparse

from Crypto.Hash import SHA256
from Crypto.Signature import PKCS1_v1_5
from Crypto.PublicKey import RSA

parser = argparse.ArgumentParser("sign.py")
parser.add_argument("file", nargs='?', const="")
args = parser.parse_args()
digest = SHA256.new()
script = open(args.file, 'r').read()
digest.update(script.encode('utf-8'))

# Load your private key
with open("private_key.pem", "r") as myfile:
    private_key = RSA.importKey(myfile.read())

# Sign the script
signer = PKCS1_v1_5.new(private_key)
sig = signer.sign(digest)

print(base64.b64encode(sig).decode('utf-8'))