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
import typing
import collections.abc
import logging


from ...utils.test import UDSTestCase

from uds.core.util import ensure

logger = logging.getLogger(__name__)


class EnsureTest(UDSTestCase):
    def test_ensure_list(self):
        self.assertEqual(ensure.is_list([]), [])
        self.assertEqual(ensure.is_list([1, 2, 3]), [1, 2, 3])
        self.assertEqual(ensure.is_list((1, 2, 3)), [1, 2, 3])
        self.assertEqual(ensure.is_list(1), [1])
        self.assertEqual(ensure.is_list('111'), ['111'])
        self.assertEqual(ensure.is_list(None), [])
        self.assertEqual(ensure.is_list({}), [])
        self.assertEqual(ensure.is_list({1, 2, 3}), [1, 2, 3])


    def test_ensure_iterable(self):
        self.assertEqual(list(ensure.is_iterable([])), [])
        self.assertIsInstance(ensure.is_iterable([]), typing.Iterator)
        self.assertEqual(list(ensure.is_iterable([1, 2, 3])), [1, 2, 3])
        self.assertIsInstance(ensure.is_iterable([1, 2, 3]), typing.Iterator)
        self.assertEqual(list(ensure.is_iterable((1, 2, 3))), [1, 2, 3])
        self.assertIsInstance(ensure.is_iterable((1, 2, 3)), typing.Iterator)
        self.assertEqual(list(ensure.is_iterable(1)), [1])
        self.assertIsInstance(ensure.is_iterable(1), typing.Iterator)
        self.assertEqual(list(ensure.is_iterable('111')), ['111'])
        self.assertIsInstance(ensure.is_iterable('111'), typing.Iterator)
        self.assertEqual(list(ensure.is_iterable(None)), [])
        self.assertIsInstance(ensure.is_iterable(None), typing.Iterator)
        self.assertEqual(list(ensure.is_iterable({})), [])
        self.assertIsInstance(ensure.is_iterable({}), typing.Iterator)
        self.assertEqual(list(ensure.is_iterable({1, 2, 3})), [1, 2, 3])
        self.assertIsInstance(ensure.is_iterable({1, 2, 3}), typing.Iterator)

