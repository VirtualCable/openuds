# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2021 Virtual Cable S.L.U.
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
#    * Neither the name of Virtual Cable S.L.U. nor the names of its contributors
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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import re

from .unique_id_generator import UniqueGenerator

logger = logging.getLogger(__name__)


class UniqueMacGenerator(UniqueGenerator):
    __slots__ = ('_macRange',)

    def __init__(self, owner: str) -> None:
        super().__init__(owner, '\tmac')

    def _to_int(self, mac: str) -> int:
        return int(mac.replace(':', ''), 16)

    def _to_mac_addr(self, seq: int) -> str:
        if seq == -1:  # No mor macs available
            return '00:00:00:00:00:00'
        return re.sub(r"(..)", r"\1:", f'{seq:012X}')[:-1]

    # Mac Generator rewrites the signature of parent class, so we need to redefine it here
    def get(self, mac_range: str) -> str:
        first_mac, last_mac = mac_range.split('-')
        return self._to_mac_addr(super()._get(self._to_int(first_mac), self._to_int(last_mac)))

    def transfer(self, seq: str, to_generator: 'UniqueMacGenerator') -> bool:
        return super()._transfer(self._to_int(seq), to_generator)

    def free(self, seq: str) -> None:
        super()._free(self._to_int(seq))

    # Release is inherited, no mod needed
