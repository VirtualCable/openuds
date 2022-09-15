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
import logging
import typing
import csv

from django.core.management.base import BaseCommand
from uds.core.util import config

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    args = "<mod.name=value mod.name=value mod.name=value...>"
    help = "Updates configuration values. If mod is omitted, UDS will be used. Omit whitespaces betwen name, =, and value (they must be a single param)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--csv',
            action='store_true',
            dest='csv',
            default=False,
            help='Shows configuration in CVS format',
        )

    def handle(self, *args, **options):
        logger.debug("Show settings")
        config.GlobalConfig.initialize()
        try:
            writer: typing.Any = None
            if options['csv']:
                # Print header
                writer = csv.writer(self.stdout, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                writer.writerow(['Section', 'Name', 'Value'])
                
            # Get sections, key, value as a list of tuples
            for section, data in config.Config.getConfigValues().items():
                for key, value in data.items():
                    # value is a dict, get 'value' key
                    if options['csv']:
                        writer.writerow([section, key, value['value']])
                    else:
                        v = value['value'].replace('\n', '\\n')
                        print(f'{section}.{key}="{v}"')

        except Exception as e:
            print('The command could not be processed: {}'.format(e))
            logger.exception('Exception processing %s', args)
