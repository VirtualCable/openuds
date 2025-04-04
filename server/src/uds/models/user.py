# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2021 Virtual Cable S.L.U.
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
from django.db.models import Count, Q, signals
from uds.core import auths, mfas, types, consts
from uds.core.util import log, storage, properties

from .authenticator import Authenticator
from ..core.consts import NEVER
from ..core.util.model import sql_now
from .uuid_model import UUIDModel

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.models import Group, UserService, Permissions
    from django.db.models.manager import RelatedManager


logger = logging.getLogger(__name__)


# pylint: disable=no-member
class User(UUIDModel, properties.PropertiesMixin):
    """
    This class represents a single user, associated with one authenticator
    """

    manager = models.ForeignKey(Authenticator, on_delete=models.CASCADE, related_name='users')
    name = models.CharField(max_length=128, db_index=True)
    real_name = models.CharField(max_length=128)
    comments = models.CharField(max_length=256)
    state = models.CharField(max_length=1, db_index=True)
    password = models.CharField(
        max_length=128, default=''
    )  # Only used on "internal" sources or sources that "needs password"
    mfa_data = models.CharField(max_length=128, default='')  # Only used on "internal" sources
    staff_member = models.BooleanField(default=False)  # Staff members can login to admin
    is_admin = models.BooleanField(default=False)  # is true, this is a super-admin
    last_access = models.DateTimeField(default=NEVER)
    parent = models.CharField(max_length=50, default=None, null=True)
    created = models.DateTimeField(default=sql_now, blank=True)

    # "fake" declarations for type checking
    # objects: 'models.manager.Manager["User"]'
    groups: 'RelatedManager[Group]'
    userServices: 'RelatedManager[UserService]'
    permissions: 'RelatedManager[Permissions]'

    class Meta(UUIDModel.Meta):  # pylint: disable=too-few-public-methods
        """
        Meta class to declare default order and unique multiple field index
        """

        ordering = ('name',)
        app_label = 'uds'
        constraints = [models.UniqueConstraint(fields=['manager', 'name'], name='u_usr_manager_name')]

    # For properties
    def get_owner_id_and_type(self) -> tuple[str, str]:
        return self.uuid, 'user'

    def get_username_for_auth(self) -> str:
        """
        Return the username transformed for authentication.
        This transformation is used for transports only, not for transforming
        anything at login time. Transports that will need the username, will invoke
        this method.
        The manager (an instance of uds.core.auths.Authenticator), can transform the database stored username
        so we can, for example, add @domain in some cases.
        """
        return self.get_manager().get_for_auth(self.name)

    @property
    def pretty_name(self) -> str:
        if self.manager.name:
            return self.name + '@' + self.manager.name
        return self.name

    def get_manager(self) -> 'auths.Authenticator':
        """
        Returns the authenticator object that owns this user.

        :note: The returned value is an instance of the authenticator class used to manage this user, not a db record.
        """
        return self.manager.get_instance()

    # Utility for logging
    def log(
        self,
        message: str,
        level: types.log.LogLevel = types.log.LogLevel.INFO,
        source: types.log.LogSource = types.log.LogSource.INTERNAL,
    ) -> None:
        log.log(self, level, message, source)

    def is_staff(self) -> bool:
        """
        Return true if this user is admin or staff member
        """
        return self.staff_member or self.is_admin

    def get_role(self) -> consts.UserRole:
        """
        Returns the role of the user
        """
        if self.pk is None:
            return consts.UserRole.ANONYMOUS

        if self.is_admin:
            return consts.UserRole.ADMIN
        if self.staff_member:
            return consts.UserRole.STAFF

        return consts.UserRole.USER

    def can_access(self, role: consts.UserRole) -> bool:
        """
        Returns true if the user has more or equal role than the one passed as argument
        """
        return self.get_role().can_access(role)

    def update_last_access(self) -> None:
        """
        Updates the last access for this user with the current time of the sql server
        """
        self.last_access = sql_now()
        self.save(update_fields=['last_access'])

    def logout(self, request: 'types.requests.ExtendedHttpRequest') -> types.auth.AuthenticationResult:
        """
        Invoked to log out this user
        Returns the url where to redirect user, or None if default url will be used
        """
        return self.get_manager().logout(request, self.name)

    def get_groups(self) -> typing.Generator['Group', None, None]:
        """
        returns the groups (and metagroups) this user belongs to
        """
        if self.parent:
            try:
                usr = User.objects.prefetch_related('authenticator', 'groups').get(uuid=self.parent)
            except Exception:  # If parent do not exists
                usr = self
        else:
            usr = self

        grps: list[int] = []

        for g in usr.groups.filter(is_meta=False):
            grps.append(g.id)
            yield g

        # Locate metagroups
        for g in (
            self.manager.groups.filter(is_meta=True)
            .annotate(number_groups=Count('groups'))  # g.groups.count()
            .annotate(
                number_belongs_meta=Count('groups', filter=Q(groups__id__in=grps))
            )  # g.groups.filter(id__in=grps).count()
        ):
            number_of_groups_belonging_in_meta: int = typing.cast(
                typing.Any, g
            ).number_belongs_meta  # Anotated field

            logger.debug('gn = %s', number_of_groups_belonging_in_meta)
            logger.debug('groups count: %s', typing.cast(typing.Any, g).number_groups)  # Anotated field

            if g.meta_if_any is True and number_of_groups_belonging_in_meta > 0:
                number_of_groups_belonging_in_meta = typing.cast(typing.Any, g).number_groups  # Anotated field

            logger.debug('gn after = %s', number_of_groups_belonging_in_meta)

            # If a meta group is empty, all users belongs to it. we can use gn != 0 to check that if it is empty, is not valid
            if number_of_groups_belonging_in_meta == typing.cast(typing.Any, g).number_groups:
                # This group matches
                yield g

    def __str__(self) -> str:
        return f'{self.pretty_name} (id:{self.id})'

    def clean_related_data(self) -> None:
        """
        Cleans up all related external data, such as mfa data, etc
        """
        # If has mfa, remove related data
        if self.manager.mfa:
            self.manager.mfa.get_instance().reset_data(mfas.MFA.get_user_unique_id(self))

    @staticmethod
    def pre_delete(sender: typing.Any, **kwargs: typing.Any) -> None:  # pylint: disable=unused-argument
        """
        Used to invoke the Service class "Destroy" before deleting it from database.

        In this case, this method ensures that the user has no userservices assigned and, if it has,
        mark those services for removal

        :note: If destroy raises an exception, the deletion is not taken.
        """
        to_delete: User = kwargs['instance']

        # first, we invoke removeUser. If this raises an exception, user will not
        # be removed
        to_delete.get_manager().remove_user(to_delete.name)

        # If has mfa, remove related data
        to_delete.clean_related_data()

        # Remove related stored values
        try:
            storage.StorageAsDict(
                owner='manager' + str(to_delete.manager.uuid), group=None, atomic=False
            ).clear()
        except Exception:
            logger.exception('Removing stored data')
        # now removes all "child" of this user, if it has children
        User.objects.filter(parent=to_delete.id).delete()

        # Remove related logs
        log.clear_logs(to_delete)

        # Removes all user services assigned to this user (unassign it and mark for removal)
        for us in to_delete.userServices.all():
            us.assign_to(None)
            us.release()

        logger.debug('Deleted user %s', to_delete)


# Connect to pre delete signal
signals.pre_delete.connect(User.pre_delete, sender=User)

# Connects the properties signals
properties.PropertiesMixin.setup_signals(User)
