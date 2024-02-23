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
import collections.abc

from django.db import models

from uds.core.types.states import State
from uds.core.util import log

from .uuid_model import UUIDModel
from .authenticator import Authenticator
from .user import User
from ..core.util.model import sql_datetime

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core import auths
    from uds.models import ServicePool, Permissions

logger = logging.getLogger(__name__)


# pylint: disable=no-member
class Group(UUIDModel):
    """
    This class represents a group, associated with one authenticator
    """

    manager = models.ForeignKey(
        Authenticator, on_delete=models.CASCADE, related_name='groups'
    )
    name = models.CharField(max_length=128, db_index=True)
    state = models.CharField(max_length=1, default=State.ACTIVE, db_index=True)
    comments = models.CharField(max_length=256, default='')
    users: 'models.ManyToManyField[User, Group]' = models.ManyToManyField(User, related_name='groups')
    is_meta = models.BooleanField(default=False, db_index=True)
    # meta_if_any means that if an user belongs to ANY of the groups, it will be considered as belonging to this group
    # if it is false, the user must belong to ALL of the groups to be considered as belonging to this group
    meta_if_any = models.BooleanField(default=False)
    groups: 'models.ManyToManyField[Group, Group]' = models.ManyToManyField('self', symmetrical=False)
    created = models.DateTimeField(default=sql_datetime, blank=True)
    skip_mfa = models.CharField(max_length=1, default=State.INACTIVE, db_index=True)

    # "fake" declarations for type checking
    # objects: 'models.manager.Manager["Group"]'
    deployedServices: 'models.manager.RelatedManager[ServicePool]'  # Legacy name, will keep this forever :)
    permissions: 'models.manager.RelatedManager[Permissions]'
    
    @property
    def service_pools(self) -> 'models.manager.RelatedManager[ServicePool]':
        """
        Returns the service pools that this group has access to
        """
        return self.deployedServices

    class Meta:  # pyright: ignore
        """
        Meta class to declare default order and unique multiple field index
        """

        ordering = ('name',)
        app_label = 'uds'
        constraints = [
            models.UniqueConstraint(
                fields=['manager', 'name'], name='u_grp_manager_name'
            )
        ]

    @property
    def pretty_name(self) -> str:
        return self.name + '@' + self.manager.name

    def get_manager(self) -> 'auths.Authenticator':
        """
        Returns the authenticator object that owns this user.

        :note: The returned value is an instance of the authenticator class used to manage this user, not a db record.
        """
        return self.manager.get_instance()

    def __str__(self) -> str:
        if self.is_meta:
            return f'Meta group {self.name}(id:{self.id}) with groups {list(self.groups.all())}'

        return f'Group {self.name}(id:{self.id}) from auth {self.manager.name}'

    @staticmethod
    def pre_delete(sender: typing.Any, **kwargs: typing.Any) -> None:  # pylint: disable=unused-argument
        """
        Used to invoke the Service class "Destroy" before deleting it from database.

        In this case, this is a dummy method, waiting for something useful to do :-)

        :note: If destroy raises an exception, the deletion is not taken.
        """
        to_delete: 'Group' = kwargs['instance']
        # Todelete is a group

        # We invoke removeGroup. If this raises an exception, group will not
        # be removed
        to_delete.get_manager().remove_group(to_delete.name)

        # Clears related logs
        log.clear_logs(to_delete)

        logger.debug('Deleted group %s', to_delete)


models.signals.pre_delete.connect(Group.pre_delete, sender=Group)
