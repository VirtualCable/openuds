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

from .group import Group
from .groups_manager import GroupsManager

# Imports for type checking
if typing.TYPE_CHECKING:
    from .authenticator import Authenticator as AuthenticatorInstance
    from uds import models


logger = logging.getLogger(__name__)


class User:
    """
    An user represents a database user, associated with its authenticator (instance)
    and its groups.
    """

    _cached_manager: 'AuthenticatorInstance'
    _groups_manager: 'GroupsManager'
    _db_user: 'models.User'
    _groups: typing.Optional[list[Group]]

    def __init__(self, db_user: 'models.User') -> None:
        self._cached_manager = db_user.get_manager()
        self._groups_manager = GroupsManager(db_user.manager)
        self._db_user = db_user
        self._groups = None

    def groups(self) -> list[Group]:
        """
        Returns the valid groups for this user.
        To do this, it will validate groups through authenticator instance using
        :py:meth:`uds.core.auths.Authenticator.getGroups` method.

        :note: Once obtained valid groups, it caches them until object removal.
        """
        from uds.models.user import (  # pylint: disable=import-outside-toplevel
            User as DBUser,
        )

        if self._groups is None:
            if self._cached_manager.external_source:
                self._cached_manager.get_groups(self._db_user.name, self._groups_manager)
                self._groups = list(self._groups_manager.enumerate_valid_groups())
                logger.debug(self._groups)
                # This is just for updating "cached" data of this user, we only get real groups at login and at modify user operation
                usr = DBUser.objects.get(pk=self._db_user.id)  # @UndefinedVariable
                usr.groups.set((g.db_obj().id for g in self._groups if g.db_obj().is_meta is False))  # type: ignore
            else:
                # From db
                usr = DBUser.objects.get(pk=self._db_user.id)  # @UndefinedVariable
                self._groups = [Group(g) for g in usr.get_groups()]
        return self._groups

    def manager(self) -> 'AuthenticatorInstance':
        """
        Returns the authenticator instance
        """
        return self._cached_manager

    def db_obj(self) -> 'models.User':
        """
        Returns the database user
        """
        return self._db_user
