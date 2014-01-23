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

'''
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''
from __future__ import unicode_literals

from django.conf import settings
from Crypto.PublicKey import RSA
from OpenSSL import crypto
from Crypto.Random import atfork
import hashlib, array

import logging

logger = logging.getLogger(__name__)

# To generate an rsa key, first we need the crypt module
# next, we do:
# from Crypto.PublicKey import RSA
# import os
# RSA.generate(1024, os.urandom).exportKey()

class CryptoManager(object):
    CODEC = 'base64' 
    
    instance = None
    
    def __init__(self):
        self._rsa = RSA.importKey(settings.RSA_KEY)
    
    @staticmethod
    def manager():
        if CryptoManager.instance is None:
            CryptoManager.instance = CryptoManager()
        return CryptoManager.instance
    
    def encrypt(self, string):
        atfork()
        return self._rsa.encrypt(string.encode('utf-8'), '')[0].encode(CryptoManager.CODEC)
    
    def decrypt(self, string):
        try:
            atfork()
            return self._rsa.decrypt(string.decode(CryptoManager.CODEC)).encode('utf-8')
        except:
            logger.exception('Decripting')
            return 'decript error'
    
    def xor(self, s1, s2):
        s1, s2 = s1.encode('utf-8'), s2.encode('utf-8')
        mult = (len(s1)/len(s2)) + 1
        s1 = array.array(b'B', s1)
        s2 = array.array(b'B', s2 * mult)
        return array.array(b'B', (s1[i] ^ s2[i] for i in range(len(s1)))).tostring()        
    
    def loadPrivateKey(self, rsaKey):
        try:
            pk = RSA.importKey(rsaKey)
        except Exception as e:
            raise e
        return pk
    
    def loadCertificate(self,certificate):
        try:
            cert = crypto.load_certificate(crypto.FILETYPE_PEM, certificate)
        except crypto.Error as e:
            raise Exception(e.message[0][2])
        return cert 

    def certificateString(self, certificate):
        return certificate.replace('-----BEGIN CERTIFICATE-----', '').replace('-----END CERTIFICATE-----', '').replace('\n', '')
            
    
    def hash(self, string):
        if string is '' or string is None:
            return ''
        return hashlib.sha1(string).hexdigest()
