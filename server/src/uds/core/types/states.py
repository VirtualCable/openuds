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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import typing
import enum

from django.utils.translation import gettext_lazy as _

from uds.core.util.decorators import classproperty


# States for different objects. Not all objects supports all States
class State(enum.StrEnum):
    """
    This class represents possible states for objects at database.
    Take in consideration that objects do not have to support all states, they are here for commodity
    """

    ACTIVE = 'A'
    BLOCKED = 'B'
    CANCELED = 'C'
    ERROR = 'E'
    FINISHED = 'F'
    BALANCING = 'H'
    INACTIVE = 'I'
    SLOWED_DOWN = 'J'  # Only used on admin dashboard, not internal real state
    CANCELING = 'K'
    LAUNCHING = 'L'
    REMOVING = 'M'
    PREPARING = 'P'
    REMOVABLE = 'R'
    REMOVED = 'S'
    # "Visual" state, no element will in fact be in this state, but admins uses it to "notily" user
    RESTRAINED = 'T'
    USABLE = 'U'
    RUNNING = 'W'
    FOR_EXECUTE = 'X'
    # "Visual" state, no element will be in fact in maintenance, but used to show "Services Pools" for which a Provider is in maintenance
    MAINTENANCE = 'Y'
    # "Visual" state, no element will be in fact in WAITING_OS, but used to show "User Services" that are waiting for os manager
    WAITING_OS = 'Z'
    # "Visual" state, no element will be in fact in WAITING_OS, but used to show "User Services" that are waiting for os manager
    META_MEMBER = 'V'

    # For accesses (calendar actions)
    ALLOW = 'ALLOW'
    DENY = 'DENY'

    # Unkonwn state
    UNKNOWN = 'UKN'

    # States that are merely for "information" to the user. They don't contain any usable instance
    @classproperty
    def INFO_STATES(self) -> list[str]:
        return [self.REMOVED, self.CANCELED, self.ERROR]

    # States that indicates that the service is "Valid" for a user
    @classproperty
    def VALID_STATES(self) -> list[str]:
        return [self.USABLE, self.PREPARING]

    # Publication States
    @classproperty
    def PUBLISH_STATES(self) -> list[str]:
        return [self.LAUNCHING, self.PREPARING]

    @classproperty
    def localized(self) -> str:
        """Returns the literal translation of the state"""
        return _TRANSLATIONS.get(self, _TRANSLATIONS[State.UNKNOWN])

    def is_active(self) -> bool:
        return self == State.ACTIVE

    def is_inactive(self) -> bool:
        return self == State.INACTIVE

    def is_blocked(self) -> bool:
        return self == State.BLOCKED

    def is_preparing(self) -> bool:
        return self == State.PREPARING

    def is_usable(self) -> bool:
        return self == State.USABLE

    def is_removable(self) -> bool:
        return self == State.REMOVABLE

    def is_removing(self) -> bool:
        return self == State.REMOVING

    def is_removed(self) -> bool:
        return self == State.REMOVED

    def is_canceling(self) -> bool:
        return self == State.CANCELING

    def is_canceled(self) -> bool:
        return self == State.CANCELED

    def is_errored(self) -> bool:
        return self == State.ERROR

    def is_finished(self) -> bool:
        return self == State.FINISHED

    def is_runing(self) -> bool:
        return self == State.RUNNING

    def is_for_execute(self) -> bool:
        return self == State.FOR_EXECUTE

    @staticmethod
    def from_str(state: str) -> 'State':
        try:
            return State(state)
        except ValueError:
            return State.UNKNOWN

    @staticmethod
    def literals_dict(*lst: 'State') -> dict[str, str]:
        """
        Returns a dictionary with current active locale translation of States to States String
        if lst is empty, returns all states
        """
        if not lst:
            return {k: str(v) for k, v in _TRANSLATIONS.items()}
        else:
            return {k: str(_TRANSLATIONS[k]) for k in lst}


class DeployState(enum.StrEnum):
    RUNNING = State.RUNNING
    FINISHED = State.FINISHED
    ERROR = State.ERROR

    UNKNOWN = State.UNKNOWN

    def is_errored(self) -> bool:
        return self == DeployState.ERROR

    def is_finished(self) -> bool:
        return self == DeployState.FINISHED

    def is_runing(self) -> bool:
        return self == DeployState.RUNNING

    @staticmethod
    def from_str(state: str) -> 'DeployState':
        try:
            return DeployState(state)
        except ValueError:
            return DeployState.UNKNOWN


_TRANSLATIONS: typing.Final[dict[State, str]] = {
    State.ACTIVE: _('Active'),
    State.INACTIVE: _('Inactive'),
    State.BLOCKED: _('Blocked'),
    State.LAUNCHING: _('Waiting publication'),
    State.PREPARING: _('In preparation'),
    State.USABLE: _('Valid'),
    State.REMOVABLE: _('Removing'),  # Display as it is removing
    State.RESTRAINED: _('Restrained'),
    State.REMOVING: _('Removing'),
    State.REMOVED: _('Removed'),
    State.CANCELED: _('Canceled'),
    State.CANCELING: _('Canceling'),
    State.ERROR: _('Error'),
    State.RUNNING: _('Running'),
    State.FINISHED: _('Finished'),
    State.FOR_EXECUTE: _('Waiting execution'),
    State.BALANCING: _('Balancing'),
    State.MAINTENANCE: _('In maintenance'),
    State.WAITING_OS: _('Waiting OS'),
    State.SLOWED_DOWN: _('Too many preparing services'),
    State.META_MEMBER: _('Meta member'),
    State.ALLOW: _('Allowed'),
    State.DENY: _('Denied'),
    State.UNKNOWN: _('Unknown'),
}
