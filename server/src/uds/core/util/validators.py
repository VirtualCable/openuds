# -*- coding: utf-8 -*-

#
# Copyright (c) 2014-2019 Virtual Cable S.L.
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
import re
import logging
import typing

from uds.core.module import Module
from django.utils.translation import gettext as _


logger = logging.getLogger(__name__)


def validateNumeric(
        numericStr: str,
        minValue: typing.Optional[int] = None,
        maxValue: typing.Optional[int] = None,
        returnAsInteger: bool = True,
        fieldName: typing.Optional[str] = None
    ) -> typing.Union[str, int]:
    """
    Validates that a numeric value is valid
    :param numericStr: Numeric value to check (as string)
    :param minValue: If not None, min value that must be the numeric or exception is thrown
    :param maxValue: If not None, max value that must be the numeric or exception is thrown
    :param returnAsInteger: if True, returs value as integer (default), else returns as string
    :param fieldName: If present, the name of the field for "Raising" exceptions, defaults to "Numeric value"
    :return: Raises Module.Validation exception if is invalid, else return the value "fixed"
    """
    numericStr = numericStr.replace(' ', '')
    fieldName = fieldName or _('Numeric')

    try:
        numeric = int(numericStr)
        if minValue is not None and numeric < minValue:
            raise Module.ValidationException(_('{0} must be greater than or equal to {1}'.format(fieldName, minValue)))

        if maxValue is not None and numeric > maxValue:
            raise Module.ValidationException(_('{0} must be lower than or equal to {1}'.format(fieldName, maxValue)))

        numericStr = str(numeric)

    except ValueError:
        raise Module.ValidationException(_('{0} contains invalid characters').format(fieldName))

    if returnAsInteger:
        return int(numericStr)

    return numericStr


def validatePort(portStr: str, returnAsInteger: bool = True) -> typing.Union[str, int]:
    """
    Validates that a port number is valid
    :param portStr: port to validate, as string
    :param returnAsInteger: if True, returns value as integer, if not, as string
    :return: Raises Module.Validation exception if is invalid, else return the value "fixed"
    """
    return validateNumeric(portStr, minValue=0, maxValue=65535, returnAsInteger=returnAsInteger, fieldName='Port')


def validateTimeout(timeOutStr, returnAsInteger: bool = True) -> typing.Union[str, int]:
    """
    Validates that a timeout value is valid
    :param timeOutStr: timeout to validate
    :param returnAsInteger: if True, returns value as integer, if not, as string
    :return: Raises Module.Validation exception if is invalid, else return the value "fixed"
    """
    return validateNumeric(timeOutStr, minValue=0, returnAsInteger=returnAsInteger, fieldName='Timeout')


def validateMacRange(macRange: str) -> str:
    """
    Corrects mac range (uppercase, without spaces), and checks that is range is valid
    :param macRange: Range to fix
    :return: Raises Module.Validation exception if is invalid, else return the value "fixed"
    """
    # Removes white spaces and all to uppercase
    macRange = macRange.upper().replace(' ', '')

    macRE = re.compile(r'^([0-9A-F]{2}[:]){5}([0-9A-F]{2})$')  # In fact, it could be XX-XX-XX-XX-XX-XX, but we use - as range separator

    try:
        macRangeStart, macRangeEnd = macRange.split('-')

        if macRE.match(macRangeStart) is None or macRE.match(macRangeEnd) is None:
            raise Exception()
        if macRangeStart > macRangeEnd:
            raise Exception()
    except Exception:
        raise Module.ValidationException(_('Invalid mac range. Mac range must be in format XX:XX:XX:XX:XX:XX-XX:XX:XX:XX:XX:XX'))

    return macRange
