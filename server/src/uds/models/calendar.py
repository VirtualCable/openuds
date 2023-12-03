# -*- coding: utf-8 -*-

# Copyright (c) 2016-2023 Virtual Cable S.L.U.
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
Author:: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing
import collections.abc

from django.db import models
from .uuid_model import UUIDModel
from .tag import TaggingMixin


logger = logging.getLogger(__name__)


# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.models import CalendarRule, CalendarAction, CalendarAccess


class Calendar(UUIDModel, TaggingMixin):
    name = models.CharField(max_length=128, default='')
    comments = models.CharField(max_length=256, default='')
    modified = models.DateTimeField(auto_now=True)

    # "fake" declarations for type checking
    # objects: 'models.manager.Manager["Calendar"]'
    rules: 'models.manager.RelatedManager[CalendarRule]'
    calendaraction_set: 'models.manager.RelatedManager[CalendarAction]'
    calendaraccess_set: 'models.manager.RelatedManager[CalendarAccess]'

    class Meta:  # pylint: disable=too-few-public-methods
        """
        Meta class to declare db table
        """

        db_table = 'uds_calendar'
        app_label = 'uds'

    # Override default save to add uuid
    def save(self, *args, **kwargs):
        logger.debug('Saving calendar')

        res = UUIDModel.save(self, *args, **kwargs)

        # Basically, recalculates all related actions next execution time...
        try:
            for v in self.calendaraction_set.all():
                v.save()
        except (
            Exception
        ):  # nosec: catch all, we don't want to fail here (if one action cannot be saved, we don't want to fail all)
            pass

        return res

    def __str__(self):
        return f'Calendar "{self.name}" modified on {self.modified}, rules: {self.rules.count()}'
