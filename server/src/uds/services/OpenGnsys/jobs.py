# -*- coding: utf-8 -*-

#
# Copyright (c) 2017-2019 Virtual Cable S.L.
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

"""
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
"""
import datetime
import logging
import typing

from django.utils.translation import gettext_noop as _

from uds.core import jobs
from uds import models

from .provider import OGProvider
from .service import OGService

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.module import Module

logger = logging.getLogger(__name__)


class OpenGnsysMaintainer(jobs.Job):
    frecuency = 60 * 60 * 4  # Once every 4 hours
    friendly_name = 'OpenGnsys cache renewal job'

    def run(self) -> None:
        logger.debug('Looking for OpenGnsys renewable cache elements')

        # Look for Providers of type VMWareVCServiceProvider
        provider: models.Provider
        for provider in models.Provider.objects.filter(
            maintenance_mode=False, data_type=OGProvider.typeType
        ):
            logger.debug('Provider %s is type openGnsys', provider)

            # Locate all services inside the provider
            service: models.Service
            for service in provider.services.all():
                instance: OGService = typing.cast(OGService, service.getInstance())
                since = models.getSqlDatetime() - datetime.timedelta(
                    hours=instance.maxReservationTime.num() - 8
                )  # If less than 8 hours of reservation...
                # Now mark for removal every CACHED service that is about to expire its reservation on OpenGnsys
                userService: models.UserService
                for userService in models.UserService.objects.filter(
                    deployed_service__service=service,
                    creation_date__lt=since,
                    cache_level=1,
                ):
                    logger.info(
                        'The cached user service %s is about to expire. Removing it so it can be recreated',
                        userService,
                    )
                    userService.remove()

        logger.debug('OpenGnsys job finished')
