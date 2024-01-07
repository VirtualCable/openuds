# -*- coding: utf-8 -*-

#
# Copyright (c) 2015 Virtual Cable S.L.
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
import logging

from django.utils.translation import gettext_noop as _, gettext_lazy

logger = logging.getLogger(__name__)

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

string = {
    ACTIVE: _('Active'),
    INACTIVE: _('Inactive'),
    BLOCKED: _('Blocked'),
    LAUNCHING: _('Waiting publication'),
    PREPARING: _('In preparation'),
    USABLE: _('Valid'),
    REMOVABLE: _('Waiting for removal'),
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
}

# States that are merely for "information" to the user. They don't contain any usable instance
INFO_STATES = [REMOVED, CANCELED, ERROR]

# States that indicates that the service is "Valid" for a user
VALID_STATES = [USABLE, PREPARING]

# Publication States
PUBLISH_STATES = [LAUNCHING, PREPARING]


def is_active(state):
    return state == ACTIVE


def is_inactive(state):
    return state == INACTIVE


def is_blocked(state):
    return state == BLOCKED


def is_preparing(state):
    return state == PREPARING


def is_usable(state):
    return state == USABLE


def is_removable(state):
    return state == REMOVABLE


def is_removing(state):
    return state == REMOVING


def is_removed(state):
    return state == REMOVED


def is_canceling(state):
    return state == CANCELING


def is_canceled(state):
    return state == CANCELED


def is_errored(state):
    return state == ERROR


def is_finished(state):
    return state == FINISHED


def is_runing(state):
    return state == RUNNING


def is_for_execute(state):
    return state == FOR_EXECUTE


def as_str(state):
    return string.get(state, '')


def dictionary():
    """
    Returns a dictionary with current active locale translation of States to States String
    """
    return {k: gettext_lazy(v) for k, v in string.items()}
