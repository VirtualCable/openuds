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
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''
from __future__ import unicode_literals

from django.db import transaction
from uds.core.util.Config import GlobalConfig
from uds.models import DeployedService, getSqlDatetime
from uds.core.util.State import State
from uds.core.jobs.Job import Job
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class DeployedServiceInfoItemsCleaner(Job):
    frecuency = 3607
    frecuency_cfg = GlobalConfig.CLEANUP_CHECK  # Request run cache "info" cleaner every configured seconds. If config value is changed, it will be used at next reload
    friendly_name = 'Deployed Service Info Cleaner'

    def __init__(self, environment):
        super(DeployedServiceInfoItemsCleaner, self).__init__(environment)

    def run(self):
        removeFrom = getSqlDatetime() - timedelta(seconds=GlobalConfig.KEEP_INFO_TIME.getInt())
        DeployedService.objects.filter(state__in=State.INFO_STATES, state_date__lt=removeFrom).delete()


class DeployedServiceRemover(Job):
    frecuency = 31
    frecuency_cfg = GlobalConfig.REMOVAL_CHECK  # Request run publication "removal" every configued seconds. If config value is changed, it will be used at next reload
    friendly_name = 'Deployed Service Cleaner'

    def __init__(self, environment):
        super(DeployedServiceRemover, self).__init__(environment)

    def startRemovalOf(self, ds):
        # Get publications in course...., can be at most 1!!!
        logger.debug('Removal process of {0}'.format(ds))

        publishing = ds.publications.filter(state=State.PREPARING)
        for p in publishing:
            p.cancel()
        # Now all publishments are canceling, let's try to cancel cache and assigned
        uServices = ds.userServices.filter(state=State.PREPARING)
        for u in uServices:
            logger.debug('Canceling {0}'.format(u))
            u.cancel()
        # Nice start of removal, maybe we need to do some limitation later, but there should not be too much services nor publications cancelable at once
        ds.state = State.REMOVING
        ds.name = ds.name + ' (removed)'
        ds.save()

    def continueRemovalOf(self, ds):
        # Recheck that there is no publication created in "bad moment"
        try:
            publishing = ds.publications.filter(state=State.PREPARING)
            for p in publishing:
                p.cancel()
        except:
            pass

        try:
            # Now all publishments are canceling, let's try to cancel cache and assigned
            uServices = ds.userServices.filter(state=State.PREPARING)
            for u in uServices:
                logger.debug('Canceling {0}'.format(u))
                u.cancel()
        except:
            pass

        # First, we remove all publications and user services in "info_state"
        with transaction.atomic():
            ds.userServices.select_for_update().filter(state__in=State.INFO_STATES).delete()

        # Mark usable user services as removable
        now = getSqlDatetime()

        with transaction.atomic():
            ds.userServices.select_for_update().filter(state=State.USABLE).update(state=State.REMOVABLE, state_date=now)

        # When no service is at database, we start with publications
        if ds.userServices.all().count() == 0:
            try:
                logger.debug('All services removed, checking active publication')
                if ds.activePublication() is not None:
                    logger.debug('Active publication found, unpublishing it')
                    ds.unpublish()
                else:
                    logger.debug('No active publication found, removing info states and checking if removal is done')
                    ds.publications.filter(state__in=State.INFO_STATES).delete()
                    if ds.publications.count() is 0:
                        ds.removed()  # Mark it as removed, clean later from database
            except Exception:
                logger.exception('Cought unexpected exception at continueRemovalOf: ')

    def run(self):
        # First check if there is someone in "removable" estate
        rems = DeployedService.objects.filter(state=State.REMOVABLE)[:10]
        if len(rems) > 0:
            logger.debug('Found a deployed service marked for removal. Starting removal of {0}'.format(rems))
            for rem in rems:
                self.startRemovalOf(rem)
        rems = DeployedService.objects.filter(state=State.REMOVING)[:10]
        if len(rems) > 0:
            logger.debug('Found a deployed service in removing state, continuing removal of {0}'.format(rems))
            for rem in rems:
                self.continueRemovalOf(rem)
