# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2024 Virtual Cable S.L.U.
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
from datetime import timedelta
import logging
import collections.abc

from django.db import transaction
from uds.core.util.config import GlobalConfig
from uds.models import ServicePool, UserService
from uds.core.util.model import sql_datetime
from uds.core.types.states import State
from uds.core.jobs import Job

logger = logging.getLogger(__name__)

MAX_REMOVING_TIME = 3600 * 24 * 1  # 2 days, in seconds


class DeployedServiceInfoItemsCleaner(Job):
    frecuency = 3607
    frecuency_cfg = (
        GlobalConfig.CLEANUP_CHECK
    )  # Request run cache "info" cleaner every configured seconds. If config value is changed, it will be used at next reload
    friendly_name = 'Deployed Service Info Cleaner'

    def run(self) -> None:
        removeFrom = sql_datetime() - timedelta(
            seconds=GlobalConfig.KEEP_INFO_TIME.as_int()
        )
        ServicePool.objects.filter(
            state__in=State.INFO_STATES, state_date__lt=removeFrom
        ).delete()


class DeployedServiceRemover(Job):
    frecuency = 31
    frecuency_cfg = (
        GlobalConfig.REMOVAL_CHECK
    )  # Request run publication "removal" every configued seconds. If config value is changed, it will be used at next reload
    friendly_name = 'Deployed Service Cleaner'

    def start_removal_of(self, service_pool: ServicePool) -> None:
        if (
            not service_pool.service
        ):  # Maybe an inconsistent value? (must not, but if no ref integrity in db, maybe someone hand-changed something.. ;)")
            logger.error('Found service pool %s without service', service_pool.name)
            service_pool.delete()  # Just remove it "a las bravas", the best we can do
            return

        # Get publications in course...., that only can be one :)
        logger.debug('Removal process of %s', service_pool)

        publishing = service_pool.publications.filter(state=State.PREPARING)
        for pub in publishing:
            pub.cancel()
        # Now all publishments are canceling, let's try to cancel cache and assigned
        uServices: collections.abc.Iterable[UserService] = service_pool.userServices.filter(
            state=State.PREPARING
        )
        for userService in uServices:
            logger.debug('Canceling %s', userService)
            userService.cancel()
        # Nice start of removal, maybe we need to do some limitation later, but there should not be too much services nor publications cancelable at once
        service_pool.state = State.REMOVING
        service_pool.state_date = sql_datetime()  # Now
        service_pool.name += ' (removed)'
        service_pool.save(update_fields=['state', 'state_date', 'name'])

    def continue_removal_of(self, servicePool: ServicePool) -> None:
        # get current time
        now = sql_datetime()

        # Recheck that there is no publication created just after "startRemovalOf"
        try:
            for pub in servicePool.publications.filter(state=State.PREPARING):
                pub.cancel()
        except Exception:  # nosec: Dont care if we fail here, we will try again later
            pass

        try:
            # Now all publications are canceling, let's try to cancel cache and assigned also
            uServices: collections.abc.Iterable[UserService] = servicePool.userServices.filter(
                state=State.PREPARING
            )
            for userService in uServices:
                logger.debug('Canceling %s', userService)
                userService.cancel()
        except Exception:  # nosec: Dont care if we fail here, we will try again later
            pass

        # First, we remove all publications and user services in "info_state"
        with transaction.atomic():
            servicePool.userServices.select_for_update().filter(
                state__in=State.INFO_STATES
            ).delete()

        # Mark usable user services as removable, as batch
        with transaction.atomic():
            servicePool.userServices.select_for_update().filter(
                state=State.USABLE
            ).update(state=State.REMOVABLE, state_date=now)

        # When no service is at database, we start with publications
        if servicePool.userServices.all().count() == 0:
            try:
                logger.debug('All services removed, checking active publication')
                if servicePool.active_publication() is not None:
                    logger.debug('Active publication found, unpublishing it')
                    servicePool.unpublish()
                else:
                    logger.debug(
                        'No active publication found, removing info states and checking if removal is done'
                    )
                    servicePool.publications.filter(
                        state__in=State.INFO_STATES
                    ).delete()
                    if servicePool.publications.count() == 0:
                        servicePool.removed()  # Mark it as removed, let model decide what to do
            except Exception:
                logger.exception('Cought unexpected exception at continueRemovalOf: ')

    def force_removal_of(self, servicePool: ServicePool) -> None:
        # Simple remove all publications and user services, without checking anything
        # Log userServices forcet to remove
        logger.warning(
            'Service %s has been in removing state for too long, forcing removal',
            servicePool.name,
        )
        for userService in servicePool.userServices.all():
            logger.warning('Force removing user service %s', userService)
            userService.delete()
        servicePool.userServices.all().delete()
        for publication in servicePool.publications.all():
            logger.warning('Force removing %s', publication)
            publication.delete()

        servicePool.removed()  # Mark it as removed, let model decide what to do

    def run(self) -> None:
        # First check if there is someone in "removable" estate
        removableServicePools: collections.abc.Iterable[
            ServicePool
        ] = ServicePool.objects.filter(state=State.REMOVABLE).order_by('state_date')[
            :10
        ]

        for servicePool in removableServicePools:
            try:
                # Skips checking deployed services in maintenance mode
                if servicePool.is_in_maintenance() is False:
                    self.start_removal_of(servicePool)
            except Exception as e1:
                logger.error('Error removing service pool %s: %s', servicePool.name, e1)
                try:
                    servicePool.delete()
                except Exception as e2:
                    logger.error('Could not delete %s', e2)

        removingServicePools: collections.abc.Iterable[ServicePool] = ServicePool.objects.filter(
            state=State.REMOVING
        ).order_by('state_date')[:10]
        # Check if they have been removing for a long time.
        # Note. if year is 1972, it comes from a previous version, set state_date to now
        # If in time and not in maintenance mode, continue removing
        for servicePool in removingServicePools:
            try:
                if servicePool.state_date.year == 1972:
                    servicePool.state_date = sql_datetime()
                    servicePool.save(update_fields=['state_date'])
                if servicePool.state_date < sql_datetime() - timedelta(
                    seconds=MAX_REMOVING_TIME
                ):
                    self.force_removal_of(servicePool)  # Force removal

                # Skips checking deployed services in maintenance mode
                if servicePool.is_in_maintenance() is False:
                    self.continue_removal_of(servicePool)
            except Exception:
                logger.exception('Removing deployed service')
