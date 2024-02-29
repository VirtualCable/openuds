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
import collections.abc
import logging

from uds.core.util import factory

from .provider import ServiceProvider
from .service import Service


logger = logging.getLogger(__name__)


class ServiceProviderFactory(factory.ModuleFactory[ServiceProvider]):
    """
    This class holds the register of all known service provider modules
    inside UDS.

    It provides a way to register and recover providers providers.
    """

    def insert(self, type_: type[ServiceProvider]) -> None:
        """
        Inserts type_ as a service provider
        """
        # Before inserting type, we will make a couple of sanity checks
        # We could also check if it provides at least a service, but
        # for debugging purposes, it's better to not check that
        # We will check that if service provided by "provider" needs
        # cache, but service do not provides publication_type,
        # that service will not be registered and it will be informed
        type_name = type_.get_type().lower()

        if type_name in self.providers():
            logger.debug('%s already registered as Service Provider', type_)
            return

        # Fix offers by checking if they are valid
        offers: list[type['Service']] = []
        for s in type_.offers:
            if s.uses_cache_l2:
                s.uses_cache = True   # Ensures uses cache is true
                if s.publication_type is None:
                    logger.error(
                        'Provider %s offers %s, but %s needs cache and do not have publication_type defined',
                        type_,
                        s,
                        s,
                    )
                    continue
            offers.append(s)

        # Store fixed offers
        type_.offers = offers

        super().insert(type_)


    def services_not_needing_publication(self) -> collections.abc.Iterable[type[Service]]:
        """
        Returns a list of all service providers registered that do not need
        to be published
        """
        return [
            s
            for p in self.providers().values()
            for s in p.offers
            if s.publication_type is None and s.must_assign_manually is False
        ]
        # old code :-)
        # res = []
        # for p in self.providers().values():
        #     for s in p.offers:
        #         if s.publication_type is None and s.must_assign_manually is False:
        #             res.append(s)
        # return res
