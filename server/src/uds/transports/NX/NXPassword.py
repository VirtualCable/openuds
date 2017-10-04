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
Created on Apr 20, 2015

@author: Adolfo Gómez, dkmaster at dkmon dot com

'''
from __future__ import unicode_literals

import six
import random


class NXPassword(object):
    # Encoding method extracted from nomachine web site:
    # http://www.nomachine.com/ar/view.php?ar_id=AR01C00125

    dummyString = "{{{{"
    numValidCharList = 85
    validCharList = [
        '!', '#', '$', '%', '&', '(', ')', '*', '+', '-',
        '.', '0', '1', '2', '3', '4', '5', '6', '7', '8',
        '9', ':', ';', '<', '>', '?', '@', 'A', 'B', 'C',
        'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M',
        'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W',
        'X', 'Y', 'Z', '[', ']', '_', 'a', 'b', 'c', 'd',
        'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n',
        'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x',
        'y', 'z', '{', '|', '}'
    ]

    @staticmethod
    def _encodePassword(p):
        sPass = ':'

        if p == '':
            return ''

        for i in range(len(p)):
            sPass += '{}:'.format(ord(p[i]) + i + 1)

        print sPass
        return sPass

    @staticmethod
    def _findCharInList(c):
        try:
            return NXPassword.validCharList.index(c)
        except ValueError:
            return -1

    @staticmethod
    def _getRandomValidCharFromList():
        # k = random.randint(0, NXPassword.numValidCharList)
        k = 0
        return NXPassword.validCharList[k]

    @staticmethod
    def scrambleString(s):
        if s is None or s == '':
            return ''

        _str = NXPassword._encodePassword(s)

        if len(_str) < 32:
            _str += NXPassword.dummyString

        password = _str[::-1]  # Reversed string

        if len(password) < 32:
            password += NXPassword.dummyString

        startChar = NXPassword._getRandomValidCharFromList()
        l = ord(startChar) + len(password) - 2

        pw = startChar

        for i1 in range(0, len(password)):
            j = NXPassword._findCharInList(password[i1])
            if j == -1:
                return s

            i = (j + l * (i1 + 2)) % NXPassword.numValidCharList
            pw += NXPassword.validCharList[i]

        pw += chr(ord(NXPassword._getRandomValidCharFromList()) + 2)

        return pw.replace('&', '&amp;').replace('<', '&lt;').replace('"', '&quot;').replace('\'', '&apos;')  # .replace('$', '\\$')
