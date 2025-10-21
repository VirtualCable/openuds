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
import typing
import collections.abc

from django.utils.translation import gettext_noop

# Old Field name type
OldFieldNameType = typing.Union[str, list[str], None]


class Tab(enum.StrEnum):
    ADVANCED = gettext_noop('Advanced')
    PARAMETERS = gettext_noop('Parameters')
    CREDENTIALS = gettext_noop('Credentials')
    TUNNEL = gettext_noop('Tunnel')
    DISPLAY = gettext_noop('Display')
    MFA = gettext_noop('MFA')
    MACHINE = gettext_noop('Machine')
    CONFIG = gettext_noop('Config')
    ATTRIBUTES = gettext_noop('Attributes')

    @staticmethod
    def from_str(value: typing.Optional[str]) -> typing.Union['Tab', str, None]:
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
    MULTICHOICE = 'multichoice'
    EDITABLELIST = 'editlist'
    CHECKBOX = 'checkbox'
    IMAGECHOICE = 'imgchoice'
    DATE = 'date'
    INFO = 'internal-info'
    TAGLIST = 'taglist'

    @staticmethod
    def from_str(value: str) -> 'FieldType':
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


# Callbacks


class CallbackResultItem(typing.TypedDict):
    # {'name': 'datastore', 'choices': res}
    name: str
    choices: typing.List['ChoiceItem']


CallbackResultType = list[CallbackResultItem]


class Filler(typing.TypedDict):
    callback_name: typing.NotRequired[str]
    parameters: list[str]
    function: typing.NotRequired[collections.abc.Callable[..., CallbackResultType]]


# Choices


@dataclasses.dataclass
class ChoiceItem:
    id: 'str|int'
    text: str
    img: str | None = None  # Only for IMAGECHOICE

    def as_dict(self) -> dict[str, typing.Any]:
        data = {
            'id': self.id,
            'text': self.text,
        }
        if self.img:
            data['img'] = self.img
        return data


ChoicesType = typing.Union[
    collections.abc.Callable[[], collections.abc.Iterable[ChoiceItem]], collections.abc.Iterable[ChoiceItem]
]


# Field Info
@dataclasses.dataclass
class FieldInfo:
    label: str
    tooltip: str
    order: int
    type: FieldType
    field_name: str = ''
    old_field_name: OldFieldNameType = None
    readonly: bool | None = None
    value: collections.abc.Callable[[], typing.Any] | typing.Any | None = None
    default: collections.abc.Callable[[], str | int | bool] | str | int | bool | None = None
    required: bool | None = None
    length: int | None = None
    lines: int | None = None
    pattern: 'FieldPatternType | str | None' = None
    tab: Tab | str | None = None
    choices: ChoicesType | None = None
    min_value: int | None = None
    max_value: int | None = None
    fills: Filler | None = None
    rows: int | None = None

    def as_dict(self) -> dict[str, typing.Any]:
        """Returns a dict with all fields that are not None"""
        return {k: v for k, v in dataclasses.asdict(self).items() if v is not None}


@dataclasses.dataclass
class GuiElement:
    name: str
    gui: FieldInfo
    value: typing.Any | None = None

    def as_dict(self) -> dict[str, typing.Any]:
        """Returns a dict with all fields that are not None"""
        return {
            'name': self.name,
            'gui': self.gui.as_dict(),
            'value': self.value,
        }
