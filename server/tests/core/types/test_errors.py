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
Author: Janier Rodríguez, jrodriguez at virtualcable dot es
"""

from uds.core import exceptions
from uds.core.types.errors import Error

from ...utils.test import UDSTestCase


class ErrorFromExceptionTest(UDSTestCase):
    """
    Mapping of authentication exceptions to the error shown to the user
    """

    def test_authenticator_exception_is_access_denied(self) -> None:
        error = Error.from_exception(exceptions.auth.AuthenticatorException('User not found'))
        self.assertEqual(error, Error.ACCESS_DENIED)

    def test_invalid_user_exception_is_access_denied(self) -> None:
        error = Error.from_exception(exceptions.auth.InvalidUserException())
        self.assertEqual(error, Error.ACCESS_DENIED)

    def test_invalid_authenticator_exception_is_invalid_callback(self) -> None:
        error = Error.from_exception(exceptions.auth.InvalidAuthenticatorException())
        self.assertEqual(error, Error.INVALID_CALLBACK)

    def test_unmapped_exception_is_unknown_error(self) -> None:
        error = Error.from_exception(ValueError('not mapped'))
        self.assertEqual(error, Error.UNKNOWN_ERROR)
