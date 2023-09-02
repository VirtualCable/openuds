# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2023 Virtual Cable S.L.U.
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
import logging
import typing

from django.db import models

from uds.core import auths, environment
from uds.core.util import log, net
from uds.core.util.state import State

from ..core.consts import NEVER
from .managed_object_model import ManagedObjectModel
from .network import Network
from .tag import TaggingMixin

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.models import Group, Network, User


logger = logging.getLogger(__name__)


class Authenticator(ManagedObjectModel, TaggingMixin):
    """
    This class represents an Authenticator inside the platform.
    Sample authenticators are LDAP, Active Directory, SAML, ...
    """

    # Constants for Visibility
    VISIBLE = 'v'
    HIDDEN = 'h'
    DISABLED = 'd'

    # net_filter
    # Note: this are STANDARD values used on "default field" networks on RESP API
    # Named them for better reading, but cannot be changed, since they are used on RESP API
    NO_FILTERING = 'n'
    ALLOW = 'a'
    DENY = 'd'

    priority = models.IntegerField(default=0, db_index=True)
    small_name = models.CharField(max_length=32, default='', db_index=True)
    state = models.CharField(max_length=1, default=VISIBLE, db_index=True)
    # "visible" is removed from 4.0, state will do this functionality, but is more flexible
    net_filtering = models.CharField(max_length=1, default=NO_FILTERING, db_index=True)

    # "fake" relations declarations for type checking
    # objects: 'models.manager.Manager["Authenticator"]'
    users: 'models.manager.RelatedManager[User]'
    groups: 'models.manager.RelatedManager[Group]'

    networks: 'models.manager.RelatedManager[Network]'
    # MFA associated to this authenticator. Can be null
    mfa = models.ForeignKey(
        'MFA',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='authenticators',
    )

    class Meta(ManagedObjectModel.Meta):  # pylint: disable=too-few-public-methods
        """
        Meta class to declare default order
        """

        ordering = ('name',)
        app_label = 'uds'

    def getInstance(self, values=None) -> auths.Authenticator:
        """
        Instantiates the object this record contains.

        Every single record of Provider model, represents an object.

        Args:
           values (list): Values to pass to constructor. If no values are specified,
                          the object is instantiated empty and them deserialized from stored data.

        Returns:
            The instance Instance of the class this provider represents

        Raises:
        """
        if self.id is None:
            return auths.Authenticator(environment.Environment.getTempEnv(), values, dbAuth=self)

        auType = self.getType()
        env = self.getEnvironment()
        auth = auType(env, values, dbAuth=self)
        self.deserialize(auth, values)
        return auth

    def getType(self) -> typing.Type[auths.Authenticator]:
        """
        Get the type of the object this record represents.

        The type is Python type, it obtains this type from AuthsFactory and associated record field.

        Returns:
            The python type for this record object

        :note: We only need to get info from this, not access specific data (class specific info)
        """
        # If type is not registered (should be, but maybe a database inconsistence), consider this a "base empty auth"
        return auths.factory().lookup(self.data_type) or auths.Authenticator

    def getOrCreateUser(self, username: str, realName: typing.Optional[str] = None) -> 'User':
        """
        Used to get or create a new user at database associated with this authenticator.

        This user has all parameter default, that are:
        * 'real_name':realName
        * 'last_access':NEVER
        * 'state':State.ACTIVE

        Args:
           username: The username to create and associate with this auhtenticator

           realName: If None, it will be the same that username. If otherwise especified, it will be the default real_name (field)

        Returns:
            True if the ip can access this Transport.

            False if the ip can't access this Transport.

            The ip check is done this way:
            * If The associated network is empty, the result is always True
            * If the associated network is not empty, and nets_positive (field) is True, the result will be True if
            the ip is contained in any subnet associated with this transport.
            * If the associated network is empty, and nets_positive (field) is False, the result will be True if
            the ip is NOT contained in ANY subnet associated with this transport.

        Raises:
        """
        user: 'User'
        realName = realName or username
        user, _ = self.users.get_or_create(
            name=username,
            defaults={
                'real_name': realName,
                'last_access': NEVER,
                'state': State.ACTIVE,
            },
        )
        if (
            user.real_name.strip() == '' or user.name.strip() == user.real_name.strip()
        ) and realName != user.real_name:
            user.real_name = realName or ''
            user.save(update_fields=['real_name'])

        return user

    def isValidUser(self, username: str, falseIfNotExists: bool = True) -> bool:
        """
        Checks the validity of an user

        Args:
            username: Name of the user to check

            falseIfNotExists: Defaults to True. It is used so we can return a value defined by caller.

            One example of falseIfNotExists using as True is for checking that the user is active or it doesn't exists.

        Returns:
            True if it exists and is active, falseIfNotExists (param) if it doesn't exists

        This is done so we can check non existing or non blocked users (state != Active, or do not exists)
        """
        try:
            usr: 'User' = self.users.get(name=username)
            return State.isActive(usr.state)
        except Exception:
            return falseIfNotExists

    def validForIp(self, ipStr: str) -> bool:
        """
        Checks if this transport is valid for the specified IP.

        Args:
           ip: Numeric ip address to check validity for. (xxx.xxx.xxx.xxx).

        Returns:
            True if the ip can access this Transport.

            False if the ip can't access this Transport.

            The check is done using the net_filtering field.
            if net_filtering is 'd' (disabled), then the result is always True
            if net_filtering is 'a' (allow), then the result is True is the ip is in the networks
            if net_filtering is 'd' (deny), then the result is True is the ip is not in the networks
        Raises:

        :note: Ip addresses has been only tested with IPv4 addresses
        """
        if self.net_filtering == Authenticator.NO_FILTERING:
            return True
        ip, version = net.ipToLong(ipStr)
        # Allow
        exists = self.networks.filter(start__lte=Network.hexlify(ip), end__gte=Network.hexlify(ip), version=version).exists()
        if self.net_filtering == Authenticator.ALLOW:
            return exists
        # Deny, must not be in any network
        return not exists

    @staticmethod
    def all() -> 'models.QuerySet[Authenticator]':
        """
        Returns all authenticators ordered by priority
        """
        return Authenticator.objects.all().order_by('priority')

    @staticmethod
    def getByTag(tag=None) -> typing.Iterable['Authenticator']:
        """
        Gets authenticator by tag name.
        Special tag name "disabled" is used to exclude customAuth
        """
        # pylint: disable=import-outside-toplevel
        from uds.core.util.config import GlobalConfig

        if tag is not None:
            authsList = Authenticator.objects.filter(small_name=tag).order_by('priority', 'name')
            if not authsList.exists():
                authsList = Authenticator.objects.all().order_by('priority', 'name')
                # If disallow global login (use all auths), get just the first by priority/name
                if GlobalConfig.DISALLOW_GLOBAL_LOGIN.getBool(False) is True:
                    authsList = authsList[:1]  # type: ignore  # Slicing is not supported by pylance right now
            logger.debug(authsList)
        else:
            authsList = Authenticator.objects.all().order_by('priority', 'name')

        for auth in authsList:
            if auth.getType() and (not auth.getType().isCustom() or tag != 'disabled'):
                yield auth

    @staticmethod
    def beforeDelete(sender, **kwargs) -> None:  # pylint: disable=unused-argument
        """
        Used to invoke the Service class "Destroy" before deleting it from database.

        The main purpuse of this hook is to call the "destroy" method of the object to delete and
        to clear related data of the object (environment data such as own storage, cache, etc...

        :note: If destroy raises an exception, the deletion is not taken.
        """
        # pylint: disable=import-outside-toplevel
        from uds.core.util.permissions import clean

        toDelete = kwargs['instance']

        logger.debug('Before delete auth %s', toDelete)

        # Only tries to get instance if data is not empty
        if toDelete.data != '':
            s = toDelete.getInstance()
            s.destroy()
            s.env.clearRelatedData()

        # Clears related logs
        log.clearLogs(toDelete)

        # Clears related permissions
        clean(toDelete)

    # returns CSV header
    @staticmethod
    def getCSVHeader(sep: str = ',') -> str:
        return sep.join(
            [
                'name',
                'type',
                'users',
                'groups',
            ]
        )

    # Return record as csv line using separator (default: ',')
    def toCsv(self, sep: str = ',') -> str:
        return sep.join(
            [
                self.name,
                self.data_type,
                str(self.users.count()),
                str(self.groups.count()),
            ]
        )

    def __str__(self):
        return f'{self.name} of type {self.data_type} (id:{self.id})'


# Connects a pre deletion signal to Authenticator
models.signals.pre_delete.connect(Authenticator.beforeDelete, sender=Authenticator)
