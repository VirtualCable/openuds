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


class UserinterfaceTestInternalData(UDSTestCase):
    def test_data(self):
        # This test is to ensure that old serialized data can be loaded
        # This data is from a
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
