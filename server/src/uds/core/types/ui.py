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
import typing
import enum
import dataclasses

from django.utils.translation import gettext_noop


class Tab(enum.StrEnum):
    ADVANCED = gettext_noop('Advanced')
    PARAMETERS = gettext_noop('Parameters')
    CREDENTIALS = gettext_noop('Credentials')
    TUNNEL = gettext_noop('Tunnel')
    DISPLAY = gettext_noop('Display')
    MFA = gettext_noop('MFA')


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


class FillerType(typing.TypedDict):
    callbackName: str
    function: typing.Callable[..., typing.Any]
    parameters: typing.List[str]


class ChoiceType(typing.TypedDict):
    id: str
    text: str


ChoicesType = typing.Union[typing.Callable[[], typing.List[ChoiceType]], typing.List[ChoiceType]]


class FieldDataType(typing.TypedDict):
    length: int
    required: bool
    label: str
    default: str
    rdonly: bool
    order: int
    tooltip: str
    value: typing.Any
    type: str
    multiline: typing.NotRequired[int]
    pattern: typing.NotRequired[str]
    tab: typing.NotRequired[str]
    choices: typing.NotRequired[ChoicesType]
    minValue: typing.NotRequired[int]
    maxValue: typing.NotRequired[int]
    fills: typing.NotRequired[FillerType]
    rows: typing.NotRequired[int]

@dataclasses.dataclass
class FieldInfoType:
    length: int
    required: bool
    label: str
    default: str
    rdonly: bool
    order: int
    tooltip: str
    value: typing.Any
    type: str
    multiline: typing.Optional[int] = None
    pattern: typing.Optional[str] = None
    tab: typing.Optional[str] = None
    choices: typing.Optional[ChoicesType] = None
    minValue: typing.Optional[int] = None
    maxValue: typing.Optional[int] = None
    fills: typing.Optional[FillerType] = None
    rows: typing.Optional[int] = None

    # Temporal methods to allow access to dataclass fields
    # using dict
    def __getitem__(
        self,
        key: typing.Literal[
            'lentgh',
            'required',
            'label',
            'default',
            'rdonly',
            'order',
            'tooltip',
            'value',
            'type',
            'multiline',
            'pattern',
            'tab',
            'choices',
            'minValue',
            'maxValue',
            'fills',
            'rows',
        ],
    ) -> typing.Any:
        return getattr(self, key)

    def __setitem__(
        self,
        key: typing.Literal[
            'lentgh',
            'required',
            'label',
            'default',
            'rdonly',
            'order',
            'tooltip',
            'value',
            'type',
            'multiline',
            'pattern',
            'tab',
            'choices',
            'minValue',
            'maxValue',
            'fills',
            'rows',
        ],
        value: typing.Any,
    ) -> None:
        setattr(self, key, value)
        
    def asDict(self) -> typing.Dict[str, typing.Any]:
        """Returns a dict with all fields that are not None
        """
        return {
            k: v
            for k, v in dataclasses.asdict(self).items()
            if v is not None
        }
