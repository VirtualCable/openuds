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

from uds.core.types.states import State

from . import group

if typing.TYPE_CHECKING:
    from uds.models import Authenticator as DBAuthenticator

logger = logging.getLogger(__name__)


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

    @dataclasses.dataclass
    class _LocalGrp:
        name: str
        group: 'group.Group'
        is_valid: bool = False
        is_pattern: bool = False

        def matches(self, name: str) -> bool:
            """
            Checks if this group name is equal to the provided name (case)
            """
            if self.is_pattern:
                try:
                    return re.search(self.name, name, re.IGNORECASE) is not None
                except Exception:
                    logger.exception('Exception in RE')
                    return False
            # If not a pattern, just compare
            return name.casefold() == self.name.casefold()

    _groups: list[_LocalGrp]
    _db_auth: 'DBAuthenticator'

    def __init__(self, db_auth: 'DBAuthenticator'):
        """
        Initializes the groups manager.

        Args:
            db_auth: The authenticator to which this GroupsManager will be associated
        """
        self._db_auth = db_auth
        # We just get active groups, inactive aren't visible to this class
        self._groups = []
        if db_auth.id:  # If "fake" authenticator (that is, root user with no authenticator in fact)
            for g in db_auth.groups.filter(state=State.ACTIVE, is_meta=False):
                name = g.name.lower()
                is_pattern_group = name.startswith('pat:')  # Is a pattern?
                self._groups.append(
                    GroupsManager._LocalGrp(
                        name=name[4:] if is_pattern_group else name,
                        group=group.Group(g),
                        is_pattern=is_pattern_group,
                    )
                )

    def _mached_groups(self, group_name: str) -> typing.Generator[_LocalGrp, None, None]:
        """
        Returns true if this groups manager contains the specified group name (string)
        """
        name = group_name.lower()
        yield from (grp for grp in self._groups if grp.matches(name))

    def enumerate_groups_name(self) -> typing.Generator[str, None, None]:
        """
        Return all groups names managed by this groups manager. The names are returned
        as where inserted inside Database (most probably using administration interface)
        """
        for g in self._groups:
            yield g.group.db_obj().name

    def enumerate_valid_groups(self) -> typing.Generator['group.Group', None, None]:
        """Returns the list of valid groups for this groups manager."""
        from uds.models import Group as DBGroup  # Avoid circular imports

        valid_id_list: list[int] = [grp.group.db_obj().id for grp in self._groups if grp.is_valid]

        # Now, get metagroups and also return them
        for db_group in DBGroup.objects.filter(manager__id=self._db_auth.id, is_meta=True):
            number_of_groups = db_group.groups.filter(id__in=valid_id_list, state=State.ACTIVE).count()
            if db_group.meta_if_any and number_of_groups > 0:
                # If meta_if_any is true, we only need one group to be valid
                # so "fake" number_of_groups to  all groups, so next if is always true
                number_of_groups = db_group.groups.count()

            # If a meta group is empty, all users belongs to it.
            # we can use number_of_groups != 0 to check that if it is empty, is not valid
            if number_of_groups == db_group.groups.count():
                # This group matches
                yield group.Group(db_group)

    def has_valid_groups(self) -> bool:
        """
        Checks if this groups manager has at least one group that has been
        validated (using :py:meth:.validate)
        """
        return any(g.is_valid for g in self._groups)

    def get_group(self, group_name: str) -> typing.Optional['group.Group']:
        """
        If this groups manager contains that group manager, it returns the
        :py:class:uds.core.auths.group.Group  representing that group name.
        """
        for group in self._groups:
            if group.matches(group_name):
                return group.group

        return None

    def validate(self, group_name: typing.Union[str, collections.abc.Iterable[str]]) -> None:
        """Validates that the group (or groups) group_name passed in is valid for this group manager.

        It check that the group specified is known by this group manager.

        Args:
           group_name: string, list or tuple of values (strings) to check

        Returns nothing, it changes the groups this groups contains attributes,
        so they reflect the known groups that are considered valid.
        """
        if not isinstance(group_name, str):
            for name in group_name:
                self.validate(name)
        else:
            for grp in self._mached_groups(group_name):
                grp.is_valid = True

    def is_valid(self, group_name: str) -> bool:
        """
        Checks if this group name is marked as valid inside this groups manager.
        Returns True if group name is marked as valid, False if it isn't.
        """
        return any(grp.is_valid for grp in self._mached_groups(group_name))

    def __str__(self) -> str:
        return f'Groupsmanager: {self._groups}'
