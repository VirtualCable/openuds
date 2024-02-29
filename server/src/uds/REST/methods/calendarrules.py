# -*- coding: utf-8 -*-

#
# Copyright (c) 2014-2019 Virtual Cable S.L.
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
import datetime
import logging
import typing

from django.db import IntegrityError
from django.utils.translation import gettext as _

from uds.core import exceptions
from uds.core.util import ensure, permissions
from uds.core.util.model import process_uuid, sql_datetime
from uds.models.calendar import Calendar
from uds.models.calendar_rule import CalendarRule, FrequencyInfo
from uds.REST.model import DetailHandler

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from django.db.models import Model

logger = logging.getLogger(__name__)


class CalendarRules(DetailHandler):  # pylint: disable=too-many-public-methods
    """
    Detail handler for Services, whose parent is a Provider
    """

    @staticmethod
    def ruleToDict(item: CalendarRule, perm: int) -> dict[str, typing.Any]:
        """
        Convert a calRule db item to a dict for a rest response
        :param item: Rule item (db)
        :param perm: Permission of the object
        """
        retVal = {
            'id': item.uuid,
            'name': item.name,
            'comments': item.comments,
            'start': item.start,
            'end': datetime.datetime.combine(item.end, datetime.time.max) if item.end else None,
            'frequency': item.frequency,
            'interval': item.interval,
            'duration': item.duration,
            'duration_unit': item.duration_unit,
            'permission': perm,
        }

        return retVal

    def get_items(self, parent: 'Model', item: typing.Optional[str]) -> typing.Any:
        parent = ensure.is_instance(parent, Calendar)
        # Check what kind of access do we have to parent provider
        perm = permissions.effective_permissions(self._user, parent)
        try:
            if item is None:
                return [CalendarRules.ruleToDict(k, perm) for k in parent.rules.all()]
            k = parent.rules.get(uuid=process_uuid(item))
            return CalendarRules.ruleToDict(k, perm)
        except Exception as e:
            logger.exception('itemId %s', item)
            raise self.invalid_item_response() from e

    def get_fields(self, parent: 'Model') -> list[typing.Any]:
        parent = ensure.is_instance(parent, Calendar)

        return [
            {'name': {'title': _('Rule name')}},
            {'start': {'title': _('Starts'), 'type': 'datetime'}},
            {'end': {'title': _('Ends'), 'type': 'date'}},
            {
                'frequency': {
                    'title': _('Repeats'),
                    'type': 'dict',
                    'dict': dict((v.name, str(v.value.title)) for v in FrequencyInfo),
                }
            },
            {'interval': {'title': _('Every'), 'type': 'callback'}},
            {'duration': {'title': _('Duration'), 'type': 'callback'}},
            {'comments': {'title': _('Comments')}},
        ]

    def save_item(self, parent: 'Model', item: typing.Optional[str]) -> None:
        parent = ensure.is_instance(parent, Calendar)

        # Extract item db fields
        # We need this fields for all
        logger.debug('Saving rule %s / %s', parent, item)
        fields = self.fields_from_params(
            [
                'name',
                'comments',
                'frequency',
                'start',
                'end',
                'interval',
                'duration',
                'duration_unit',
            ]
        )

        if int(fields['interval']) < 1:
            raise self.invalid_item_response('Repeat must be greater than zero')

        # Convert timestamps to datetimes
        fields['start'] = datetime.datetime.fromtimestamp(fields['start'])
        if fields['end'] is not None:
            fields['end'] = datetime.datetime.fromtimestamp(fields['end'])

        calRule: CalendarRule
        try:
            if item is None:  # Create new
                calRule = parent.rules.create(**fields)
            else:
                calRule = parent.rules.get(uuid=process_uuid(item))
                calRule.__dict__.update(fields)
                calRule.save()
        except CalendarRule.DoesNotExist:
            raise self.invalid_item_response() from None
        except IntegrityError as e:  # Duplicate key probably
            raise exceptions.rest.RequestError(_('Element already exists (duplicate key error)')) from e
        except Exception as e:
            logger.exception('Saving calendar')
            raise self.invalid_request_response(f'incorrect invocation to PUT: {e}') from e

    def delete_item(self, parent: 'Model', item: str) -> None:
        parent = ensure.is_instance(parent, Calendar)
        logger.debug('Deleting rule %s from %s', item, parent)
        try:
            calRule = parent.rules.get(uuid=process_uuid(item))
            calRule.calendar.modified = sql_datetime()
            calRule.calendar.save()
            calRule.delete()
        except Exception as e:
            logger.exception('Exception')
            raise self.invalid_item_response() from e

    def get_title(self, parent: 'Model') -> str:
        parent = ensure.is_instance(parent, Calendar)
        try:
            return _('Rules of {0}').format(parent.name)
        except Exception:
            return _('Current rules')
