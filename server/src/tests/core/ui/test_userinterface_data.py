# -*- coding: utf-8 -*-

#
# Copyright (c) 2022 Virtual Cable S.L.U.
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
import typing

# We use commit/rollback
from ...utils.test import UDSTestCase

from uds.core import types, consts
from uds.core.ui.user_interface import gui

from ...fixtures.user_interface import TestingUserInterface, DEFAULTS

logger = logging.getLogger(__name__)


class UserinterfaceInternalTest(UDSTestCase):
    def test_value(self):
        # Asserts that data is correctly stored and retrieved
        ui = TestingUserInterface()
        self.assertEqual(ui.str_field.value, DEFAULTS['str_field'])
        self.assertEqual(ui.str_auto_field.value, DEFAULTS['str_auto_field'])
        self.assertEqual(ui.num_field.value, DEFAULTS['num_field'])
        self.assertEqual(ui.password_field.value, DEFAULTS['password_field'])
        self.assertEqual(ui.hidden_field.value, DEFAULTS['hidden_field'])
        self.assertEqual(ui.choice_field.value, DEFAULTS['choice_field'])
        self.assertEqual(ui.multi_choice_field.value, DEFAULTS['multi_choice_field'])
        self.assertEqual(ui.editable_list_field.value, DEFAULTS['editable_list_field'])
        self.assertEqual(ui.checkbox_field.value, DEFAULTS['checkbox_field'])
        self.assertEqual(ui.image_choice_field.value, DEFAULTS['image_choice_field'])
        self.assertEqual(ui.date_field.value, DEFAULTS['date_field'])
        self.assertEqual(ui.info_field.value, DEFAULTS['info_field'])
        
    def test_default(self):
        ui = TestingUserInterface()
        # Now for default values
        self.assertEqual(ui.str_field.default, DEFAULTS['str_field'])
        self.assertEqual(ui.str_auto_field.default, DEFAULTS['str_auto_field'])
        self.assertEqual(ui.num_field.default, DEFAULTS['num_field'])
        self.assertEqual(ui.password_field.default, DEFAULTS['password_field'])
        self.assertEqual(ui.hidden_field.default, DEFAULTS['hidden_field'])
        self.assertEqual(ui.choice_field.default, DEFAULTS['choice_field'])
        self.assertEqual(ui.multi_choice_field.default, DEFAULTS['multi_choice_field'])
        self.assertEqual(ui.editable_list_field.default, DEFAULTS['editable_list_field'])
        self.assertEqual(ui.checkbox_field.default, DEFAULTS['checkbox_field'])
        self.assertEqual(ui.image_choice_field.default, DEFAULTS['image_choice_field'])
        self.assertEqual(ui.date_field.default, DEFAULTS['date_field'])
        self.assertEqual(ui.info_field.default, DEFAULTS['info_field'])

    def test_references(self):
        ui = TestingUserInterface()
        # Ensure references are fine
        self.assertEqual(ui.str_field.value, ui._gui['str_field'].value)
        self.assertEqual(ui.str_auto_field.value, ui._gui['str_auto_field'].value)
        self.assertEqual(ui.num_field.value, ui._gui['num_field'].value)
        self.assertEqual(ui.password_field.value, ui._gui['password_field'].value)
        self.assertEqual(ui.hidden_field.value, ui._gui['hidden_field'].value)
        self.assertEqual(ui.choice_field.value, ui._gui['choice_field'].value)
        self.assertEqual(ui.multi_choice_field.value, ui._gui['multi_choice_field'].value)
        self.assertEqual(ui.editable_list_field.value, ui._gui['editable_list_field'].value)
        self.assertEqual(ui.checkbox_field.value, ui._gui['checkbox_field'].value)
        self.assertEqual(ui.image_choice_field.value, ui._gui['image_choice_field'].value)
        self.assertEqual(ui.date_field.value, ui._gui['date_field'].value)
        self.assertEqual(ui.info_field.value, ui._gui['info_field'].value)

    def test_modify(self):
        ui = TestingUserInterface()
        # Modify values, and recheck references
        ui.str_field.value = 'New value'
        self.assertEqual(ui.str_field.value, ui._gui['str_field'].value)
        ui.str_auto_field.value = 'New value'
        self.assertEqual(ui.str_auto_field.value, ui._gui['str_auto_field'].value)
        ui.num_field.value = 100
        self.assertEqual(ui.num_field.value, ui._gui['num_field'].value)
        ui.password_field.value = 'New value'
        self.assertEqual(ui.password_field.value, ui._gui['password_field'].value)
        ui.hidden_field.value = 'New value'
        self.assertEqual(ui.hidden_field.value, ui._gui['hidden_field'].value)
        ui.choice_field.value = 'New value'
        self.assertEqual(ui.choice_field.value, ui._gui['choice_field'].value)
        ui.multi_choice_field.value = ['New value', 'New value 2']
        self.assertEqual(ui.multi_choice_field.value, ui._gui['multi_choice_field'].value)
        ui.editable_list_field.value = ['New value', 'New value 2']
        self.assertEqual(ui.editable_list_field.value, ui._gui['editable_list_field'].value)
        ui.checkbox_field.value = False
        self.assertEqual(ui.checkbox_field.value, ui._gui['checkbox_field'].value)
        ui.image_choice_field.value = 'New value'
        self.assertEqual(ui.image_choice_field.value, ui._gui['image_choice_field'].value)
        ui.date_field.value = '2001-01-01'
        self.assertEqual(ui.date_field.value, ui._gui['date_field'].value)
        ui.info_field.value = 'New value'
        self.assertEqual(ui.info_field.value, ui._gui['info_field'].value)

    def test_valuesDict(self):
        ui = TestingUserInterface()
        self.assertEqual(
            ui.valuesDict(),
            {
                'str_field': DEFAULTS['str_field'],
                'str_auto_field': DEFAULTS['str_auto_field'],
                'num_field': DEFAULTS['num_field'],
                'password_field': DEFAULTS['password_field'],
                'hidden_field': DEFAULTS['hidden_field'],
                'choice_field': DEFAULTS['choice_field'],
                'multi_choice_field': DEFAULTS['multi_choice_field'],
                'editable_list_field': DEFAULTS['editable_list_field'],
                'checkbox_field': DEFAULTS['checkbox_field'],
                'image_choice_field': DEFAULTS['image_choice_field'],
                'date_field': DEFAULTS['date_field'],
                'info_field': DEFAULTS['info_field'],
            },
        )
        
    def test_labels(self):
        ui = TestingUserInterface()
        self.assertEqual(
            { k: v.label for k, v in ui._gui.items() },
            {
                'str_field': 'Text Field',
                'str_auto_field': 'Text Autocomplete Field',
                'num_field': 'Numeric Field',
                'password_field': 'Password Field',
                'hidden_field': 'Hidden Field',
                'choice_field': 'Choice Field',
                'multi_choice_field': 'Multi Choice Field',
                'editable_list_field': 'Editable List Field',
                'checkbox_field': 'Checkbox Field',
                'image_choice_field': 'Image Choice Field',
                'date_field': 'Date Field',
                'info_field': 'Info Field',
            },
        )
        
    def test_order(self):
        ui = TestingUserInterface()
        self.assertEqual(
            { k: v._fieldsInfo.order for k, v in ui._gui.items() },
            {
                'str_field': 0,
                'str_auto_field': 1,
                'num_field': 2,
                'password_field': 3,
                'hidden_field': 4,
                'choice_field': 5,
                'multi_choice_field': 6,
                'editable_list_field': 7,
                'checkbox_field': 8,
                'image_choice_field': 9,
                'date_field': 10,
                'info_field': 0,  # Info field is without order, so it's 0
            },
        )
        
    def test_required(self):
        ui = TestingUserInterface()
        self.assertEqual(
            { k: v._fieldsInfo.required for k, v in ui._gui.items() },
            {
                'str_field': True,
                'str_auto_field': True,
                'num_field': True,
                'password_field': True,
                'hidden_field': None,  # Not present, so it's None
                'choice_field': False,
                'multi_choice_field': None,  # Not present, so it's None
                'editable_list_field': False,
                'checkbox_field': True,
                'image_choice_field': True,
                'date_field': True,
                'info_field': None,  # Info field is without required, so it's None
            },
        )
        
    def test_tooltip(self):
        ui = TestingUserInterface()
        self.assertEqual(
            { k: v._fieldsInfo.tooltip for k, v in ui._gui.items() },
            {
                'str_field': 'This is a text field',
                'str_auto_field': 'This is a text autocomplete field',
                'num_field': 'This is a numeric field',
                'password_field': 'This is a password field',
                'hidden_field': '', # Tooltip is required, so it's ''
                'choice_field': 'This is a choice field',
                'multi_choice_field': 'This is a multi choice field',
                'editable_list_field': 'This is a editable list field',
                'checkbox_field': 'This is a checkbox field',
                'image_choice_field': 'This is a image choice field',
                'date_field': 'This is a date field',
                'info_field': '',  # Info field is without tooltip, so it's '' because it's required
            },
        )