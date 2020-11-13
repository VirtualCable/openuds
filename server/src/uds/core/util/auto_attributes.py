# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2019 Virtual Cable S.L.
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
import codecs
import pickle
import logging
import typing

from uds.core.serializable import Serializable

logger = logging.getLogger(__name__)


class Attribute:
    _type: typing.Type
    _value: typing.Optional[typing.Any]

    def __init__(self, theType: typing.Type, value: typing.Optional[typing.Any] = None):
        self._type = theType
        self.setValue(value)

    def getType(self):
        return self._type

    def getValue(self):
        return self._value

    def getStrValue(self):
        return str(self._value)

    def setValue(self, value: typing.Any):
        if value is None:
            self._value = self._type()
        else:
            self._value = self._type(value)


class AutoAttributes(Serializable):
    """
    Easy creation of attributes to marshal & unmarshal at modules
    usage as base class (First class so yours inherits this "marshal" and "unmarshal"
    initialize at init with super(myclass,self).__init__(attr1=type, attr2=type, ...)
    or with declare(attr1=type,attr2=type,..)
    Access attrs as "self._attr1, self._attr2"
    """

    attrs: typing.Dict

    def __init__(self, **kwargs):
        Serializable.__init__(self)
        self.attrs = {}
        self.declare(**kwargs)

    def __getattribute__(self, name):
        if name.startswith('_') and name[1:] in self.attrs:
            return self.attrs[name[1:]].getValue()
        return object.__getattribute__(self, name)

    def __setattr__(self, name, value):
        if name.startswith('_') and name[1:] in self.attrs:
            self.attrs[name[1:]].setValue(value)
        else:
            object.__setattr__(self, name, value)

    def declare(self, **kwargs):
        d = {}
        for key, typ in kwargs.items():
            d[key] = Attribute(typ)
        self.attrs = d

    def marshal(self) -> bytes:
        for k, v in self.attrs.items():
            logger.debug('Marshall Autoattributes: %s=%s', k, v.getValue())
        return codecs.encode(b'\2'.join([b'%s\1%s' % (k.encode('utf8'), pickle.dumps(v, protocol=0)) for k, v in self.attrs.items()]), 'bz2')

    def unmarshal(self, data: bytes) -> None:
        if not data:  # Can be empty
            return
        # We keep original data (maybe incomplete)
        try:
            data = codecs.decode(data, 'bz2')
        except Exception:  # With old zip encoding
            data = codecs.decode(data, 'zip')
        # logger.debug('DATA: %s', data)
        for pair in data.split(b'\2'):
            k, v = pair.split(b'\1')
            # logger.debug('k: %s  ---   v: %s', k, v)
            try:
                self.attrs[k.decode()] = pickle.loads(v)
            except Exception: # Old encoding on python2, set encoding for loading
                self.attrs[k.decode()] = pickle.loads(v, encoding='utf8')

        for k2, v2 in self.attrs.items():
            logger.debug('Marshall Autoattributes: %s=%s', k2, v2.getValue())

    def __str__(self) -> str:
        str_ = '<AutoAttribute '
        for k, v in self.attrs.items():
            str_ += "%s (%s) = %s" % (k, v.getType(), v.getStrValue())
        return str_ + '>'
