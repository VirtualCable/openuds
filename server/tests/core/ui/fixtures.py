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
import random
import datetime

from uds.core.ui.user_interface import UserInterface, gui

DEFAULTS: dict[str, typing.Any] = {
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
    'help_field': ['title', 'Default value info'],
}


class TestingOldUserInterface(UserInterface):
    strField = gui.TextField(
        label='Text Field',
        order=0,
        tooltip='This is a text field',
        required=True,
        default=typing.cast(str, DEFAULTS['str_field']),
        value=typing.cast(str, DEFAULTS['str_field']),
    )
    strAutoField = gui.TextAutocompleteField(
        label='Text Autocomplete Field',
        order=1,
        tooltip='This is a text autocomplete field',
        required=True,
        default=typing.cast(str, DEFAULTS['str_auto_field']),
        value=typing.cast(str, DEFAULTS['str_auto_field']),
    )
    numField = gui.NumericField(
        label='Numeric Field',
        order=2,
        tooltip='This is a numeric field',
        required=True,
        default=typing.cast(int, DEFAULTS['num_field']),
        value=typing.cast(int, DEFAULTS['num_field']),
    )
    passwordField = gui.PasswordField(
        label='Password Field',
        order=3,
        tooltip='This is a password field',
        required=True,
        default=typing.cast(str, DEFAULTS['password_field']),
        value=typing.cast(str, DEFAULTS['password_field']),
    )
    hiddenField = gui.HiddenField(
        label='Hidden Field',
        order=4,
        default=DEFAULTS['hidden_field'],
    )
    choiceField = gui.ChoiceField(
        label='Choice Field',
        order=5,
        tooltip='This is a choice field',
        required=False,
        default=typing.cast(str, DEFAULTS['choice_field']),
        value=typing.cast(str, DEFAULTS['choice_field']),
    )
    multiChoiceField = gui.MultiChoiceField(
        label='Multi Choice Field',
        order=6,
        tooltip='This is a multi choice field',
        default=typing.cast(list[str], DEFAULTS['multi_choice_field']),
        value=typing.cast(list[str], DEFAULTS['multi_choice_field']),
    )
    editableListField = gui.EditableListField(
        label='Editable List Field',
        order=7,
        tooltip='This is a editable list field',
        required=False,
        default=typing.cast(list[str], DEFAULTS['editable_list_field']),
        value=typing.cast(list[str], DEFAULTS['editable_list_field']),
    )
    checkboxField = gui.CheckBoxField(
        label='Checkbox Field',
        order=8,
        tooltip='This is a checkbox field',
        required=True,
        default=typing.cast(bool, DEFAULTS['checkbox_field']),
        value=typing.cast(bool, DEFAULTS['checkbox_field']),
    )
    imageChoiceField = gui.ImageChoiceField(
        label='Image Choice Field',
        order=9,
        tooltip='This is a image choice field',
        required=True,
        default=typing.cast(str, DEFAULTS['image_choice_field']),
        value=typing.cast(str, DEFAULTS['image_choice_field']),
    )
    dateField = gui.DateField(
        label='Date Field',
        order=10,
        tooltip='This is a date field',
        required=True,
        default=typing.cast(datetime.date, DEFAULTS['date_field']),
        value=typing.cast(datetime.date, DEFAULTS['date_field']),
    )


class TestingUserInterface(UserInterface):
    str_field = gui.TextField(
        label='Text Field',
        order=0,
        tooltip='This is a text field',
        required=True,
        default=typing.cast(str, DEFAULTS['str_field']),
        old_field_name='strField',
    )
    str_auto_field = gui.TextAutocompleteField(
        label='Text Autocomplete Field',
        order=1,
        tooltip='This is a text autocomplete field',
        required=True,
        default=typing.cast(str, DEFAULTS['str_auto_field']),
        choices=[
            gui.choice_item('Value 1', 'Value 1'),
            gui.choice_item('Value 2', 'Value 2'),
            gui.choice_item('Value 3', 'Value 3'),
        ],
        old_field_name='strAutoField',
    )
    num_field = gui.NumericField(
        label='Numeric Field',
        order=2,
        tooltip='This is a numeric field',
        required=True,
        default=typing.cast(int, DEFAULTS['num_field']),
        min_value=0,
        max_value=100,
        old_field_name='numField',
    )
    password_field = gui.PasswordField(
        label='Password Field',
        order=3,
        tooltip='This is a password field',
        required=True,
        default=typing.cast(str, DEFAULTS['password_field']),
        old_field_name='passwordField',
    )
    hidden_field = gui.HiddenField(
        label='Hidden Field',
        order=4,
        default=DEFAULTS['hidden_field'],
        old_field_name='hiddenField',
    )
    choice_field = gui.ChoiceField(
        label='Choice Field',
        order=5,
        tooltip='This is a choice field',
        required=False,
        default=typing.cast(str, DEFAULTS['choice_field']),
        choices=[
            gui.choice_item('Value 1', 'Value 1'),
            gui.choice_item('Value 2', 'Value 2'),
            gui.choice_item('Value 3', 'Value 3'),
        ],
        old_field_name='choiceField',
    )
    multi_choice_field = gui.MultiChoiceField(
        label='Multi Choice Field',
        order=6,
        tooltip='This is a multi choice field',
        default=typing.cast(list[str], DEFAULTS['multi_choice_field']),
        choices=[
            gui.choice_item('Value 1', 'Value 1'),
            gui.choice_item('Value 2', 'Value 2'),
            gui.choice_item('Value 3', 'Value 3'),
        ],
        old_field_name='multiChoiceField',
    )
    editable_list_field = gui.EditableListField(
        label='Editable List Field',
        order=7,
        tooltip='This is a editable list field',
        required=False,
        default=typing.cast(list[str], DEFAULTS['editable_list_field']),
        old_field_name='editableListField',
    )
    checkbox_field = gui.CheckBoxField(
        label='Checkbox Field',
        order=8,
        tooltip='This is a checkbox field',
        required=True,
        default=typing.cast(bool, DEFAULTS['checkbox_field']),
        old_field_name='checkboxField',
    )
    image_choice_field = gui.ImageChoiceField(
        label='Image Choice Field',
        order=9,
        tooltip='This is a image choice field',
        required=True,
        default=typing.cast(str, DEFAULTS['image_choice_field']),
        choices=[
            gui.choice_item('Value 1', 'Value 1'),
            gui.choice_item('Value 2', 'Value 2'),
            gui.choice_item('Value 3', 'Value 3'),
        ],
        old_field_name='imageChoiceField',
    )
    date_field = gui.DateField(
        label='Date Field',
        order=10,
        tooltip='This is a date field',
        required=True,
        default=typing.cast(datetime.date, DEFAULTS['date_field']),
        old_field_name='dateField',
    )
    help_field = gui.HelpField(
        label='Info Field',
        title=DEFAULTS['help_field'][0],
        help=DEFAULTS['help_field'][1],
        old_field_name='helpField',
    )

    # Equals operator, to speed up tests writing
    def __eq__(self, other: typing.Any) -> bool:
        if isinstance(other, TestingOldUserInterface):
            return (
                self.str_field.value == other.strField.value
                and self.str_auto_field.value == other.strAutoField.value
                and self.num_field.as_int() == other.numField.as_int()
                and self.password_field.value == other.passwordField.value
                # Hidden field is not compared, because it is not serialized
                and self.choice_field.value == other.choiceField.value
                and self.multi_choice_field.value == other.multiChoiceField.value
                and self.editable_list_field.value == other.editableListField.value
                and self.checkbox_field.value == other.checkboxField.value
                and self.image_choice_field.value == other.imageChoiceField.value
                and self.date_field.value == other.dateField.value
                # Info field is not compared, because it is not serialized
                # Nor help field, not present in old version
            )
        if not isinstance(other, TestingUserInterface):
            return False
        return (
            self.str_field.value == other.str_field.value
            and self.str_auto_field.value == other.str_auto_field.value
            and self.num_field.as_int() == other.num_field.as_int()
            and self.password_field.value == other.password_field.value
            # Hidden field is not compared, because it is not serialized
            and self.choice_field.value == other.choice_field.value
            and self.multi_choice_field.value == other.multi_choice_field.value
            and self.editable_list_field.value == other.editable_list_field.value
            and self.checkbox_field.value == other.checkbox_field.value
            and self.image_choice_field.value == other.image_choice_field.value
            and self.date_field.value == other.date_field.value
            # Info field is not compared, because it is not serialized
            # Nor help field, not present in old version
        )

    def randomize_values(self) -> None:
        self.str_field.default = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=10))
        self.str_auto_field.default = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=10))
        self.num_field.default = random.randint(0, 100)
        self.password_field.default = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=10))
        self.choice_field.default = random.choice(['Value 1', 'Value 2', 'Value 3'])
        self.multi_choice_field.default = random.sample(['Value 1', 'Value 2', 'Value 3'], 2)
        self.editable_list_field.default = random.sample(['Value 1', 'Value 2', 'Value 3'], 2)
        self.checkbox_field.default = random.choice([True, False])
        self.image_choice_field.default = random.choice(['Value 1', 'Value 2', 'Value 3'])
        self.date_field.default = datetime.date(
            random.randint(2000, 2022), random.randint(1, 12), random.randint(1, 28)
        )
        # Ignore HelpField, not present in old version

        # Also, randomize values
        self.str_field.value = self.str_field.default
        self.str_auto_field.value = self.str_auto_field.default
        self.num_field.value = self.num_field.default
        self.password_field.value = self.password_field.default
        self.choice_field.value = self.choice_field.default
        self.multi_choice_field.value = self.multi_choice_field.default
        self.editable_list_field.value = self.editable_list_field.default
        self.checkbox_field.value = self.checkbox_field.default
        self.image_choice_field.value = self.image_choice_field.default
        self.date_field.value = self.date_field.default


class TestingUserInterfaceFieldNameOrig(UserInterface):
    strField = gui.TextField(
        label='Text Field',
        order=0,
        tooltip='This is a text field',
        required=True,
        default=typing.cast(str, DEFAULTS['str_field']),
        value=typing.cast(str, DEFAULTS['str_field']),
    )


class TestingUserInterfaceFieldName(UserInterface):
    str_field = gui.TextField(
        label='Text Field',
        order=0,
        tooltip='This is a text field',
        required=True,
        default='',  # Will be loaded from orig
        old_field_name='strField',
    )


class TestingUserInterfaceFieldNameSeveral(UserInterface):
    str2_field = gui.TextField(
        label='Text Field',
        order=0,
        tooltip='This is a text field',
        required=True,
        default='',  # Will be loaded from orig
        old_field_name=['str_field', 'strField'],
    )
