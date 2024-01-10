# -*- coding: utf-8 -*-
#
# Copyright (c) 2024 Virtual Cable S.L.U.
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
import enum
import typing
from django.utils.translation import gettext_noop as _, gettext_lazy


class State(enum.StrEnum):
    ACTIVE = 'A'
    BLOCKED = 'B'
    CANCELED = 'C'
    ERROR = 'E'
    FINISHED = 'F'
    BALANCING = 'H'
    INACTIVE = 'I'
    CANCELING = 'K'
    LAUNCHING = 'L'
    REMOVING = 'M'
    PREPARING = 'P'
    REMOVABLE = 'R'
    REMOVED = 'S'
    USABLE = 'U'
    RUNNING = 'W'
    FOR_EXECUTE = 'X'
    MAINTENANCE = 'Y'  # "Visual" state, no element will be in fact in maintenance, but used to show "Services Pools" for which a Provider is in maintenance
    WAITING_OS = 'Z'  # "Visual" state, no element will be in fact in WAITING_OS, but used to show "User Services" that are whating for os manager

    def as_str(self) -> str:
        return _TRANSLATIONS.get(self, self.value)


_TRANSLATIONS: typing.Final[dict[State, str]] = {
    State.ACTIVE: _('Active'),
    State.INACTIVE: _('Inactive'),
    State.BLOCKED: _('Blocked'),
    State.LAUNCHING: _('Waiting publication'),
    State.PREPARING: _('In preparation'),
    State.USABLE: _('Valid'),
    State.REMOVABLE: _('Waiting for removal'),
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
}
