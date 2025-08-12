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
import typing
from uds.core import types
from django.utils.translation import gettext


class GuiBuilder:
    fields: list[types.ui.GuiElement]
    order: int = 0
    saved_tab: types.ui.Tab | str | None = None

    def __init__(
        self,
        order: int = 0,
    ) -> None:
        """
        Initializes the GuiBuilder with a starting order.
        """
        self.order = order
        self.fields = []

    def next(self) -> int:
        """
        Returns the next value of the counter.
        """
        val = self.order
        self.order += 1
        return val

    def next_tab(self) -> None:
        """
        returns the next value that is divisible by 10.
        """
        self.order = (self.order // 10 + 1) * 10

    def make_gui(
        self,
        name: str,
        type: types.ui.FieldType,
        *,
        label: str | None = None,
        tab: types.ui.Tab | str | None = None,
        order: int | None = None,
        length: int | None = None,
        min_value: int | None = None,
        max_value: int | None = None,
        default: str | int | bool | None = None,
        required: bool | None = None,
        readonly: bool | None = None,
        tooltip: str | None = None,
        choices: list[types.ui.ChoiceItem] | None = None,
    ) -> types.ui.GuiElement:
        """
        Adds common fields to the given GUI element.
        """
        gui_desk: types.ui.GuiDescription = {
            'type': type,
            'label': label or '',
            'order': self.next(),
        }
        tab = tab or self.saved_tab

        if tab:
            gui_desk['tab'] = tab

        if order is not None:
            gui_desk['order'] = order
        if length is not None:
            gui_desk['length'] = length
        if min_value is not None:
            gui_desk['min_value'] = min_value
        if max_value is not None:
            gui_desk['max_value'] = max_value
        if default is not None:
            gui_desk['default'] = default
        if required is not None:
            gui_desk['required'] = required
        if readonly is not None:
            gui_desk['readonly'] = readonly
        if choices is not None:
            gui_desk['choices'] = choices

        gui_desk['tooltip'] = tooltip or ''

        return {
            'name': name,
            'gui': gui_desk,
        }

    def new_tab(self, tab: types.ui.Tab | str | None = None) -> typing.Self:
        """
        Resets the order counter to the next tab.
        """
        self.saved_tab = tab
        self.next_tab()
        return self

    def set_order(self, order: int) -> typing.Self:
        """
        Resets the order counter to the given value.
        """
        self.order = order
        return self

    def add_fields(self, fields: list[types.ui.GuiElement], *, parent: str | None = None) -> typing.Self:
        """
        Adds a list of GUI elements to the GUI.
        """
        # Copy fields, deep copy to ensure not modifying the original fields
        fields = [field.copy() for field in fields]
        for field in fields:
            # Add "parent." to the name of each field if a parent is specified
            if parent:
                field['name'] = f"{parent}.{field['name']}"
            field['gui']['order'] = self.next()
                
        self.fields.extend(fields)

        return self

    def add_stock_field(self, field: types.rest.stock.StockField) -> typing.Self:
        """
        Adds a stock field set to the GUI.
        """

        def update_order(gui: types.ui.GuiElement) -> types.ui.GuiElement:
            gui = gui.copy()
            gui['gui']['order'] = self.next()
            return gui

        self.fields.extend([update_order(i) for i in field.get_fields()])
        return self

    def add_hidden(
        self,
        name: str,
        *,
        default: str | int | bool | None = None,
        readonly: bool = False,
    ) -> typing.Self:
        """
        Creates a hidden field with the given parameters.
        """
        self.fields.append(
            self.make_gui(
                name,
                types.ui.FieldType.HIDDEN,
                default=default,
                readonly=readonly,
            )
        )
        return self

    def add_info(
        self,
        name: str,
        *,
        default: str | int | bool | None = None,
        readonly: bool = False,
    ) -> typing.Self:
        """
        Creates an info field with the given parameters.
        """
        self.fields.append(
            self.make_gui(
                name,
                types.ui.FieldType.INFO,
                default=default,
                readonly=readonly,
            )
        )
        return self

    def add_text(
        self,
        name: str,
        label: str,
        *,
        tooltip: str = '',
        tab: types.ui.Tab | str | None = None,
        default: str | None = None,
        readonly: bool = False,
        length: int | None = None,
        required: bool | None = None,
    ) -> typing.Self:
        """
        Creates a text field with the given parameters.
        """
        self.fields.append(
            self.make_gui(
                name,
                types.ui.FieldType.TEXT,
                label=label,
                tab=tab,
                default=default or '',
                readonly=readonly,
                length=length,
                required=required,
                tooltip=tooltip,
            )
        )
        return self

    def add_numeric(
        self,
        name: str,
        label: str,
        *,
        tooltip: str = '',
        tab: types.ui.Tab | str | None = None,
        default: int | None = None,
        readonly: bool = False,
        min_value: int | None = None,
        max_value: int | None = None,
        required: bool | None = None,
    ) -> typing.Self:
        """
        Creates a numeric field with the given parameters.
        """
        self.fields.append(
            self.make_gui(
                name,
                types.ui.FieldType.NUMERIC,
                label=label,
                tab=tab,
                default=default or 0,
                readonly=readonly,
                min_value=min_value,
                max_value=max_value,
                tooltip=tooltip,
                required=required,
            )
        )
        return self

    def add_checkbox(
        self,
        name: str,
        label: str,
        *,
        tooltip: str = '',
        tab: types.ui.Tab | str | None = None,
        default: bool | None = None,
        readonly: bool = False,
        required: bool | None = None,
    ) -> typing.Self:
        """
        Creates a checkbox field with the given parameters.
        """
        self.fields.append(
            self.make_gui(
                name,
                types.ui.FieldType.CHECKBOX,
                label=label,
                tab=tab,
                default=default or False,
                tooltip=tooltip,
                readonly=readonly,
                required=required,
            )
        )
        return self

    def add_choice(
        self,
        name: str,
        label: str,
        choices: list[types.ui.ChoiceItem],
        *,
        tooltip: str = '',
        tab: types.ui.Tab | str | None = None,
        default: str | None = None,
        readonly: bool = False,
        required: bool | None = None,
    ) -> typing.Self:
        """
        Creates a choice field with the given parameters.
        """
        self.fields.append(
            self.make_gui(
                name,
                types.ui.FieldType.CHOICE,
                label=label,
                choices=choices,
                tab=tab,
                default=default or (choices[0]['id'] if choices else None),
                readonly=readonly,
                tooltip=tooltip,
                required=required,
            )
        )
        return self

    def add_multichoice(
        self,
        name: str,
        label: str,
        choices: list[types.ui.ChoiceItem],
        *,
        tooltip: str = '',
        tab: types.ui.Tab | str | None = None,
        default: str | None = None,
        readonly: bool = False,
        required: bool | None = None,
    ) -> typing.Self:
        """
        Creates a multichoice field with the given parameters.
        """
        self.fields.append(
            self.make_gui(
                name,
                types.ui.FieldType.MULTICHOICE,
                label=label,
                choices=choices,
                tab=tab,
                tooltip=tooltip,
                default=default,
                readonly=readonly,
                required=required,
            )
        )
        return self

    def add_image_choice(
        self,
        *,
        name: str | None = None,
        label: str | None = None,
        choices: list[types.ui.ChoiceItem] | None = None,
        tooltip: str | None = None,
        tab: types.ui.Tab | str | None = None,
        default: str | None = None,
        readonly: bool = False,
        required: bool | None = None,
    ) -> typing.Self:
        """
        Creates an image choice field with the given parameters.
        """
        from uds.core import ui
        from uds.core.consts.images import DEFAULT_THUMB_BASE64
        from uds.models import Image

        name = name or 'image_id'
        label = label or gettext('Associated Image')
        if tooltip is None:
            tooltip = gettext('Select an image')

        if choices is None:
            choices = [ui.gui.choice_image(v.uuid, v.name, v.thumb64) for v in Image.objects.all()]

        # Prepend ui.gui.choice_image(-1, '--------', DEFAULT_THUMB_BASE64)
        choices = [ui.gui.choice_image(-1, '--------', DEFAULT_THUMB_BASE64)] + ui.gui.sorted_choices(choices)

        self.fields.append(
            self.make_gui(
                name,
                types.ui.FieldType.IMAGECHOICE,
                label=label,
                choices=choices,
                tab=tab,
                default=default,
                tooltip=tooltip,
                readonly=readonly,
                required=required,
            )
        )
        return self

    def build(self) -> list[types.ui.GuiElement]:
        return self.fields


class TableBuilder:
    """
    Builds a list of table fields for REST API responses.
    """

    title: str
    subtitle: str | None
    fields: list[types.rest.TableField]
    style_info: types.rest.RowStyleInfo

    def __init__(self, title: str, subtitle: str | None = None) -> None:
        # TODO: USe table_name on a later iteration of the code
        self.title = title
        self.subtitle = subtitle
        self.fields = []
        self.style_info = types.rest.RowStyleInfo.null()

    def _add_field(
        self,
        name: str,
        title: str,
        type: types.rest.TableFieldType = types.rest.TableFieldType.ALPHANUMERIC,
        visible: bool = True,
        width: str | None = None,
        dct: dict[typing.Any, typing.Any] | None = None,
    ) -> typing.Self:
        """
        Adds a field to the table fields.
        """
        self.fields.append(
            types.rest.TableField(
                name=name,
                title=title,
                type=type,
                visible=visible,
                width=width,
                dct=dct,  # Dictionary for dictionary fields, if applicable
            )
        )

        return self

    # For each field type, we can add a specific method
    def text_column(self, name: str, title: str, visible: bool = True, width: str | None = None) -> typing.Self:
        """
        Adds a string field to the table fields.
        """
        return self._add_field(name, title, types.rest.TableFieldType.ALPHANUMERIC, visible, width)

    def numeric_column(
        self, name: str, title: str, visible: bool = True, width: str | None = None
    ) -> typing.Self:
        """
        Adds a number field to the table fields.
        """
        return self._add_field(name, title, types.rest.TableFieldType.NUMERIC, visible, width)

    def boolean(self, name: str, title: str, visible: bool = True, width: str | None = None) -> typing.Self:
        """
        Adds a boolean field to the table fields.
        """
        return self._add_field(name, title, types.rest.TableFieldType.BOOLEAN, visible, width)

    def datetime_column(
        self, name: str, title: str, visible: bool = True, width: str | None = None
    ) -> typing.Self:
        """
        Adds a datetime field to the table fields.
        """
        return self._add_field(name, title, types.rest.TableFieldType.DATETIME, visible, width)

    def datetime_sec(
        self, name: str, title: str, visible: bool = True, width: str | None = None
    ) -> typing.Self:
        """
        Adds a datetime with seconds field to the table fields.
        """
        return self._add_field(name, title, types.rest.TableFieldType.DATETIMESEC, visible, width)

    def date(self, name: str, title: str, visible: bool = True, width: str | None = None) -> typing.Self:
        """
        Adds a date field to the table fields.
        """
        return self._add_field(name, title, types.rest.TableFieldType.DATE, visible, width)

    def time(self, name: str, title: str, visible: bool = True, width: str | None = None) -> typing.Self:
        """
        Adds a time field to the table fields.
        """
        return self._add_field(name, title, types.rest.TableFieldType.TIME, visible, width)

    def icon(self, name: str, title: str, visible: bool = True, width: str | None = None) -> typing.Self:
        """
        Adds an icon field to the table fields.
        """
        return self._add_field(name, title, types.rest.TableFieldType.ICON, visible, width)

    def dict_column(
        self,
        name: str,
        title: str,
        dct: dict[typing.Any, typing.Any],
        visible: bool = True,
        width: str | None = None,
    ) -> typing.Self:
        """
        Adds a dictionary field to the table fields.
        """
        return self._add_field(name, title, types.rest.TableFieldType.DICTIONARY, visible, width, dct=dct)

    def image(self, name: str, title: str, visible: bool = True, width: str | None = None) -> typing.Self:
        """
        Adds an image field to the table fields.
        """
        return self._add_field(name, title, types.rest.TableFieldType.IMAGE, visible, width)

    def row_style(self, prefix: str, field: str) -> typing.Self:
        """
        Sets the row style for the table fields.
        """
        self.style_info = types.rest.RowStyleInfo(prefix=prefix, field=field)
        return self

    def build(self) -> types.rest.TableInfo:
        """
        Returns the table info for the table fields.
        """
        return types.rest.TableInfo(
            title=self.title,
            fields=self.fields,
            row_style=self.style_info,
            subtitle=self.subtitle,
        )
