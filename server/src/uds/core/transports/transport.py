# pylint: disable=unused-argument  # this has a lot of "default" methods, so we need to ignore unused arguments most of the time

#
# Copyright (c) 2012-2022 Virtual Cable S.L.U.
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
import codecs
import collections.abc
import logging
import sys
import typing

from django.utils.translation import gettext_noop as _

from uds import models
from uds.core import consts, types
from uds.core.managers.crypto import CryptoManager
from uds.core.module import Module
from uds.core.util import net

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.environment import Environment
    from uds.core.types.requests import ExtendedHttpRequestWithUser
    from uds import models

logger = logging.getLogger(__name__)


class Transport(Module):
    """
    An OS Manager is responsible for communication the service the different actions to take (i.e. adding a windows machine to a domain)
    The Service (i.e. virtual machine) communicates with the OSManager via a published web method, that must include the unique ID.
    In order to make easier to agents identify themselfs, the Unique ID can be a list with various Ids (i.e. the macs of the virtual machine).
    Server will iterate thought them and look for an identifier associated with the service. This list is a comma separated values (i.e. AA:BB:CC:DD:EE:FF,00:11:22:...)
    Remember also that we inherit the test and check methods from BaseModule
    """

    # Transport informational related data, inherited from BaseModule
    type_name = 'Base Transport Manager'
    type_type = 'Base Transport'
    type_description = 'Base Transport'
    icon_file = 'transport.png'
    # Supported names for OS (used right now, but lots of more names for sure)
    # Windows
    # Macintosh
    # Linux
    supported_oss: tuple[types.os.KnownOS, ...] = consts.os.DESKTOP_OSS  # Supported operating systems

    # If the link to use transport is provided by transport itself
    own_link: bool = False

    # Protocol "type". This is not mandatory, but will help
    protocol: types.transports.Protocol = types.transports.Protocol.NONE

    # For allowing grouping transport on dashboard "new" menu, and maybe other places
    group: typing.ClassVar[types.transports.Grouping] = types.transports.Grouping.DIRECT

    _db_obj: typing.Optional['models.Transport'] = None

    def __init__(self, environment: 'Environment', values: types.core.ValuesType):
        super().__init__(environment, values)
        self.initialize(values)

    def initialize(self, values: 'types.core.ValuesType') -> None:
        """
        This method will be invoked from __init__ constructor.
        This is provided so you don't have to provide your own __init__ method,
        and invoke base methods.
        This will get invoked when all initialization stuff is done

        Args:
            Values: If values is not none, this object is being initialized
            from administration interface, and not unmarshal will be done.
            If it's None, this is initialized internally, and unmarshal will
            be called after this.

        Default implementation does nothing
        """

    def destroy(self) -> None:
        """
        Invoked when Transport is deleted
        """

    def db_obj(self) -> 'models.Transport':
        """
        Returns the database object for this provider
        """
        from uds.models.transport import Transport

        if self._db_obj is None:
            if not self.get_uuid():
                return Transport.null()
            self._db_obj = Transport.objects.get(uuid__iexact=self.get_uuid())

        return self._db_obj

    def test_connectivity(
        self,
        userservice: 'models.UserService',
        ip: str,
        port: typing.Union[str, int],
        timeout: float = 4,
    ) -> bool:
        return net.test_connectivity(ip, int(port), timeout)

    def is_ip_allowed(self, userservice: 'models.UserService', ip: str) -> bool:
        """
        Checks if the transport is available for the requested destination ip
        Override this in yours transports
        """
        return False

    def get_available_error_msg(self, userservice: 'models.UserService', ip: str) -> str:
        """
        Returns a customized error message, that will be used when a service fails to check "isAvailableFor"
        Override this in yours transports if needed
        """
        return f'Not accessible (using service ip {ip})'

    @classmethod
    def supports_protocol(cls, protocol: typing.Union[collections.abc.Iterable[str], str]) -> bool:
        if isinstance(protocol, str):
            return protocol.lower() == cls.protocol.lower()
        # Not string group of strings
        for v in protocol:
            if cls.supports_protocol(v):
                return True
        return False

    @classmethod
    def supports_os(cls, os: types.os.KnownOS) -> bool:
        """
        Helper method to check if transport supports requested operating system.
        Class method
        """
        return os in cls.supported_oss

    @classmethod
    def provides_connetion_info(cls) -> bool:
        """
        Helper method to check if transport provides information about connection
        """
        return cls.get_connection_info is not Transport.get_connection_info

    def get_connection_info(
        self,
        userservice: typing.Union['models.UserService', 'models.ServicePool'],
        user: 'models.User',
        password: str,
    ) -> types.connections.ConnectionData:
        """
        This method must provide information about connection.
        We don't have to implement it, but if we wont to allow some types of connections
        (such as Client applications, some kinds of TC, etc... we must provide it or those
        kind of terminals/application will not work

        Args:
            userservice: UserService for witch we are rendering the connection (db model), or ServicePool (db model)self.

            user: user (dbUser) logged in
            pass: password used in authentication

        The expected result from this method is a ConnectionInfoType object

        :note: The provided service can be an user service or an service pool (parent of user services).
               I have implemented get_connection_info in both so in most cases we do not need if the service is
               ServicePool or UserService. In case of get_connection_info for an ServicePool, no transformation
               is done, because there is no relation at that level between user and service.
        """
        if isinstance(userservice, models.ServicePool):
            username, password = userservice.process_user_password(user.name, password)
        else:
            username = self.processed_username(userservice, user)
        return types.connections.ConnectionData(
            protocol=self.protocol,
            username=username,
            service_type=types.services.ServiceType.VDI,
            password='',  # nosec: password is empty string, no password
            domain='',
        )

    def processed_username(self, userservice: 'models.UserService', user: 'models.User') -> str:
        """
        Used to "transform" username that will be sent to service
        This is used to make the "user" that will receive the service match with that sent in notification
        @return: transformed username
        """
        return user.name

    def generate_key(self, length: int = 32) -> str:
        """
        Returns a random key of the requested length
        Used for generate keys for the tunnel mainly, but can be used for other purposes
        """
        return CryptoManager.manager().random_string(length)

    def get_transport_script(
        self,
        userservice: 'models.UserService',
        transport: 'models.Transport',
        ip: str,
        os: 'types.os.DetectedOsInfo',  # pylint: disable=redefined-outer-name
        user: 'models.User',
        password: str,
        request: 'ExtendedHttpRequestWithUser',
    ) -> types.transports.TransportScript:
        """
        If this is an uds transport, this will return the tranport script needed for executing
        this on client
        """
        return types.transports.TransportScript(
            script="raise Exception('The selected transport is not supported on your platform.'.format(transport=sp['transport']))",
            signature_b64='Ki6Emu7h3gBmqipOD7uW6ytIXQLg149a2vRcCHcl2yyIXqX0'
            '4JAViKwhVrbQhAZ5kli1uzLOKa7heLMT0Wif6SAckcMuyOng'
            'lrEZW0xnzuCWYTj3373a1qWX8wres8mzxA9x3cQ9PuzDSRDS'
            'ZMbXbVTifkZU0t5hAV4poLe7oAkjx9bypmQOjFB3MN0XRqGT'
            'AqlT+bViL4a8FL/pkMIDk/2Z2PGh2yF8FkWBab34eSHCwXA8'
            'GgZ/xC3VtO7c1hq6bxNdneVxxLM74EYRpqy4rXX8QXCoZ2kB'
            '+7VMviG+lqXDkj1xQpTK77rnYj6ye6mSHLPd+bLkQ3/XqV6e'
            '1pqTlVwas1PMmsduEuhEJ+cRh9IhOMCM9oTWcngPGD8n9CQM'
            'k3eMmb/73Tx5ZCg6BhpNjZNKmnomEmEFkdQpX3afZ4bS9Nic'
            'E9M+IJTv+g5AImGZTZXsskDTYP+bQeygugXw0p3YZqDaJeIp'
            'C2u1gDZjgCJ6FobGVziqdqLNRNOjwjP82y8nU6jvs6rnQD+4'
            'qBps9EVau//q3nXyTbWtQfmC8hqQ5hsFID9K27WNy92OHqIc'
            'fd6NuTG7jC+TiHyMGC937TfiQQy+0J8BiQtjY4Q3I+Sws7AT'
            'XXv7MJMqYLXIVi0Fn8yrTiFqEDP2l4eFwKv7XZn5c+RO8ZE9'
            'NbxIWj2Fvuw=',
            parameters={'transport': transport.name},
        )

    def encoded_transport_script(
        self,
        userservice: 'models.UserService',
        transport: 'models.Transport',
        ip: str,
        os: 'types.os.DetectedOsInfo',  # pylint: disable=redefined-outer-name
        user: 'models.User',
        password: str,
        request: 'ExtendedHttpRequestWithUser',
    ) -> types.transports.TransportScript:
        """
        Encodes the script so the client can understand it
        """
        transport_script = self.get_transport_script(userservice, transport, ip, os, user, password, request)
        logger.debug('Transport script: %s', transport_script)

        return types.transports.TransportScript(
            script=codecs.encode(codecs.encode(transport_script.script.encode(), 'bz2'), 'base64')
            .decode()
            .replace('\n', ''),
            signature_b64=transport_script.signature_b64,
            parameters=transport_script.parameters,
        )

    def get_relative_script(
        self, scriptname: str, params: collections.abc.Mapping[str, typing.Any]
    ) -> types.transports.TransportScript:
        """Returns a script that will be executed on client, but will be downloaded from server

        Args:
            scriptname: Name of the script to be downloaded, relative path (i.e. 'scripts/direct/transport.py')
            params: Parameters for the return tuple
        """
        # Reads script and signature
        import os  # pylint: disable=import-outside-toplevel

        base_path = os.path.dirname(
            sys.modules[self.__module__].__file__ or 'not_found'
        )  # Will raise if not found

        with open(os.path.join(base_path, scriptname), 'r', encoding='utf8') as script_file:
            script = script_file.read()
        with open(os.path.join(base_path, scriptname + '.signature'), 'r', encoding='utf8') as signature_file:
            signature = signature_file.read()

        return types.transports.TransportScript(
            script=script,
            script_type='python',
            signature_b64=signature,
            parameters=params,
        )

    def get_script(
        self,
        osname: str,
        type: typing.Literal['tunnel', 'direct'],
        params: collections.abc.Mapping[str, typing.Any],
    ) -> types.transports.TransportScript:
        """
        Returns a script for the given os and type
        """
        return self.get_relative_script(f'scripts/{osname.lower()}/{type}.py', params)

    def get_link(
        self,
        userservice: 'models.UserService',
        transport: 'models.Transport',
        ip: str,
        os: 'types.os.DetectedOsInfo',  # pylint: disable=redefined-outer-name
        user: 'models.User',
        password: str,
        request: 'ExtendedHttpRequestWithUser',
    ) -> str:
        """
        Must override if transport does provides its own link
        If transport provides own link, this method provides the link itself
        """
        return 'https://www.udsenterprise.com'

    def update_link_window(
        self,
        link: str,
        *,
        on_same_window: bool = False,
        on_new_window: bool = False,
        uuid: typing.Optional[str] = None,
        default_uuid: typing.Optional[str] = None,
    ) -> str:
        uuid = uuid or self.get_uuid()
        default_uuid = default_uuid or self.get_uuid()

        amp = '&' if '?' in link else '?'

        if not on_new_window and not on_same_window:
            return f'{link}{amp}{consts.transports.ON_SAME_WINDOW_VAR}={default_uuid}'

        if on_same_window:
            return f'{link}{amp}{consts.transports.ON_SAME_WINDOW_VAR}=yes'

        # Must be on new window
        return f'{link}{amp}{consts.transports.ON_NEW_WINDOW_VAR}={uuid}'

        return link
