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
import typing

from django.utils.translation import gettext_lazy as _

if typing.TYPE_CHECKING:
    from uds.core.types.calendar import CalendarAction


# Current posible actions
#
CALENDAR_ACTION_PUBLISH: typing.Final['CalendarAction'] = {
    'id': 'PUBLISH',
    'description': _('Publish'),
    'params': (),
}
CALENDAR_ACTION_CACHE_L1: typing.Final['CalendarAction'] = {
    'id': 'CACHEL1',
    'description': _('Set cache size'),
    'params': (
        {
            'type': 'numeric',
            'name': 'size',
            'description': _('Cache size'),
            'default': '1',
        },
    ),
}
CALENDAR_ACTION_CACHE_L2: typing.Final['CalendarAction'] = {
    'id': 'CACHEL2',
    'description': _('Set L2 cache size'),
    'params': (
        {
            'type': 'numeric',
            'name': 'size',
            'description': _('Cache L2 size'),
            'default': '1',
        },
    ),
}
CALENDAR_ACTION_INITIAL: typing.Final['CalendarAction'] = {
    'id': 'INITIAL',
    'description': _('Set initial services'),
    'params': (
        {
            'type': 'numeric',
            'name': 'size',
            'description': _('Initial services'),
            'default': '1',
        },
    ),
}
CALENDAR_ACTION_MAX: typing.Final['CalendarAction'] = {
    'id': 'MAX',
    'description': _('Set maximum number of services'),
    'params': (
        {
            'type': 'numeric',
            'name': 'size',
            'description': _('Maximum services'),
            'default': '10',
        },
    ),
}
CALENDAR_ACTION_ADD_TRANSPORT: typing.Final['CalendarAction'] = {
    'id': 'ADD_TRANSPORT',
    'description': _('Add a transport'),
    'params': (
        {
            'type': 'transport',
            'name': 'transport',
            'description': _('Transport'),
            'default': '',
        },
    ),
}
CALENDAR_ACTION_DEL_TRANSPORT: typing.Final['CalendarAction'] = {
    'id': 'REMOVE_TRANSPORT',
    'description': _('Remove a transport'),
    'params': (
        {
            'type': 'transport',
            'name': 'transport',
            'description': _('Trasport'),
            'default': '',
        },
    ),
}
CALENDAR_ACTION_DEL_ALL_TRANSPORTS: typing.Final['CalendarAction'] = {
    'id': 'REMOVE_ALL_TRANSPORTS',
    'description': _('Remove all transports'),
    'params': (),
}
CALENDAR_ACTION_ADD_GROUP: typing.Final['CalendarAction'] = {
    'id': 'ADD_GROUP',
    'description': _('Add a group'),
    'params': ({'type': 'group', 'name': 'group', 'description': _('Group'), 'default': ''},),
}
CALENDAR_ACTION_DEL_GROUP: typing.Final['CalendarAction'] = {
    'id': 'REMOVE_GROUP',
    'description': _('Remove a group'),
    'params': ({'type': 'group', 'name': 'group', 'description': _('Group'), 'default': ''},),
}
CALENDAR_ACTION_DEL_ALL_GROUPS: typing.Final['CalendarAction'] = {
    'id': 'REMOVE_ALL_GROUPS',
    'description': _('Remove all groups'),
    'params': (),
}
CALENDAR_ACTION_IGNORE_UNUSED: typing.Final['CalendarAction'] = {
    'id': 'IGNORE_UNUSED',
    'description': _('Sets the ignore unused'),
    'params': (
        {
            'type': 'bool',
            'name': 'state',
            'description': _('Ignore assigned and unused'),
            'default': False,
        },
    ),
}
CALENDAR_ACTION_REMOVE_USERSERVICES: typing.Final['CalendarAction'] = {
    'id': 'REMOVE_USERSERVICES',
    'description': _('Remove ALL assigned user service. USE WITH CAUTION!'),
    'params': (),
}

CALENDAR_ACTION_REMOVE_STUCK_USERSERVICES: typing.Final['CalendarAction'] = {
    'id': 'STUCK_USERSERVICES',
    'description': _('Remove OLD assigned user services.'),
    'params': (
        {
            'type': 'numeric',
            'name': 'hours',
            'description': _('Time in hours before considering the user service is OLD.'),
            'default': '72',
        },
    ),
}

CALENDAR_ACTION_CLEAN_CACHE_L1: typing.Final['CalendarAction'] = {
    'id': 'CLEAN_CACHE_L1',
    'description': _('Clean L1 cache'),
    'params': (),
}

CALENDAR_ACTION_CLEAN_CACHE_L2: typing.Final['CalendarAction'] = {
    'id': 'CLEAN_CACHE_L2',
    'description': _('Clean L2 cache'),
    'params': (),
}


CALENDAR_ACTION_DICT: typing.Final[dict[str, 'CalendarAction']] = {
    c['id']: c
    for c in (
        CALENDAR_ACTION_PUBLISH,
        CALENDAR_ACTION_CACHE_L1,
        CALENDAR_ACTION_CACHE_L2,
        CALENDAR_ACTION_INITIAL,
        CALENDAR_ACTION_MAX,
        CALENDAR_ACTION_ADD_TRANSPORT,
        CALENDAR_ACTION_DEL_TRANSPORT,
        CALENDAR_ACTION_DEL_ALL_TRANSPORTS,
        CALENDAR_ACTION_ADD_GROUP,
        CALENDAR_ACTION_DEL_GROUP,
        CALENDAR_ACTION_DEL_ALL_GROUPS,
        CALENDAR_ACTION_IGNORE_UNUSED,
        CALENDAR_ACTION_REMOVE_USERSERVICES,
        CALENDAR_ACTION_REMOVE_STUCK_USERSERVICES,
        CALENDAR_ACTION_CLEAN_CACHE_L1,
        CALENDAR_ACTION_CLEAN_CACHE_L2,
    )
}
