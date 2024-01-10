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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
# We use commit/rollback
from ...utils.test import UDSTestCase
from uds.core.ui.user_interface import gui, UDSB, UDSK

from django.conf import settings
from uds.core.util import ensure

class GuiTest(UDSTestCase):
    def test_globals(self):
        self.assertEqual(UDSK, settings.SECRET_KEY[8:24].encode())
        self.assertEqual(UDSB, b'udsprotect')

    def test_convert_to_choices(self) -> None:
        # Several cases
        # 1. Empty list
        # 2.- single string
        # 3.- A list of strings
        # 4.- A list of dictinaries, must be {'id': 'xxxx', 'text': 'yyy'}
        # 5.- A Dictionary, Keys will be used in 'id' and values in 'text'
        self.assertEqual(gui.as_choices([]), [])
        self.assertEqual(gui.as_choices('aaaa'), [{'id': 'aaaa', 'text': 'aaaa'}])
        self.assertEqual(
            gui.as_choices(['a', 'b']),
            [{'id': 'a', 'text': 'a'}, {'id': 'b', 'text': 'b'}],
        )
        self.assertEqual(
            gui.as_choices({'a': 'b', 'c': 'd'}),
            [{'id': 'a', 'text': 'b'}, {'id': 'c', 'text': 'd'}],
        )
        self.assertEqual(
            gui.as_choices({'a': 'b', 'c': 'd'}),
            [{'id': 'a', 'text': 'b'}, {'id': 'c', 'text': 'd'}],
        )
        # Expect an exception if we pass a list of dictionaries without id or text
        self.assertRaises(ValueError, gui.as_choices, [{'a': 'b', 'c': 'd'}])
        # Also if we pass a list of dictionaries with id and text, but not all of them
        self.assertRaises(
            ValueError,
            gui.as_choices,
            [{'id': 'a', 'text': 'b'}, {'id': 'c', 'text': 'd'}, {'id': 'e'}],
        )

    def test_convert_to_list(self) -> None:
        # Several cases
        # 1. Empty list
        # 2.- single string
        # 3.- A list of strings
        self.assertEqual(ensure.is_list([]), [])
        self.assertEqual(ensure.is_list('aaaa'), ['aaaa'])
        self.assertEqual(ensure.is_list(['a', 'b']), ['a', 'b'])
        self.assertEqual(ensure.is_list(1), [1])

    def test_choice_image(self) -> None:
        # id, text, and base64 image
        self.assertEqual(
            gui.choice_image('id', 'text', 'image'),
            {'id': 'id', 'text': 'text', 'img': 'image'},
        )

    def test_to_bool(self) -> None:
        for val in ('true', 'True', 'TRUE', 'yes', 'Yes', 'YES', '1'):
            self.assertTrue(gui.as_bool(val), f'Failed to convert "{val}" to True')
        for val in ('false', 'False', 'FALSE', 'no', 'No', 'NO', '0'):
            self.assertFalse(
                gui.as_bool(val), f'Failed to convert "{val}" to False'
            )
