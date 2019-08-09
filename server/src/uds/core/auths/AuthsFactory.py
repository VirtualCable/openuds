# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2019 Virtual Cable S.L.
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
import typing

# Not imported in runtime, just for type checking
if typing.TYPE_CHECKING:
    from .BaseAuthenticator import Authenticator

class AuthsFactory:
    """
    This class holds the register of all known authentication modules
    inside UDS.

    It provides a way to register and recover Authentication providers.
    """
    _factory: typing.Optional['AuthsFactory'] = None
    _auths: typing.Dict[str, typing.Type['Authenticator']] = {}

    def __init__(self):
        pass

    @staticmethod
    def factory() -> 'AuthsFactory':
        """
        Returns the factory that keeps the register of authentication providers.
        """
        if AuthsFactory._factory is None:
            AuthsFactory._factory = AuthsFactory()
        return AuthsFactory._factory

    def providers(self) -> typing.Dict[str, typing.Type['Authenticator']]:
        """
        Returns the list of authentication providers already registered.
        """
        return self._auths

    def insert(self, type_: typing.Type['Authenticator']):
        """
        Registers a new authentication provider
        """
        self._auths[type_.type().lower()] = type_

    def lookup(self, typeName: str) -> typing.Optional[typing.Type['Authenticator']]:
        """
        Tries to locate an authentication provider and by its name, and, if
        not found, returns None
        """
        return self._auths.get(typeName.lower(), None)
