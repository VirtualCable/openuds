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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging

from django.db.models import Count

from uds.core.jobs import Job
from uds import models
from uds.core.managers.log import objects

# from uds.core.util.config import GlobalConfig


logger = logging.getLogger(__name__)


class LogMaintenance(Job):
    frecuency = 7200  # Once every two hours
    # frecuency_cfg = GlobalConfig.XXXX
    friendly_name = 'Log maintenance'

    def run(self) -> None:
        # Select all disctinct owner_id and owner_type and count of each
        # For each one, check if it has more than max_elements, and if so, delete the oldest ones
        for owner_id, owner_type, count in (
            models.Log.objects.values_list('owner_id', 'owner_type')
            .annotate(count=Count('owner_id'))
            .order_by('owner_id')
        ):
            # First, ensure we do not have more than requested logs, and we can put one more log item
            try:
                ownerType = objects.LogObjectType(owner_type)
            except ValueError:
                # If we do not know the owner type, we will delete all logs for this owner
                models.Log.objects.filter(owner_id=owner_id, owner_type=owner_type).delete()
                continue

            max_elements = ownerType.get_max_elements()
            if 0 < max_elements < count:   # Negative max elements means "unlimited"
                # We will delete the oldest ones
                for record in models.Log.objects.filter(owner_id=owner_id, owner_type=owner_type).order_by('created', 'id')[: count - max_elements + 1]:
                    record.delete()

