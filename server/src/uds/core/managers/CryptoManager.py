# -*- coding: utf-8 -*-

#
# Copyright (c) 2012 Virtual Cable S.L.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright notice,
#      this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright notice,
#      this list of conditions and the following disclaimer in the documentation
#      and/or other materials provided with the distribution.
#    * Neither the name of Virtual Cable S.L. nor the names of its contributors
#      may be used to endorse or promote products derived from this software
#      without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
from __future__ import unicode_literals

from django.conf import settings
from uds.core.util import encoders
from Crypto.PublicKey import RSA
from Crypto.Cipher import AES
from uds.core.util import encoders
from OpenSSL import crypto
from Crypto.Random import atfork
import hashlib
import array
import uuid
import struct
import datetime
import random
import string

import logging
import six

logger = logging.getLogger(__name__)

# To generate an rsa key, first we need the crypt module
# next, we do:
# from Crypto.PublicKey import RSA
# import os
# RSA.generate(1024, os.urandom).exportKey()


class CryptoManager(object):
    instance = None

    def __init__(self):
        self._rsa = RSA.importKey(settings.RSA_KEY)
        self._namespace = uuid.UUID('627a37a5-e8db-431a-b783-73f7d20b4934')
        self._counter = 0

    @staticmethod
    def AESKey(key, length):
        if isinstance(key, six.text_type):
            key = key.encode('utf8')

        while len(key) < length:
            key += key  # Dup key

        kl = [ord(v) for v in key]
        pos = 0
        while len(kl) > length:
            kl[pos] ^= kl[length]
            pos = (pos + 1) % length
            del kl[length]

        return b''.join([chr(v) for v in kl])

    @staticmethod
    def manager():
        if CryptoManager.instance is None:
            CryptoManager.instance = CryptoManager()
        return CryptoManager.instance

    def encrypt(self, value):
        if isinstance(value, six.text_type):
            value = value.encode('utf-8')

        atfork()
        return encoders.encode((self._rsa.encrypt(value, six.b(''))[0]), 'base64', asText=True)

    def decrypt(self, value):
        if isinstance(value, six.text_type):
            value = value.encode('utf-8')
        # import inspect
        try:
            atfork()
            return six.text_type(self._rsa.decrypt(encoders.decode(value, 'base64')).decode('utf-8'))
        except Exception:
            logger.exception('Decripting: {0}'.format(value))
            # logger.error(inspect.stack())
            return 'decript error'

    def AESCrypt(self, text, key, base64=False):
        # First, match key to 16 bytes. If key is over 16, create a new one based on key of 16 bytes length
        cipher = AES.new(CryptoManager.AESKey(key, 16), AES.MODE_CBC, 'udsinitvectoruds')
        rndStr = self.randomString(cipher.block_size)
        paddedLength = ((len(text) + 4 + 15) // 16) * 16
        toEncode = struct.pack('>i', len(text)) + text + rndStr[:paddedLength - len(text) - 4]
        encoded = cipher.encrypt(toEncode)
        if hex:
            return encoders.encode(encoded, 'base64', True)

        return encoded

    def AESDecrypt(self, text, key, base64=False):
        if base64:
            text = encoders.decode(text, 'base64')

        cipher = AES.new(CryptoManager.AESKey(key, 16), AES.MODE_CBC, 'udsinitvectoruds')
        toDecode = cipher.decrypt(text)
        return toDecode[4:4 + struct.unpack('>i', toDecode[:4])[0]]

        return

    def xor(self, s1, s2):
        if isinstance(s1, six.text_type):
            s1 = s1.encode('utf-8')
        if isinstance(s2, six.text_type):
            s2 = s2.encode('utf-8')
        mult = int(len(s1) / len(s2)) + 1
        s1 = array.array('B', s1)
        s2 = array.array('B', s2 * mult)
        # We must return bynary in xor, because result is in fact binary
        return array.array('B', (s1[i] ^ s2[i] for i in range(len(s1)))).tostring()

    def symCrypt(self, text, key):
        return self.xor(text, key)

    def symDecrpyt(self, cryptText, key):
        return self.xor(cryptText, key).decode('utf-8')

    def loadPrivateKey(self, rsaKey):
        try:
            pk = RSA.importKey(rsaKey)
        except Exception as e:
            raise e
        return pk

    def loadCertificate(self, certificate):
        try:
            cert = crypto.load_certificate(crypto.FILETYPE_PEM, certificate)
        except crypto.Error as e:
            raise Exception(e.message[0][2])
        return cert

    def certificateString(self, certificate):
        return certificate.replace('-----BEGIN CERTIFICATE-----', '').replace('-----END CERTIFICATE-----', '').replace('\n', '')

    def hash(self, value):
        if isinstance(value, six.text_type):
            value = value.encode('utf-8')

        if value is '' or value is None:
            return ''

        return six.text_type(hashlib.sha1(value).hexdigest())

    def uuid(self, obj=None):
        """
        Generates an uuid from obj. (lower case)
        If obj is None, returns an uuid based on current datetime + counter
        """
        if obj is None:
            obj = self.randomString()
            self._counter += 1
        elif isinstance(obj, six.binary_type):
            obj = obj.decode('utf8')  # To binary
        else:
            obj = '{}'.format(obj)

        return six.text_type(uuid.uuid5(self._namespace, obj)).lower()  # I believe uuid returns a lowercase uuid always, but in case... :)

    def randomString(self, length=40):
        return ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(length))
