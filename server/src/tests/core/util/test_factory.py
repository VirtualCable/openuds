# -*- coding: utf-8 -*-

#
# Copyright (c) 2024 Virtual Cable S.L.U.
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
from ast import Sub
import typing
import collections.abc
import logging

from unittest import mock

from py import test


from ...utils.test import UDSTestCase

from uds.core.util import factory

logger = logging.getLogger(__name__)


class FactoryObject:
    def __init__(self, name: str, value: int):
        self.name = name
        self.value = value


class Subclass1(FactoryObject):
    pass


class Subclass2(FactoryObject):
    pass


class FactoryTest(UDSTestCase):
    def test_factory(self) -> None:
        test_factory = factory.Factory[FactoryObject]()

        test_factory.register('first', Subclass1)
        test_factory.register('second', Subclass2)

        self.assertIn('first', test_factory.objects())
        self.assertIn('second', test_factory.objects())

        self.assertTrue('first' in test_factory.objects())
        self.assertTrue('second' in test_factory.objects())

        self.assertCountEqual(test_factory.objects(), ['first', 'second'])

        self.assertEqual(test_factory.objects()['first'], Subclass1)
        self.assertEqual(test_factory['first'], Subclass1)
        self.assertEqual(test_factory.get_type('first'), Subclass1)

        self.assertEqual(test_factory.objects()['second'], Subclass2)
        self.assertEqual(test_factory['second'], Subclass2)
        self.assertEqual(test_factory.get_type('second'), Subclass2)

        # This should not raise an exception, but call to its logger.debug
        with mock.patch.object(factory.logger, 'debug') as mock_debug:
            test_factory.register('first', Subclass1)
            mock_debug.assert_called_once()

        # As singleton, another instance should be the same
        self.assertEqual(test_factory, factory.Factory[FactoryObject]())
