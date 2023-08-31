# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2023 Virtual Cable S.L.U.
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
import dataclasses
import enum
import re
import typing

from django.utils.translation import gettext_noop


class Tab(enum.StrEnum):
    ADVANCED = gettext_noop('Advanced')
    PARAMETERS = gettext_noop('Parameters')
    CREDENTIALS = gettext_noop('Credentials')
    TUNNEL = gettext_noop('Tunnel')
    DISPLAY = gettext_noop('Display')
    MFA = gettext_noop('MFA')

    @staticmethod
    def fromStr(value: typing.Optional[str]) -> typing.Union['Tab', str, None]:
        """Returns a Tab from a string
        If value is not a valid Tab, returns Tab.PARAMETERS

        Args:
            value (str): String to convert to Tab
        """
        if not value:
            return None
        try:
            return Tab(value)
        except ValueError:
            return value


class FieldType(enum.StrEnum):
    TEXT = 'text'
    TEXT_AUTOCOMPLETE = 'text-autocomplete'
    NUMERIC = 'numeric'
    PASSWORD = 'password'  # nosec: this is not a password
    HIDDEN = 'hidden'
    CHOICE = 'choice'
    MULTI_CHOICE = 'multichoice'
    EDITABLE_LIST = 'editlist'
    CHECKBOX = 'checkbox'
    IMAGE_CHOICE = 'imgchoice'
    IMAGE = 'image'
    DATE = 'date'
    INFO = 'internal-info'

    @staticmethod
    def fromStr(value: str) -> 'FieldType':
        """Returns a FieldType from a string
        If value is not a valid FieldType, returns FieldType.TEXT

        Args:
            value (str): String to convert to FieldType
        """
        try:
            return FieldType(value)
        except ValueError:
            return FieldType.TEXT


class FieldPatternType(enum.StrEnum):
    IPV4 = 'ipv4'
    IPV6 = 'ipv6'
    IP = 'ip'
    MAC = 'mac'
    URL = 'url'
    EMAIL = 'email'
    FQDN = 'fqdn'
    HOSTNAME = 'hostname'
    HOST = 'host'
    PATH = 'path'
    NONE = ''


class FillerType(typing.TypedDict):
    callbackName: str
    parameters: typing.List[str]
    function: typing.NotRequired[typing.Callable[..., typing.Any]]


class ChoiceType(typing.TypedDict):
    id: str
    text: str


ChoicesType = typing.Union[typing.Callable[[], typing.List[ChoiceType]], typing.List[ChoiceType]]


@dataclasses.dataclass
class FieldInfoType:
    length: int
    required: bool
    label: str
    default: typing.Union[typing.Callable[[], str], str]
    readonly: bool
    order: int
    tooltip: str
    value: typing.Union[typing.Callable[[], typing.Any], typing.Any]
    type: FieldType
    multiline: typing.Optional[int] = None
    pattern: typing.Union[FieldPatternType, 're.Pattern'] = FieldPatternType.NONE
    tab: typing.Union[Tab, str, None] = None
    choices: typing.Optional[ChoicesType] = None
    minValue: typing.Optional[int] = None
    maxValue: typing.Optional[int] = None
    fills: typing.Optional[FillerType] = None
    rows: typing.Optional[int] = None

    def asDict(self) -> typing.Dict[str, typing.Any]:
        """Returns a dict with all fields that are not None"""
        return {k: v for k, v in dataclasses.asdict(self).items() if v is not None}
