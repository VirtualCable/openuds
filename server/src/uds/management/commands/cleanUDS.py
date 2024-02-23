# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2023 Virtual Cable S.L.U.
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
import sys
import typing

from django.core.management.base import BaseCommand
from django.core.cache import cache

from uds.core.util.config import GlobalConfig
from uds.core.util.cache import Cache
from uds.core.types.states import State
from uds.models import Scheduler


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    args = "None"
    help = "Clean up all uneeded data from UDS (cache, ...). This is mainly used for versions installations, so he have clean data"

    def handle(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        sys.stdout.write("Cleaning up UDS\n")
        GlobalConfig.initialize()

        sys.stdout.write("Cache...\n")
        # UDSs cache
        Cache.purge_outdated()
        # Django caches
        cache.clear()

        sys.stdout.write("Releasing schedulers...\n")
        # Release all Schedulers
        Scheduler.objects.all().update(owner_server='', state=State.FOR_EXECUTE)

        sys.stdout.write("UDS Cleaned UP\n")
