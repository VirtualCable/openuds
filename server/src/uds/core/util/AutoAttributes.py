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
import pickle
import logging
import typing

from uds.core.serializable import Serializable
from uds.core.util import encoders

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


# noinspection PyMissingConstructor
class AutoAttributes(Serializable):
    """
    Easy creation of attributes to marshal & unmarshal at modules
    usage as base class (First class so yours inherits this "marshal" and "unmarshal"
    initialize at init with super(myclass,self).__init__(attr1=type, attr2=type, ...)
    or with declare(attr1=type,attr2=type,..)
    Access attrs as "self._attr1, self._attr2"
    """

    _dict: typing.Dict

    def __init__(self, **kwargs):
        super().__init__()
        self.dict = {}
        self.declare(**kwargs)

    def __getattribute__(self, name):
        if name.startswith('_') and name[1:] in self.dict:
            return self.dict[name[1:]].getValue()
        return object.__getattribute__(self, name)

    def __setattr__(self, name, value):
        if name.startswith('_') and name[1:] in self.dict:
            self.dict[name[1:]].setValue(value)
        else:
            object.__setattr__(self, name, value)

    def declare(self, **kwargs):
        d = {}
        for key, typ in kwargs.items():
            d[key] = Attribute(typ)
        self.dict = d

    def marshal(self) -> bytes:
        return typing.cast(bytes, encoders.encode(b'\2'.join([b'%s\1%s' % (k.encode('utf8'), pickle.dumps(v, protocol=0)) for k, v in self.dict.items()]), 'bz2'))

    def unmarshal(self, data: bytes):
        if not data:  # Can be empty
            return
        # We keep original data (maybe incomplete)
        try:
            data = typing.cast(bytes, encoders.decode(data, 'bz2'))
        except Exception:  # With old zip encoding
            data = typing.cast(bytes, encoders.decode(data, 'zip'))
        # logger.debug('DATA: %s', data)
        for pair in data.split(b'\2'):
            k, v = pair.split(b'\1')
            # logger.debug('k: %s  ---   v: %s', k, v)
            self.dict[k.decode('utf8')] = pickle.loads(v)

    def __str__(self):
        str_ = '<AutoAttribute '
        for k, v in self.dict.items():
            str_ += "%s (%s) = %s" % (k, v.getType(), v.getStrValue())
        return str_ + '>'
