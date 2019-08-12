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
import re
import logging
import typing

from uds.core.util.State import State
from .Group import Group

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
    _groups: typing.Dict[str, dict]

    def __init__(self, dbAuthenticator: 'DBAuthenticator'):
        """
        Initializes the groups manager.
        The dbAuthenticator is the database record of the authenticator
        to which this groupsManager will be associated
        """
        self._dbAuthenticator = dbAuthenticator
        self._groups = {}  # We just get active groups, inactive aren't visible to this class
        for g in dbAuthenticator.groups.filter(state=State.ACTIVE, is_meta=False):
            name = g.name.lower()
            isPattern = name.find('pat:') == 0  # Is a pattern?
            self._groups[name] = {'name': g.name, 'group': Group(g), 'valid': False, 'pattern': isPattern}

    def checkAllGroups(self, groupName: str):
        """
        Returns true if this groups manager contains the specified group name (string)
        """
        name = groupName.lower()
        res = []
        for gName, grp in self._groups.items():
            if grp['pattern'] is True:
                logger.debug('Group is a pattern: %s', grp)
                try:
                    logger.debug('Match: %s->%s', grp['name'][4:], name)
                    if re.search(grp['name'][4:], name, re.IGNORECASE) is not None:
                        res.append(grp)  # Stop searching, one group at least matches
                except Exception:
                    logger.exception('Exception in RE')
            else:
                logger.debug('Group: %s==%s', name, gName)
                if name == gName:
                    res.append(grp)
        return res

    def getGroupsNames(self) -> typing.Iterable[str]:
        """
        Return all groups names managed by this groups manager. The names are returned
        as where inserted inside Database (most probably using administration interface)
        """
        for g in self._groups.values():
            yield g['group'].dbGroup().name

    def getValidGroups(self) -> typing.Iterable[Group]:
        """
        returns the list of valid groups (:py:class:uds.core.auths.Group.Group)
        """
        from uds.models import Group as DBGroup

        lst: typing.List[str] = []
        for g in self._groups.values():
            if g['valid'] is True:
                lst += (g['group'].dbGroup().id,)
                yield g['group']

        # Now, get metagroups and also return them
        for g2 in DBGroup.objects.filter(manager__id=self._dbAuthenticator.id, is_meta=True):  # @UndefinedVariable
            gn = g2.groups.filter(id__in=lst, state=State.ACTIVE).count()
            if g2.meta_if_any is True and gn > 0:
                gn = g2.groups.count()
            if gn == g2.groups.count():  # If a meta group is empty, all users belongs to it. we can use gn != 0 to check that if it is empty, is not valid
                # This group matches
                yield Group(g2)

    def hasValidGroups(self):
        """
        Checks if this groups manager has at least one group that has been
        validated (using :py:meth:.validate)
        """
        for g in self._groups.values():
            if g['valid'] is True:
                return True
        return False

    def getGroup(self, groupName: str) -> typing.Optional[Group]:
        """
        If this groups manager contains that group manager, it returns the
        :py:class:uds.core.auths.Group.Group  representing that group name.
        """
        if groupName.lower() in self._groups:
            return self._groups[groupName.lower()]['group']
        return None

    def validate(self, groupName: typing.Union[str, typing.Iterable]):
        """
        Validates that the group groupName passed in is valid for this group manager.

        It check that the group specified is known by this group manager.

        Args:
           groupName: string, list or tuple of values (strings) to check

        Returns nothing, it changes the groups this groups contains attributes,
        so they reflect the known groups that are considered valid.
        """
        if not isinstance(groupName, str):
            for n in groupName:
                self.validate(n)
        else:
            for grp in self.checkAllGroups(groupName):
                grp['valid'] = True

    def isValid(self, groupName: str) -> bool:
        """
        Checks if this group name is marked as valid inside this groups manager.
        Returns True if group name is marked as valid, False if it isn't.
        """
        for grp in self.checkAllGroups(groupName):
            if grp['valid']:
                return True
        return False

    def __str__(self):
        return "Groupsmanager: {0}".format(self._groups)
