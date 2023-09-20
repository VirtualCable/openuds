# -*- coding: utf-8 -*-
#
# Copyright (c) 2023 Virtual Cable S.L.U.
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
import enum


class ServiceType(enum.StrEnum):
    VDI = 'VDI'
    VAPP = 'VAPP'

    def asStr(self) -> str:
        """Returns the service type as a string"""
        return str(self)


class ServicesCountingType(enum.IntEnum):
    # 0 -> Standard max count type, that is, count only "creating and running" instances
    # 1 -> Count all instances, including "waint for delete" and "deleting" ones
    STANDARD = 0
    CONSERVATIVE = 1

    @staticmethod
    def fromInt(value: int) -> 'ServicesCountingType':
        """Returns the MaxServiceCountingMethodType from an int
        If the int is not a valid value, returns STANDARD
        """
        try:
            return ServicesCountingType(value)
        except ValueError:
            return ServicesCountingType.STANDARD
        
    @staticmethod
    def fromStr(value: str) -> 'ServicesCountingType':
        """Returns the MaxServiceCountingMethodType from an str
        If the str is not a valid value, returns STANDARD
        """
        try:
            return ServicesCountingType[value]
        except KeyError:
            return ServicesCountingType.STANDARD