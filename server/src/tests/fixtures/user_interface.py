# -*- coding: utf-8 -*-
#
# Copyright (c) 2022 Virtual Cable S.L.
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
import datetime

from uds.core.ui.user_interface import UserInterface, gui

DEFAULTS: typing.Dict[str, typing.Union[str, int, typing.List[str], datetime.date]] = {
    'str_field': 'Default value text',
    'str_auto_field': 'Default value auto',
    'num_field': 50,
    'password_field': 'Default value password',
    'hidden_field': 'Default value hidden',
    'choice_field': 'Default value choice',
    'multi_choice_field': ['Default value multi choice 1', 'Default value multi choice 2'],
    'editable_list_field': ['Default value editable list 1', 'Default value editable list 2'],
    'checkbox_field': True,
    'image_choice_field': 'Default value image choice',
    'image_field': 'Default value image',
    'date_field': datetime.date(2009, 12, 9),
    'info_field': 'Default value info',
}

class TestingUserInterface(UserInterface):
    str_field = gui.TextField(
        label='Text Field',
        order=0,
        tooltip='This is a text field',
        required=True,
        value=typing.cast(str, DEFAULTS['str_field']),
    )
    str_auto_field = gui.TextAutocompleteField(
        label='Text Autocomplete Field',
        order=1,
        tooltip='This is a text autocomplete field',
        required=True,
        default=typing.cast(str, DEFAULTS['str_auto_field']),
        choices=['Value 1', 'Value 2', 'Value 3'],
    )
    num_field = gui.NumericField(
        label='Numeric Field',
        order=1,
        tooltip='This is a numeric field',
        required=True,
        default=typing.cast(int, DEFAULTS['num_field']),
        minValue=0,
        maxValue=100,
    )
    password_field = gui.PasswordField(
        label='Password Field',
        order=2,
        tooltip='This is a password field',
        required=True,
        default=DEFAULTS['password_field'],
    )
    hidden_field = gui.HiddenField(
        label='Hidden Field',
        order=3,
        default=DEFAULTS['hidden_field'],
    )
    choice_field = gui.ChoiceField(
        label='Choice Field',
        order=4,
        tooltip='This is a choice field',
        required=True,
        value=typing.cast(str, DEFAULTS['choice_field']),
        choices=['Value 1', 'Value 2', 'Value 3'],
    )
    multi_choice_field = gui.MultiChoiceField(
        label='Multi Choice Field',
        order=5,
        tooltip='This is a multi choice field',
        required=True,
        default=typing.cast(typing.List[str], DEFAULTS['multi_choice_field']),
        choices=['Value 1', 'Value 2', 'Value 3'],
    )
    editable_list_field = gui.EditableListField(
        label='Editable List Field',
        order=6,
        tooltip='This is a editable list field',
        required=True,
        default=typing.cast(typing.List[str], DEFAULTS['editable_list_field']),
    )
    checkbox_field = gui.CheckBoxField(
        label='Checkbox Field',
        order=7,
        tooltip='This is a checkbox field',
        required=True,
        default=typing.cast(bool, DEFAULTS['checkbox_field']),
    )
    image_choice_field = gui.ImageChoiceField(
        label='Image Choice Field',
        order=8,
        tooltip='This is a image choice field',
        required=True,
        default=typing.cast(str, DEFAULTS['image_choice_field']),
        choices=['Value 1', 'Value 2', 'Value 3'],
    )
    date_field = gui.DateField(
        label='Date Field',
        order=10,
        tooltip='This is a date field',
        required=True,
        default=typing.cast(datetime.date, DEFAULTS['date_field']),
    )
    info_field = gui.InfoField(
        label='title',
        default=typing.cast(str, DEFAULTS['info_field']),
    )


    # Equals operator, to speed up tests writing
    def __eq__(self, other: typing.Any) -> bool:
        if not isinstance(other, TestingUserInterface):
            return False
        return (
            self.str_field.value == other.str_field.value
            and self.str_auto_field.value == other.str_auto_field.value
            and self.num_field.num() == other.num_field.num()
            and self.password_field.value == other.password_field.value
            # Hidden field is not compared, because it is not serialized
            and self.choice_field.value == other.choice_field.value
            and self.multi_choice_field.value == other.multi_choice_field.value
            and self.editable_list_field.value == other.editable_list_field.value
            and self.checkbox_field.value == other.checkbox_field.value
            and self.image_choice_field.value == other.image_choice_field.value
            and self.date_field.value == other.date_field.value
            # Info field is not compared, because it is not serialized
        )
