# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2025 Virtual Cable S.L.U.
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
from uds.core import types

class OrderCounter:
    """
    A simple counter that can be used to order elements in a list.
    It is used to ensure that the order of elements is consistent across different runs.
    """
    counter: int
    
    def __init__(self, value: int = 0):
        super().__init__()
        self.counter = value

    def next(self) -> int:
        """
        Returns the next value of the counter.
        """
        val = self.counter
        self.counter += 1
        return val

    def next_tab(self) -> int:
        """
        returns the next value that is divisible by 10.
        """
        self.counter = (self.counter // 10 + 1) * 10
        return self.counter

def _add_common(
    gui: types.ui.GuiElement,
    *,
    tab: types.ui.Tab | str | None = None,
    order: int | None = None,
    length: int | None = None,
    min_value: int | None = None,
    max_value: int | None = None,
    default: str | int | bool | None = None,
    required: bool | None = None,
    readonly: bool | None = None,
    tooltip: str | None = None,
) -> types.ui.GuiElement:
    """
    Adds common fields to the given GUI element.
    """
    if tab:
        gui['gui']['tab'] = tab
    if order is not None:
        gui['gui']['order'] = order
    if length is not None:
        gui['gui']['length'] = length
    if min_value is not None:
        gui['gui']['min_value'] = min_value
    if max_value is not None:
        gui['gui']['max_value'] = max_value
    if default is not None:
        gui['gui']['default'] = default
    if required is not None:
        gui['gui']['required'] = required
    if readonly is not None:
        gui['gui']['readonly'] = readonly
    
    gui['gui']['tooltip'] = tooltip or ''

    return gui

def hidden_field(
    order: int,
    name: str,
    *,
    default: str | int | bool | None = None,
    tab: types.ui.Tab | str | None = None,
) -> types.ui.GuiElement:
    """
    Creates a hidden field with the given parameters.
    """
    return _add_common(
        {
            'name': name,
            'gui': {
                'label': name,
                'type': types.ui.FieldType.HIDDEN,
                'order': order,
            },
        },
        tab=tab,
        order=order,
        default=default,
    )   


def info_field(
    order: int,
    name: str,
    *,
    default: str | int | bool | None = None,
) -> types.ui.GuiElement:
    """
    Creates an info field with the given parameters.
    """
    return _add_common(
        {
            'name': name,
            'gui': {
                'label': name,
                'type': types.ui.FieldType.INFO,
                'order': order,
            },
        },
        order=order,
        default=default,
    )

def text_field(
    order: int,
    name: str,
    label: str,
    *,
    tooltip: str = '',
    tab: types.ui.Tab | str | None = None,
    length: int | None = None,
    default: str | None = None,
    required: bool | None = None,
) -> types.ui.GuiElement:
    """
    Creates a text field with the given parameters.
    """
    return _add_common(
        {
            'name': name,
            'gui': {
                'label': label,
                'type': types.ui.FieldType.TEXT,
                'order': order,
            },
        },
        tab=tab,
        order=order,
        length=length,
        default=default,
        required=required,
        tooltip=tooltip,
    )


def choice_field(
    order: int,
    name: str,
    label: str,
    choices: list[types.ui.ChoiceItem],
    *,
    tooltip: str = '',
    tab: types.ui.Tab | str | None = None,
    default: str | None = None,
    readonly: bool = False,
) -> types.ui.GuiElement:
    """
    Creates a choice field with the given parameters.
    """
    return _add_common(
        {
            'name': name,
            'gui': {
                'label': label,
                'type': types.ui.FieldType.CHOICE,
                'choices': choices,
                'order': order,
            },
        },
        tab=tab,
        order=order,
        default=default,
        readonly=readonly,
        tooltip=tooltip,
    )


def multichoice_field(
    order: int,
    name: str,
    label: str,
    choices: list[types.ui.ChoiceItem],
    *,
    tooltip: str = '',
    tab: types.ui.Tab | str | None = None,
) -> types.ui.GuiElement:
    """
    Creates a multichoice field with the given parameters.
    """
    return _add_common(
        {
            'name': name,
            'gui': {
                'label': label,
                'type': types.ui.FieldType.MULTICHOICE,
                'choices': choices,
                'order': order,
            },
        },
        tab=tab,
        order=order,
        tooltip=tooltip,
    )


def numeric_field(
    order: int,
    name: str,
    label: str,
    *,
    tooltip: str = '',
    tab: types.ui.Tab | str | None = None,
    min_value: int | None = None,
    max_value: int | None = None,
    default: int | None = None,
) -> types.ui.GuiElement:
    """
    Creates a numeric field with the given parameters.
    """
    gui: types.ui.GuiDescription = {
        'label': label,
        'type': types.ui.FieldType.NUMERIC,
        'order': order,
    }
    return _add_common(
        {
            'name': name,
            'gui': gui,
        },
        tab=tab,
        order=order,
        min_value=min_value,
        max_value=max_value,
        default=default,
        tooltip=tooltip,
    )

def checkbox_field(
    order: int,
    name: str,
    label: str,
    *,
    tooltip: str = '',
    tab: types.ui.Tab | str | None = None,
    default: bool | None = None,
) -> types.ui.GuiElement:
    """
    Creates a checkbox field with the given parameters.
    """
    return _add_common(
        {
            'name': name,
            'gui': {
                'label': label,
                'type': types.ui.FieldType.CHECKBOX,
                'order': order,
            },
        },
        tab=tab,
        order=order,
        default=default,
        tooltip=tooltip,
    )


def image_field(
    order: int,
    name: str,
    label: str,
    *,
    tooltip: str = '',
    tab: types.ui.Tab | str | None = None,
    default: str | None = None,
) -> types.ui.GuiElement:
    """
    Creates an image field with the given parameters.
    """
    return _add_common(
        {
            'name': name,
            'gui': {
                'label': label,
                'type': types.ui.FieldType.IMAGECHOICE,
                'order': order,
            },
        },
        tab=tab,
        order=order,
        default=default,
        tooltip=tooltip,
    )


def image_choice_field(
    order: int,
    name: str,
    label: str,
    choices: list[types.ui.ChoiceItem],
    *,
    tooltip: str = '',
    tab: types.ui.Tab | str | None = None,
    default: str | None = None,
) -> types.ui.GuiElement:
    """
    Creates an image choice field with the given parameters.
    """
    return _add_common(
        {
            'name': name,
            'gui': {
                'label': label,
                'type': types.ui.FieldType.IMAGECHOICE,
                'choices': choices,
                'order': order,
            },
        },
        tab=tab,
        order=order,
        default=default,
        tooltip=tooltip,
    )
