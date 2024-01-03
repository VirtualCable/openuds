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
import collections.abc
import dataclasses
import logging
import re
import typing

from uds.core.util.state import State

from .group import Group

if typing.TYPE_CHECKING:
    from uds.models import Authenticator as DBAuthenticator

logger = logging.getLogger(__name__)

@dataclasses.dataclass(frozen=True)
class _LocalGrp:
    name: str
    group: 'Group'
    is_valid: bool = False
    is_pattern: bool = False

    def matches(self, name: str) -> bool:
        """
        Checks if this group name is equal to the provided name (case)
        """
        return name.casefold() == self.name.casefold()
    
    def replace(self, **kwargs) -> '_LocalGrp':
        return dataclasses.replace(self, **kwargs)


class GroupsManager:
    """
    Manages registered groups for an specific authenticator.

    Most authenticators (except internal database one, that is an special case)
    has their database of users and passwords outside UDS. Think, for example,
    about LDAP. It has its own database of users and groups, and has its own
    correspondence of which user belongs to which group.

    UDS Only knows a subset of this groups, those that the administrator has
    registered inside UDS.

    To manage the equivalence between groups from the authenticator and UDS groups,
    we provide a list of "known groups" by uds. The authenticator then makes the
    correspondence, marking the groups (UDS groups) that the user belongs to as
    valid.

    Managed groups names are compared using case insensitive comparison.
    """

    _groups: list[_LocalGrp]

    def __init__(self, dbAuthenticator: 'DBAuthenticator'):
        """
        Initializes the groups manager.
        The dbAuthenticator is the database record of the authenticator
        to which this groupsManager will be associated
        """
        self._dbAuthenticator = dbAuthenticator
        # We just get active groups, inactive aren't visible to this class
        self._groups = []
        if (
            dbAuthenticator.id
        ):  # If "fake" authenticator (that is, root user with no authenticator in fact)
            for g in dbAuthenticator.groups.filter(state=State.ACTIVE, is_meta=False):
                name = g.name.lower()
                isPattern = name.find('pat:') == 0  # Is a pattern?
                self._groups.append(
                    _LocalGrp(
                        name=name[4:] if isPattern else name,
                        group=Group(g),
                        is_pattern=isPattern,
                    )
                )

    def _indexes_for_mached_groups(self, groupName: str) -> typing.Generator[int, None, None]:
        """
        Returns true if this groups manager contains the specified group name (string)
        """
        name = groupName.lower()
        for n, grp in enumerate(self._groups):
            if grp.is_pattern:
                logger.debug('Group is a pattern: %s', grp)
                try:
                    logger.debug('Match: %s->%s', grp.name, name)
                    if re.search(grp.name, name, re.IGNORECASE) is not None:
                        yield n
                except Exception:
                    logger.exception('Exception in RE')
            else:
                if grp.matches(name):  # If group name matches
                    yield n

    def getGroupsNames(self) -> typing.Generator[str, None, None]:
        """
        Return all groups names managed by this groups manager. The names are returned
        as where inserted inside Database (most probably using administration interface)
        """
        for g in self._groups:
            yield g.group.db_group().name

    def getValidGroups(self) -> typing.Generator['Group', None, None]:
        """
        returns the list of valid groups (:py:class:uds.core.auths.group.Group)
        """
        from uds.models import \
            Group as DBGroup  # pylint: disable=import-outside-toplevel

        valid_id_list: list[int] = []
        for group in self._groups:
            if group.is_valid:
                valid_id_list.append(group.group.db_group().id)
                yield group.group

        # Now, get metagroups and also return them
        for db_group in DBGroup.objects.filter(
            manager__id=self._dbAuthenticator.id, is_meta=True
        ):  # @UndefinedVariable
            gn = db_group.groups.filter(
                id__in=valid_id_list, state=State.ACTIVE
            ).count()
            if db_group.meta_if_any and gn > 0:
                gn = db_group.groups.count()
            if (
                gn == db_group.groups.count()
            ):  # If a meta group is empty, all users belongs to it. we can use gn != 0 to check that if it is empty, is not valid
                # This group matches
                yield Group(db_group)

    def hasValidGroups(self) -> bool:
        """
        Checks if this groups manager has at least one group that has been
        validated (using :py:meth:.validate)
        """
        return any(g.is_valid for g in self._groups)

    def getGroup(self, groupName: str) -> typing.Optional[Group]:
        """
        If this groups manager contains that group manager, it returns the
        :py:class:uds.core.auths.group.Group  representing that group name.
        """
        for group in self._groups:
            if group.matches(groupName):
                return group.group

        return None

    def validate(self, groupName: typing.Union[str, collections.abc.Iterable[str]]) -> None:
        """Validates that the group (or groups) groupName passed in is valid for this group manager.

        It check that the group specified is known by this group manager.

        Args:
           groupName: string, list or tuple of values (strings) to check

        Returns nothing, it changes the groups this groups contains attributes,
        so they reflect the known groups that are considered valid.
        """
        if not isinstance(groupName, str):
            for name in groupName:
                self.validate(name)
        else:
            for index in self._indexes_for_mached_groups(groupName):
                self._groups[index] = self._groups[index].replace(is_valid=True)

    def isValid(self, groupName: str) -> bool:
        """
        Checks if this group name is marked as valid inside this groups manager.
        Returns True if group name is marked as valid, False if it isn't.
        """
        for n in self._indexes_for_mached_groups(groupName):
            if self._groups[n].is_valid:
                return True
        return False

    def __str__(self) -> str:
        return f'Groupsmanager: {self._groups}'
