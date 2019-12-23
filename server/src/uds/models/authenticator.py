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
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing

from django.db import models
from django.db.models import signals

from uds.core import auths
from uds.core import environment
from uds.core.util import log
from uds.core.util.state import State

from .managed_object_model import ManagedObjectModel
from .tag import TaggingMixin
from .util import NEVER

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from .user import User
    from django.db.models import QuerySet  # pylint: disable=ungrouped-imports


logger = logging.getLogger(__name__)


class Authenticator(ManagedObjectModel, TaggingMixin):
    """
    This class represents an Authenticator inside the platform.
    Sample authenticators are LDAP, Active Directory, SAML, ...
    """

    priority = models.IntegerField(default=0, db_index=True)
    small_name = models.CharField(max_length=32, default='', db_index=True)
    visible = models.BooleanField(default=True)

    class Meta(ManagedObjectModel.Meta):  # pylint: disable=too-few-public-methods
        """
        Meta class to declare default order
        """
        ordering = ('name',)
        app_label = 'uds'

    def getInstance(self, values=None) ->  auths.Authenticator:
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
            return auths.Authenticator(self, environment.Environment.getTempEnv(), values)

        auType = self.getType()
        env = self.getEnvironment()
        auth = auType(self, env, values)
        self.deserialize(auth, values)
        return auth

    def getType(self) -> typing.Type[auths.Authenticator]:
        """
        Get the type of the object this record represents.

        The type is Python type, it obtains this type from ServiceProviderFactory and associated record field.

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
        realName = realName if realName is None else username
        user, _ = self.users.get_or_create(name=username, defaults={'real_name': realName, 'last_access': NEVER, 'state': State.ACTIVE})
        if (user.real_name.strip() == '' or user.name.strip() == user.real_name.strip()) and realName != user.real_name:
            user.real_name = realName
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

    @staticmethod
    def all() -> 'QuerySet':
        """
        Returns all authenticators ordered by priority
        """
        return Authenticator.objects.all().order_by('priority')

    @staticmethod
    def getByTag(tag=None) -> typing.List['Authenticator']:
        """
        Gets authenticator by tag name.
        Special tag name "disabled" is used to exclude customAuth
        """
        from uds.core.util.config import GlobalConfig

        if tag is not None:
            authsList: 'QuerySet' = Authenticator.objects.filter(small_name=tag).order_by('priority', 'name')
            if not authsList:
                authsList = Authenticator.objects.all().order_by('priority', 'name')
                # If disallow global login (use all auths), get just the first by priority/name
                if GlobalConfig.DISALLOW_GLOBAL_LOGIN.getBool(False) is True:
                    authsList = authsList[0:1]
            logger.debug(authsList)
        else:
            authsList = Authenticator.objects.all().order_by('priority', 'name')

        return [auth for auth in authsList if auth.getType() and (auth.getType().isCustom() is False or tag != 'disabled')]

    @staticmethod
    def beforeDelete(sender, **kwargs):
        """
        Used to invoke the Service class "Destroy" before deleting it from database.

        The main purpuse of this hook is to call the "destroy" method of the object to delete and
        to clear related data of the object (environment data such as own storage, cache, etc...

        :note: If destroy raises an exception, the deletion is not taken.
        """
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

    def __str__(self):
        return u"{0} of type {1} (id:{2})".format(self.name, self.data_type, self.id)


# Connects a pre deletion signal to Authenticator
signals.pre_delete.connect(Authenticator.beforeDelete, sender=Authenticator)
