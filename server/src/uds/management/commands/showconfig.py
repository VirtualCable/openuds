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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import argparse
import logging
import typing
import collections.abc
import csv
import yaml

from django.core.management.base import BaseCommand
from uds.core.util import config

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Show current PUBLIC configuration of UDS broker (passwords are not shown)"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            '--csv',
            action='store_true',
            dest='csv',
            default=False,
            help='Shows configuration in CVS format',
        )
        parser.add_argument(
            '--yaml',
            action='store_true',
            dest='yaml',
            default=False,
            help='Shows configuration in YAML format',
        )

    def handle(self, *args: typing.Any, **options: typing.Any) -> None:
        logger.debug("Show settings")
        config.GlobalConfig.initialize()
        try:
            writer: typing.Any = None
            if options['csv']:
                # Print header
                writer = csv.writer(self.stdout, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                writer.writerow(['Section', 'Name', 'Value'])
            elif options['yaml']:
                writer = {}  # Create a dict to store data, and write at the end
            # Get sections, key, value as a list of tuples
            for section, data in config.Config.get_config_values().items():
                for key, value in data.items():
                    # value is a dict, get 'value' key
                    if options['csv']:
                        writer.writerow([section, key, value['value']])
                    elif options['yaml']:
                        if section not in writer:
                            writer[section] = {}
                        writer[section][key] = value['value']
                    else:
                        v = value['value'].replace('\n', '\\n')
                        self.stdout.write(f'{section}.{key}="{v}"')
            if options['yaml']:
                self.stdout.write(yaml.safe_dump(writer, default_flow_style=False))
        except Exception as e:
            self.stdout.write(f'The command could not be processed: {e}')
            self.stdout.flush()
            logger.exception('Exception processing %s', args)
