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
# We use commit/rollback
from ...utils.test import UDSTestCase
from uds.core.ui.user_interface import (
    gui,
    UserInterface
)
import time

from ...fixtures.user_interface import TestingUserInterface, DEFAULTS

class UserinterfaceTest(UDSTestCase):

    # Helpers
    def ensure_values_fine(self, ui: TestingUserInterface) -> None:
        # Ensure that all values are fine for the ui fields
        self.assertEqual(ui.str_field.value, DEFAULTS['str_field'], 'str_field')
        self.assertEqual(ui.str_auto_field.value, DEFAULTS['str_auto_field'], 'str_auto_field')
        self.assertEqual(ui.num_field.num(), DEFAULTS['num_field'], 'num_field')
        self.assertEqual(ui.password_field.value, DEFAULTS['password_field'], 'password_field')
        # Hidden field is not stored, so it's not checked
        self.assertEqual(ui.choice_field.value, DEFAULTS['choice_field'], 'choice_field')
        self.assertEqual(ui.multi_choice_field.value, DEFAULTS['multi_choice_field'], 'multi_choice_field')
        self.assertEqual(ui.editable_list_field.value, DEFAULTS['editable_list_field'], 'editable_list_field')
        self.assertEqual(ui.checkbox_field.value, DEFAULTS['checkbox_field'], 'checkbox_field')
        self.assertEqual(ui.image_choice_field.value, DEFAULTS['image_choice_field'], 'image_choice_field')
        self.assertEqual(ui.image_field.value, DEFAULTS['image_field'], 'image_field')
        self.assertEqual(ui.date_field.value, DEFAULTS['date_field'], 'date_field')

    def test_serialization(self):
        pass

    def test_old_serialization(self):
        # This test is to ensure that old serialized data can be loaded
        # This data is from a
        ui = TestingUserInterface()
        data = ui.oldSerializeForm()
        ui2 = TestingUserInterface()
        ui2.oldUnserializeForm(data)

        self.assertEqual(ui, ui2)
        self.ensure_values_fine(ui2)

        # Now unserialize old data with new method, (will internally call oldUnserializeForm)
        ui3 = TestingUserInterface()
        ui3.unserializeForm(data)

        self.assertEqual(ui, ui3)
        self.ensure_values_fine(ui3)

    def test_new_serialization(self):
        # This test is to ensure that new serialized data can be loaded
        ui = TestingUserInterface()
        data = ui.serializeForm()
        ui2 = TestingUserInterface()
        ui2.unserializeForm(data)

        self.assertEqual(ui, ui2)
        self.ensure_values_fine(ui2)