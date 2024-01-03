# pylint: disable=unused-argument  # this has a lot of "default" methods, so we need to ignore unused arguments most of the time

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
import datetime
import random
import enum
import hashlib
import logging
import typing
import collections.abc

from django.utils.translation import gettext_noop as _, gettext
from uds.core.module import Module
from uds.core.util.model import sql_datetime
from uds.models.network import Network
from uds.core import exceptions

if typing.TYPE_CHECKING:
    from uds.core.environment import Environment
    from uds.core.types.request import ExtendedHttpRequest
    from uds.models import User

logger = logging.getLogger(__name__)


class LoginAllowed(enum.StrEnum):
    """
    This enum is used to know if the MFA code was sent or not.
    """

    ALLOWED = '0'
    DENIED = '1'
    ALLOWED_IF_IN_NETWORKS = '2'
    DENIED_IF_IN_NETWORKS = '3'

    @staticmethod
    def checkAction(
        action: 'LoginAllowed|str',
        request: 'ExtendedHttpRequest',
        networks: typing.Optional[collections.abc.Iterable[str]] = None,
    ) -> bool:
        def checkIp() -> bool:
            if networks is None:
                return True  # No network restrictions, so we allow
            return any(
                i.contains(request.ip)
                for i in Network.objects.filter(uuid__in=list(networks))
            )

        if isinstance(action, str):
            action = LoginAllowed(action)

        return {
            LoginAllowed.ALLOWED: True,
            LoginAllowed.DENIED: False,
            LoginAllowed.ALLOWED_IF_IN_NETWORKS: checkIp(),
            LoginAllowed.DENIED_IF_IN_NETWORKS: not checkIp(),
        }.get(action, False)

    @staticmethod
    def valuesForSelect() -> collections.abc.Mapping[str, str]:
        return {
            LoginAllowed.ALLOWED.value: gettext('Allow user login'),
            LoginAllowed.DENIED.value: gettext('Deny user login'),
            LoginAllowed.ALLOWED_IF_IN_NETWORKS.value: gettext(
                'Allow user to login if it IP is in the networks list'
            ),
            LoginAllowed.DENIED_IF_IN_NETWORKS.value: gettext(
                'Deny user to login if it IP is in the networks list'
            ),
        }


class MFA(Module):
    """
    this class provides an abstraction of a Multi Factor Authentication
    """

    # informational related data
    # : Name of type, used at administration interface to identify this
    # : notifier type (e.g. "Email", "SMS", etc.)
    # : This string will be translated when provided to admin interface
    # : using gettext, so you can mark it as "_" at derived classes (using gettext_noop)
    # : if you want so it can be translated.
    typeName: typing.ClassVar[str] = _('Base MFA')

    # : Name of type used by Managers to identify this type of service
    # : We could have used here the Class name, but we decided that the
    # : module implementator will be the one that will provide a name that
    # : will relation the class (type) and that name.
    typeType: typing.ClassVar[str] = 'baseMFA'

    # : Description shown at administration level for this authenticator.
    # : This string will be translated when provided to admin interface
    # : using gettext, so you can mark it as "_" at derived classes (using gettext_noop)
    # : if you want so it can be translated.
    typeDescription: typing.ClassVar[str] = _('Base MFA')

    # : Icon file, used to represent this authenticator at administration interface
    # : This file should be at same folder as this class is, except if you provide
    # : your own :py:meth:uds.core.module.BaseModule.icon method.
    iconFile: typing.ClassVar[str] = 'mfa.png'

    class RESULT(enum.IntEnum):
        """
        This enum is used to know if the MFA code was sent or not.
        """

        OK = 1
        ALLOWED = 2

    def __init__(self, environment: 'Environment', values: Module.ValuesType):
        super().__init__(environment, values)
        self.initialize(values)

    def initialize(self, values: Module.ValuesType) -> None:
        """
        This method will be invoked from __init__ constructor.
        This is provided so you don't have to provide your own __init__ method,
        and invoke base methods.
        This will get invoked when all initialization stuff is done

        Args:
            values: If values is not none, this object is being initialized
            from administration interface, and not unmarshal will be done.
            If it's None, this is initialized internally, and unmarshal will
            be called after this.

        Default implementation does nothing
        """

    def label(self) -> str:
        """
        This method will be invoked from the MFA form, to know the human name of the field
        that will be used to enter the MFA code.
        """
        return 'MFA Code'

    def html(self, request: 'ExtendedHttpRequest', userId: str, username: str) -> str:
        """
        This method will be invoked from the MFA form, to know the HTML that will be presented
        to the user below the MFA code form.

        Args:
            userId: Id of the user that is requesting the MFA code
            request: Request object, so you can get more information

        Returns:
            HTML to be presented to the user along with the MFA code form
        """
        return ''

    def emptyIndentifierAllowedToLogin(
        self, request: 'ExtendedHttpRequest'
    ) -> typing.Optional[bool]:
        """
        If this method returns True, an user that has no "identifier" is allowed to login without MFA
        Returns:
            True: If an user that has no "identifier" is allowed to login without MFA
            False: If an user that has no "identifier" is not allowed to login without MFA
            None: Process request, let the class decide if the user is allowed to login without MFA
        """
        return True

    def sendCode(
        self,
        request: 'ExtendedHttpRequest',
        userId: str,
        username: str,
        identifier: str,
        code: str,
    ) -> 'MFA.RESULT':
        """
        This method will be invoked from "process" method, to send the MFA code to the user.
        If returns MFA.RESULT.OK, the MFA code was sent.
        If returns MFA.RESULT.ALLOW, the MFA code was not sent, the user does not need to enter the MFA code.
        If raises an error, the MFA code was not sent, and the user needs to enter the MFA code.
        """
        logger.error('MFA.sendCode not implemented')
        raise exceptions.auth.MFAError('MFA.sendCode not implemented')

    def _getData(
        self, request: 'ExtendedHttpRequest', userId: str
    ) -> typing.Optional[tuple[datetime.datetime, str]]:
        """
        Internal method to get the data from storage
        """
        storageKey = request.ip + userId
        return self.storage.getPickle(storageKey)

    def _removeData(self, request: 'ExtendedHttpRequest', userId: str) -> None:
        """
        Internal method to remove the data from storage
        """
        storageKey = request.ip + userId
        self.storage.remove(storageKey)

    def _putData(self, request: 'ExtendedHttpRequest', userId: str, code: str) -> None:
        """
        Internal method to put the data into storage
        """
        storageKey = request.ip + userId
        self.storage.putPickle(storageKey, (sql_datetime(), code))

    def process(
        self,
        request: 'ExtendedHttpRequest',
        userId: str,
        username: str,
        identifier: str,
        validity: typing.Optional[int] = None,
    ) -> 'MFA.RESULT':
        """
        This method will be invoked from the MFA form, to send the MFA code to the user.
        The identifier where to send the code, will be obtained from "mfaIdentifier" method.
        Default implementation generates a random code and sends invokes "sendCode" method.

        If returns MFA.RESULT.OK, the MFA code was sent.
        If returns MFA.RESULT.ALLOW, the MFA code was not sent, the user does not need to enter the MFA code.
        If raises an error, the MFA code was not sent, and the user needs to enter the MFA code.

        Args:
            request: The request object
            userId: An unique, non authenticator dependant, id for the user (at this time, it's sha3_256 of user + authenticator)
            username: The user name, the one used to login
            identifier: The identifier where to send the code (phone, email, etc)
            validity: The validity of the code in seconds. If None, the default value will be used.

        Returns:
            MFA.RESULT.OK if the code was already sent
            MFA.RESULT.ALLOW if the user does not need to enter the MFA code (i.e. fail to send the code)
            Raises an error if the code was not sent and was required to be sent
        """
        # try to get the stored code
        data = self._getData(request, userId)
        validity = validity if validity is not None else 0
        try:
            if data and validity:
                # if we have a stored code, check if it's still valid
                if data[0] + datetime.timedelta(seconds=validity) > sql_datetime():
                    # if it's still valid, just return without sending a new one
                    return MFA.RESULT.OK
        except Exception:
            # if we have a problem, just remove the stored code
            self._removeData(request, userId)

        # Generate a 6 digit code (0-9)
        code = ''.join(random.SystemRandom().choices('0123456789', k=6))
        logger.debug('Generated OTP is %s', code)

        # Send the code to the user
        # May raise an exception if the code was not sent and is required to be sent
        # pylint: disable=assignment-from-no-return
        result = self.sendCode(request, userId, username, identifier, code)

        # Store the code in the database, own storage space, if no exception was raised
        self._putData(request, userId, code)

        return result

    def validate(
        self,
        request: 'ExtendedHttpRequest',
        userId: str,
        username: str,
        identifier: str,
        code: str,
        validity: typing.Optional[int] = None,
    ) -> None:
        """
        If this method is provided by an authenticator, the user will be allowed to enter a MFA code
        You must raise an "exceptions.MFAError" if the code is not valid.

        Args:
            request: The request object
            userId: An unique, non authenticator dependant, id for the user (at this time, it's sha3_256 of user + authenticator)
            username: The user name, the one used to login
            identifier: The identifier where to send the code (phone, email, etc)
            code: The code entered by the user
            validity: The validity of the code in seconds. If None, the default value will be used.

        Returns:
            None if the code is valid
            Raises an error if the code is not valid ("exceptions.MFAError")
        """
        # Validate the code
        try:
            err = _('Invalid MFA code')

            data = self._getData(request, userId)
            if data and len(data) == 2:
                validity = validity if validity is not None else 0
                if (
                    validity > 0
                    and data[0] + datetime.timedelta(seconds=validity)
                    < sql_datetime()
                ):
                    # if it is no more valid, raise an error
                    # Remove stored code and raise error
                    self._removeData(request, userId)
                    raise exceptions.auth.MFAError('MFA Code expired')

                # Check if the code is valid
                if data[1] == code:
                    # Code is valid, remove it from storage
                    self._removeData(request, userId)
                    return
        except Exception as e:
            # Any error means invalid code
            err = str(e)

        raise exceptions.auth.MFAError(err)

    def resetData(
        self,
        userId: str,
    ) -> None:
        """
        This method allows to reset the MFA state of an user.
        Normally, this will do nothing, but for persistent MFA data (as Google Authenticator), this will remove the data.
        """

    @staticmethod
    def getUserId(user: 'User') -> str:
        """
        Composes an unique, mfa dependant, id for the user (at this time, it's sha3_256 of user + mfa)
        """
        mfa = user.manager.mfa
        if not mfa:
            raise exceptions.auth.MFAError('MFA is not enabled')

        return hashlib.sha3_256(
            (user.name + (user.uuid or '') + mfa.uuid).encode()
        ).hexdigest()
