# -*- coding: utf-8 -*-

#
# Copyright (c) 2023 Virtual Cable S.L.U.
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

from django.db.models import Count

from uds.core.jobs import Job
from uds import models
from uds.core.types import log
from uds.core.util.model import sql_now
from uds.core.util import config

# from uds.core.util.config import GlobalConfig


logger = logging.getLogger(__name__)


class LogMaintenance(Job):
    frecuency = 3600  # Once every hour
    # frecuency_cfg = GlobalConfig.XXXX
    friendly_name = 'Log maintenance'

    def run(self) -> None:
        logger.debug('Starting log maintenance')
        # Select all disctinct owner_id and owner_type and count of each
        # For each one, check if it has more than max_elements, and if so, delete the oldest ones
        for owner_id, owner_type, count in (
            models.Log.objects.values_list('owner_id', 'owner_type')
            .annotate(count=Count('owner_id'))
            .order_by('owner_id')
        ):
            # First, ensure we do not have more than requested logs, and we can put one more log item
            try:
                owner_type = log.LogObjectType(owner_type)
            except ValueError:
                # If we do not know the owner type, we will delete all logs for this owner
                models.Log.objects.filter(owner_id=owner_id, owner_type=owner_type).delete()
                continue

            max_elements = owner_type.get_max_elements()
            # Ensures that last hour logs are not deleted
            removing_before = sql_now() - datetime.timedelta(seconds=3600)
            if 0 < max_elements < count:  # Negative max elements means "unlimited"
                # Recent logs (last hour)
                recent_ids = set(models.Log.objects.filter(
                    owner_id=owner_id,
                    owner_type=owner_type,
                    created__gte=removing_before
                ).values_list('id', flat=True))

                # Old logs (before last hour)
                old_ids_to_keep = set(models.Log.objects.filter(
                    owner_id=owner_id,
                    owner_type=owner_type,
                    created__lt=removing_before
                ).order_by('-created', '-id').values_list('id', flat=True)[:max_elements])

                # IDs to keep
                ids_to_keep = recent_ids.union(old_ids_to_keep)

                # Delete everything else
                models.Log.objects.filter(
                    owner_id=owner_id,
                    owner_type=owner_type,
                ).exclude(id__in=ids_to_keep).delete()

        # Also, delete all logs older than config.GlobalConfig.STATS_DURATION.as_int()*2 days
        # This is to ensure we do not have "orphan" logs too old
        models.Log.objects.filter(
            created__lt=sql_now() - datetime.timedelta(days=config.GlobalConfig.STATS_DURATION.as_int() * 2)
        ).delete()
        logger.debug('Log maintenance done')
