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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import typing
import logging

from .provider import ServiceProvider
from .service import Service

logger = logging.getLogger(__name__)


class ServiceProviderFactory:
    """
    This class holds the register of all known service provider modules
    inside UDS.

    It provides a way to register and recover providers providers.
    """
    _factory: typing.Optional['ServiceProviderFactory'] = None

    def __init__(self):
        """
        Initializes internal dictionary for service providers registration
        """
        self._providers: typing.Dict[str, typing.Type[ServiceProvider]] = {}

    @staticmethod
    def factory() -> 'ServiceProviderFactory':
        """
        Returns the factory that keeps the register of service providers.
        """
        if ServiceProviderFactory._factory is None:
            ServiceProviderFactory._factory = ServiceProviderFactory()
        return ServiceProviderFactory._factory

    def providers(self) -> typing.Dict[str, typing.Type[ServiceProvider]]:
        """
        Returns the list of service providers already registered.
        """
        return self._providers

    def insert(self, type_: typing.Type[ServiceProvider]) -> None:
        """
        Inserts type_ as a service provider
        """
        # Before inserting type, we will make a couple of sanity checks
        # We could also check if it provides at least a service, but
        # for debugging purposes, it's better to not check that
        # We will check that if service provided by "provider" needs
        # cache, but service do not provides publicationType,
        # that service will not be registered and it will be informed
        typeName = type_.type().lower()
        if typeName in self._providers:
            logger.debug('%s already registered as Service Provider', type_)
            return

        offers = []
        for s in type_.offers:
            if s.usesCache_L2 is True:
                s.usesCache = True
                if s.publicationType is None:
                    logger.error('Provider %s offers %s, but %s needs cache and do not have publicationType defined', type_, s, s)
                    continue
            offers.append(s)

        # Only offers valid services
        type_.offers = offers
        logger.debug('Adding provider %s as %s', type_.type(), type_)

        self._providers[typeName] = type_

    def lookup(self, typeName) -> typing.Optional[typing.Type[ServiceProvider]]:
        """
        Tries to locate a server provider and by its name, and, if
        not found, returns None
        """
        return self._providers.get(typeName.lower(), None)

    def servicesThatDoNotNeedPublication(self) -> typing.Iterable[typing.Type[Service]]:
        """
        Returns a list of all service providers registered that do not need
        to be published
        """
        res = []
        for p in self._providers.values():
            for s in p.offers:
                if s.publicationType is None and s.mustAssignManually is False:
                    res.append(s)
        return res
