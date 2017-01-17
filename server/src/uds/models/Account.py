# -*- coding: utf-8 -*-
#
# Copyright (c) 2012 Virtual Cable S.L.
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
#    * Neither the name of Virtual Cable S.L. nor the names of its contributors
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
'''
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
'''

from __future__ import unicode_literals

__updated__ = '2017-01-17'

from django.db import models

from uds.models.UUIDModel import UUIDModel
from uds.models.Tag import TaggingMixin
from uds.models.Util import getSqlDatetime
from django.db.models import signals

import logging

logger = logging.getLogger(__name__)


class Account(UUIDModel, TaggingMixin):
    '''
    Account storing on DB model
    '''
    name = models.CharField(max_length=128, unique=False, db_index=True)
    comments = models.CharField(max_length=256)

    def startUsageAccounting(self, service):
        if hasattr(service, 'accounting'):  # Already has an account
            return
        start = getSqlDatetime()
        if service.user is not None:
            userName = service.user.pretty_name
            userUuid = service.user.uuid
        else:
            userName = '??????'
            userUuid = '00000000-0000-0000-0000-000000000000'
        return self.usages.create(
            user_service=service,
            user_name=userName,
            user_uuid=userUuid,
            pool_name=service.deployed_service.name,
            pool_uuid=service.deployed_service.uuid,
            start=start,
            end=start
        )

    def stopUsageAccounting(self, service):
        if hasattr(service, 'accounting') is False:
            return

        tmp = service.accounting
        tmp.user_service = None
        tmp.end = getSqlDatetime()
        tmp.save()

    class Meta:
        '''
        Meta class to declare the name of the table at database
        '''
        db_table = 'uds_accounts'
        app_label = 'uds'

    def __unicode__(self):
        return 'Account id {}, name {}'.format(self.id, self.name)
