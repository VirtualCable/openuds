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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import re

from .unique_id_generator import UniqueIDGenerator

logger = logging.getLogger(__name__)


class UniqueMacGenerator(UniqueIDGenerator):
    __slots__ = ('_macRange',)

    def __init__(self, owner: str) -> None:
        super().__init__('mac', owner, '\tmac')

    def _to_int(self, mac: str) -> int:
        return int(mac.replace(':', ''), 16)

    def _to_mac_addr(self, seq: int) -> str:
        if seq == -1:  # No mor macs available
            return '00:00:00:00:00:00'
        return re.sub(r"(..)", r"\1:", f'{seq:012X}')[:-1]

    # noinspection PyMethodOverriding
    def get(self, macRange: str) -> str:  # type: ignore  # pylint: disable=arguments-differ
        firstMac, lastMac = macRange.split('-')
        return self._to_mac_addr(super().get(self._to_int(firstMac), self._to_int(lastMac)))

    def transfer(self, mac: str, toUMgen: 'UniqueMacGenerator'):  # type: ignore  # pylint: disable=arguments-renamed
        super().transfer(self._to_int(mac), toUMgen)

    def free(self, mac: str) -> None:  # type: ignore  # pylint: disable=arguments-renamed
        super().free(self._to_int(mac))

    # Release is inherited, no mod needed
