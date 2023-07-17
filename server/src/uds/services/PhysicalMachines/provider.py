# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2021 Virtual Cable S.L.U.
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
import configparser
import logging
import typing

from django.utils.translation import gettext_noop as _

import dns.resolver

from uds.core import services, exceptions
from uds.core.ui.user_interface import gui
from uds.core.util import net
from uds.core.util import log

if typing.TYPE_CHECKING:
    from uds.core.module import Module

logger = logging.getLogger(__name__)

VALID_CONFIG_SECTIONS = set(('wol',))


class PhysicalMachinesProvider(services.ServiceProvider):
    # What services do we offer?
    typeName = _('Static IP Machines Provider')
    typeType = 'PhysicalMachinesServiceProvider'
    typeDescription = _('Provides connection to machines by IP')
    iconFile = 'provider.png'

    # No extra data needed
    config = gui.TextField(
        length=8192,
        multiline=6,
        label=_('Advanced configuration'),
        order=3,
        tooltip=_('Advanced configuration data for the provider'),
        required=False,
        tab=gui.Tab.ADVANCED,
    )

    def initialize(self, values: 'Module.ValuesType') -> None:
        """checks and initializes values

        Args:
            values (Module.ValuesType): List of values on initialization (maybe None)

        Raises:
            exceptions.ValidationException
        """
        if values is None:
            return

        self.config.value = self.config.value.strip()

        if self.config.value:
            config = configparser.ConfigParser()
            try:
                config.read_string(self.config.value)
                # Seems a valid configuration file, let's see if all se
            except Exception as e:
                raise exceptions.ValidationError(
                    _('Invalid advanced configuration: ') + str(e)
                )

            for section in config.sections():
                if section not in VALID_CONFIG_SECTIONS:
                    raise exceptions.ValidationError(
                        _('Invalid section in advanced configuration: ') + section
                    )

            # Sections are valid, check values
            # wol section
            for key in config['wol']:
                try:
                    net.networksFromString(key)  # Raises exception if net is invalid
                except Exception:
                    raise exceptions.ValidationError(
                        _('Invalid network in advanced configuration: ') + key
                    ) from None
                # Now check value is an url
                if config['wol'][key][:4] != 'http':
                    raise exceptions.ValidationError(
                        _('Invalid url in advanced configuration: ') + key
                    )

    from .service_multi import IPMachinesService  # pylint: disable=import-outside-toplevel
    from .service_single import IPSingleMachineService  # pylint: disable=import-outside-toplevel

    offers = [IPMachinesService, IPSingleMachineService]

    def wolURL(self, ip: str, mac: str) -> str:
        """Tries to get WOL server for indicated IP

        Args:
            ip (str): ip of target machine

        Returns:
            str: URL of WOL server or empty ('') if no server for the ip is found
        """
        if not self.config.value or not ip or not mac:
            return ''

        # If ip is in fact a hostname...
        if not net.ipToLong(ip).version:
            # Try to resolve name...
            try:
                # Prefer ipv4
                res: typing.Any = dns.resolver.resolve(ip)
                ip = res[0].address
            except Exception:
                # Try ipv6
                try:
                    res = dns.resolver.resolve(ip, 'AAAA')
                    ip = res[0].address
                except Exception as e:
                    self.doLog(log.LogLevel.WARNING, f'Name {ip} could not be resolved')
                    logger.warning('Name %s could not be resolved (%s)', ip, e)
                    return ''

        try:
            config = configparser.ConfigParser()
            config.read_string(self.config.value)
            for key in config['wol']:
                if net.contains(key, ip):
                    return config['wol'][key].replace('{MAC}', mac).replace('{IP}', ip)

        except Exception as e:
            logger.error('Error parsing advanced configuration: %s', e)

        return ''

    def __str__(self):
        return "Physical Machines Provider"
