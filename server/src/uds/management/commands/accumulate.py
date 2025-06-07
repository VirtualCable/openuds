# -*- coding: utf-8 -*-

#
# Copyright (c) 2022-2023 Virtual Cable S.L.U.
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

from uds.core import environment
from uds.workers.stats_collector import StatsAccumulator

if typing.TYPE_CHECKING:
    import argparse

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Executes the stats collector acummulator, that updates the stats counters accum table with the current stats counters'

    verbose: bool = True
    filter_args: list[tuple[str, str]] = []

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        
    def add_arguments(self, parser: 'argparse.ArgumentParser') -> None:

        # quiet mode
        parser.add_argument(
            '--quiet',
            action='store_false',
            dest='verbose',
            default=True,
            help='Quiet mode',
        )
        

    def handle(self, *args: typing.Any, **options: typing.Any) -> None:
        self.verbose = options['verbose']

        if self.verbose:
            self.stderr.write(f'Accumulating stats counters')
            logging.getLogger('uds').setLevel(logging.DEBUG)
            # Output also to stderr
            logging.getLogger('uds').addHandler(logging.StreamHandler(self.stderr))

        # Create the accumulator
        accumulator = StatsAccumulator(environment=environment.Environment.temporary_environment())
        accumulator.run()

        if self.verbose:
            self.stderr.write('Stats counters accumulated successfully')
