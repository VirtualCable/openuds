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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import datetime
import logging
import typing

from django.db import IntegrityError
from django.utils.translation import gettext as _

from uds.core import exceptions, types
from uds.core.util import ensure, permissions, ui as ui_utils
from uds.core.util.model import process_uuid, sql_now
from uds.models.calendar import Calendar
from uds.models.calendar_rule import CalendarRule, FrequencyInfo
from uds.REST.model import DetailHandler

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from django.db.models import Model

logger = logging.getLogger(__name__)

class CalendarRuleItem(types.rest.BaseRestItem):
    id: str
    name: str
    comments: str
    start: datetime.datetime
    end: datetime.datetime|None
    frequency: str
    interval: int
    duration: int
    duration_unit: str
    permission: int

class CalendarRules(DetailHandler[CalendarRuleItem]):  # pylint: disable=too-many-public-methods
    """
    Detail handler for Services, whose parent is a Provider
    """

    @staticmethod
    def rule_as_dict(item: CalendarRule, perm: int) -> CalendarRuleItem:
        """
        Convert a calrule db item to a dict for a rest response
        :param item: Rule item (db)
        :param perm: Permission of the object
        """
        return {
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

    def get_items(self, parent: 'Model', item: typing.Optional[str]) -> types.rest.ItemsResult[CalendarRuleItem]:
        parent = ensure.is_instance(parent, Calendar)
        # Check what kind of access do we have to parent provider
        perm = permissions.effective_permissions(self._user, parent)
        try:
            if item is None:
                return [CalendarRules.rule_as_dict(k, perm) for k in parent.rules.all()]
            k = parent.rules.get(uuid=process_uuid(item))
            return CalendarRules.rule_as_dict(k, perm)
        except Exception as e:
            logger.exception('itemId %s', item)
            raise self.invalid_item_response() from e
        
    def get_table_info(self, parent: 'Model') -> types.rest.TableInfo:
        parent = ensure.is_instance(parent, Calendar)
        return (
            ui_utils.TableBuilder(_('Rules of {0}').format(parent.name))
            .string(name='name', title=_('Name'))
            .datetime(name='start', title=_('Start'))
            .date(name='end', title=_('End'))
            .dictionary(name='frequency', title=_('Frequency'), dct=FrequencyInfo.literals_dict())
            .number(name='interval', title=_('Interval'))
            .number(name='duration', title=_('Duration'))
            .string(name='comments', title=_('Comments'))
            .build()
        )

    def save_item(self, parent: 'Model', item: typing.Optional[str]) -> typing.Any:
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

        calendar_rule: CalendarRule
        try:
            if item is None:  # Create new
                calendar_rule = parent.rules.create(**fields)
            else:
                calendar_rule = parent.rules.get(uuid=process_uuid(item))
                calendar_rule.__dict__.update(fields)
                calendar_rule.save()
                return {'id': calendar_rule.uuid}
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
            calendar_rule = parent.rules.get(uuid=process_uuid(item))
            calendar_rule.calendar.modified = sql_now()
            calendar_rule.calendar.save()
            calendar_rule.delete()
        except Exception as e:
            logger.exception('Exception')
            raise self.invalid_item_response() from e

