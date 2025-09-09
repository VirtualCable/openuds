# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2019 Virtual Cable S.L.
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
import logging
import typing

from django.core.management.base import BaseCommand
from uds import models
from uds.core.util import unique_mac_generator

logger = logging.getLogger(__name__)

MIN_VERBOSITY: typing.Final[int] = 1  # Minimum verbosity to print freed macs



class Command(BaseCommand):
    help = "Execute maintenance tasks for UDS broker"

    def clean_unused_service_macs(self, service: models.Service) -> int:
        # Get all userservices from this service, extract their "unique_id" (the mac)
        # And store it in a set for later use
        self.stdout.write(f'Cleaning unused macs for service {service.name} (id: {service.id})\n')
        
        def mac_to_int(mac: str) -> int:
            try:
                return int(mac.replace(':', ''), 16)
            except Exception:
                return -1

        mac_gen = unique_mac_generator.UniqueMacGenerator(f't-service-{service.id}')

        used_macs = {
            mac_to_int(us.unique_id) for us in models.UserService.objects.filter(deployed_service__service=service)
        }

        counter = 0
        for seq in (
            models.UniqueId.objects.filter(basename='\tmac', assigned=True, owner=f't-service-{service.id}')
            .exclude(seq__in=used_macs)
            .values_list('seq', flat=True)
        ):
            counter += 1
            self.stdout.write(f'Freeing mac {mac_gen._to_mac_addr(seq)} for service {service.name}\n')
            mac_gen.free(mac_gen._to_mac_addr(seq))
            
        self.stdout.write(f'Freed {counter} macs for service {service.name}\n')
        logger.info('Freed %d macs for service %s', counter, service.name)
            
        return counter

    def handle(self, *args: typing.Any, **options: typing.Any) -> None:
        logger.debug('Maintenance called with args: %s, options: %s', args, options)

        counter = 0
        for service in models.Service.objects.all():
            try:
                counter += self.clean_unused_service_macs(service)
            except Exception as e:
                logger.error('Error doing maintenance for service %s: %s', service.name, e)
                self.stdout.write(f'Error doing maintenance for service {service.name}: {e}\n')

        logger.info('Maintenance finished, total freed macs: %d', counter)
        self.stdout.write(f'Total freed macs: {counter}\n')