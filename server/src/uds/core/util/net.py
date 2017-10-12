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
import re

# Test patters for networks
reCIDR = re.compile(r'^([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})/([0-9]{1,2})$')
reMask = re.compile(r'^([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})netmask([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})$')
re1Asterisk = re.compile(r'^([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\.\*$')
re2Asterisk = re.compile(r'^([0-9]{1,3})\.([0-9]{1,3})\.\*\.?\*?$')
re3Asterisk = re.compile(r'^([0-9]{1,3})\.\*\.?\*?\.?\*?$')
reRange = re.compile(r'^([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})-([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})$')
reHost = re.compile(r'^([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})$')


def ipToLong(ip):
    '''
    convert decimal dotted quad string to long integer
    '''
    try:
        hexn = ''.join(["%02X" % int(i) for i in ip.split('.')])
        return int(hexn, 16)
    except:
        return 0  # Invalid values will map to "0.0.0.0" --> 0


def longToIp(n):
    '''
    convert long int to dotted quad string
    '''
    try:
        d = 256 * 256 * 256
        q = []
        while d > 0:
            m, n = divmod(n, d)
            q.append(str(m))
            d /= 256

        return '.'.join(q)
    except:
        return '0.0.0.0'  # Invalid values will map to "0.0.0.0"


def networksFromString(strNets, allowMultipleNetworks=True):
    '''
    Parses the network from strings in this forms:
      - A.* (or A.*.* or A.*.*.*)
      - A.B.* (or A.B.*.* )
      - A.B.C.* (i.e. 192.168.0.*)
      - A.B.C.D/N (i.e. 192.168.0.0/24)
      - A.B.C.D netmask X.X.X.X (i.e. 192.168.0.0 netmask 255.255.255.0)
      - A.B.C.D - E.F.G.D (i.e. 192-168.0.0-192.168.0.255)
      - A.B.C.D
    If allowMultipleNetworks is True, it allows ',' and ';' separators (and, ofc, more than 1 network)
    Returns a list of networks tuples in the form [(start1, end1), (start2, end2) ...]
    '''

    inputString = strNets

    def check(*args):
        for n in args:
            if int(n) < 0 or int(n) > 255:
                raise Exception()

    def toNum(*args):
        start = 256 * 256 * 256
        val = 0
        for n in args:
            val += start * int(n)
            start /= 256
        return val

    def maskFromBits(nBits):
        v = 0
        for n in range(nBits):
            v |= 1 << (31 - n)
        return v

    if allowMultipleNetworks is True:
        res = []
        for strNet in re.split('[;,]', strNets):
            if strNet != '':
                res.append(networksFromString(strNet, False))
        return res

    strNets = strNets.replace(' ', '')

    if strNets == '*':
        return 0, 4294967295

    try:
        # Test patterns
        m = reCIDR.match(strNets)
        if m is not None:
            check(*m.groups())
            bits = int(m.group(5))
            if bits < 0 | bits > 32:
                raise Exception()
            val = toNum(*m.groups())
            bits = maskFromBits(bits)
            noBits = ~bits & 0xffffffff
            return val & bits, val | noBits

        m = reMask.match(strNets)
        if m is not None:
            check(*m.groups())
            val = toNum(*(m.groups()[0:4]))
            bits = toNum(*(m.groups()[4:8]))
            noBits = ~bits & 0xffffffff
            return val & bits, val | noBits

        m = reRange.match(strNets)
        if m is not None:
            check(*m.groups())
            val = toNum(*(m.groups()[0:4]))
            val2 = toNum(*(m.groups()[4:8]))
            if val2 < val:
                raise Exception()
            return val, val2

        m = reHost.match(strNets)
        if m is not None:
            check(*m.groups())
            val = toNum(*m.groups())
            return val, val

        for v in ((re1Asterisk, 3), (re2Asterisk, 2), (re3Asterisk, 1)):
            m = v[0].match(strNets)
            if m is not None:
                check(*m.groups())
                val = toNum(*(m.groups()[0:v[1] + 1]))
                bits = maskFromBits(v[1] * 8)
                noBits = ~bits & 0xffffffff
                return val & bits, val | noBits

        # No pattern recognized, invalid network
        raise Exception()
    except:
        raise ValueError(inputString)


def ipInNetwork(ip, network):
    if isinstance(ip, unicode) or isinstance(ip, str):
        ip = ipToLong(ip)
    if isinstance(network, unicode) or isinstance(network, str):
        network = networksFromString(network)

    for net in network:
        if net[0] <= ip <= net[1]:
            return True
    return False
