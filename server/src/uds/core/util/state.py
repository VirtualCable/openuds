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
from django.utils.translation import gettext_noop as _, gettext_lazy


# States for different objects. Not all objects supports all States
class State:
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
    RESTRAINED = 'T'  # "Visual" state, no element will in fact be in this state, but admins uses it to "notily" user
    USABLE = 'U'
    RUNNING = 'W'
    FOR_EXECUTE = 'X'
    MAINTENANCE = 'Y'  # "Visual" state, no element will be in fact in maintenance, but used to show "Services Pools" for which a Provider is in maintenance
    WAITING_OS = 'Z'  # "Visual" state, no element will be in fact in WAITING_OS, but used to show "User Services" that are waiting for os manager
    META_MEMBER = 'V'  # "Visual" state, no element will be in fact in WAITING_OS, but used to show "User Services" that are waiting for os manager

    string = {
        ACTIVE: _('Active'),
        INACTIVE: _('Inactive'),
        BLOCKED: _('Blocked'),
        LAUNCHING: _('Waiting publication'),
        PREPARING: _('In preparation'),
        USABLE: _('Valid'),
        REMOVABLE: _('Removing'),  # Display as it is removing
        RESTRAINED: _('Restrained'),
        REMOVING: _('Removing'),
        REMOVED: _('Removed'),
        CANCELED: _('Canceled'),
        CANCELING: _('Canceling'),
        ERROR: _('Error'),
        RUNNING: _('Running'),
        FINISHED: _('Finished'),
        FOR_EXECUTE: _('Waiting execution'),
        BALANCING: _('Balancing'),
        MAINTENANCE: _('In maintenance'),
        WAITING_OS: _('Waiting OS'),
        SLOWED_DOWN: _('Too many preparing services'),
        META_MEMBER: _('Meta member'),
    }

    # States that are merely for "information" to the user. They don't contain any usable instance
    INFO_STATES = [REMOVED, CANCELED, ERROR]

    # States that indicates that the service is "Valid" for a user
    VALID_STATES = [USABLE, PREPARING]

    # Publication States
    PUBLISH_STATES = [LAUNCHING, PREPARING]

    @staticmethod
    def isActive(state):
        return state == State.ACTIVE

    @staticmethod
    def isInactive(state):
        return state == State.INACTIVE

    @staticmethod
    def isBlocked(state):
        return state == State.BLOCKED

    @staticmethod
    def isPreparing(state):
        return state == State.PREPARING

    @staticmethod
    def isUsable(state):
        return state == State.USABLE

    @staticmethod
    def isRemovable(state):
        return state == State.REMOVABLE

    @staticmethod
    def isRemoving(state):
        return state == State.REMOVING

    @staticmethod
    def isRemoved(state):
        return state == State.REMOVED

    @staticmethod
    def isCanceling(state):
        return state == State.CANCELING

    @staticmethod
    def isCanceled(state):
        return state == State.CANCELED

    @staticmethod
    def isErrored(state):
        return state == State.ERROR

    @staticmethod
    def isFinished(state):
        return state == State.FINISHED

    @staticmethod
    def isRuning(state):
        return state == State.RUNNING

    @staticmethod
    def isForExecute(state):
        return state == State.FOR_EXECUTE

    @staticmethod
    def toString(state):
        return State.string.get(state, '')

    @staticmethod
    def dictionary():
        """
        Returns a dictionary with current active locale translation of States to States String
        """
        res = {}
        for k, v in State.string.items():
            res[k] = gettext_lazy(v)
        return res
