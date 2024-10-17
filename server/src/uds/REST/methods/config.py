# -*- coding: utf-8 -*-

#
# Copyright (c) 2014-2019 Virtual Cable S.L.
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
import typing
import logging

from uds.core.util.config import Config as CfgConfig
from uds.REST import Handler


logger = logging.getLogger(__name__)


# Enclosed methods under /config path
class Config(Handler):
    needs_admin = True  # By default, staff is lower level needed

    def get(self) -> typing.Any:
        return CfgConfig.get_config_values(self.is_admin())

    def put(self) -> typing.Any:
        for section, section_dict in typing.cast(dict[str, dict[str, dict[str, str]]], self._params).items():
            for key, vals in section_dict.items():
                config = CfgConfig.update(CfgConfig.SectionType.from_str(section), key, vals['value'])
                if config is not None:
                    logger.info(
                        'Updating config value %s.%s to %s by %s',
                        section,
                        key,
                        vals['value'] if not config.is_password else '********',
                        self._user.name,
                    )
                else:
                    logger.error('Non existing config value %s.%s to %s by %s', section, key, vals['value'], self._user.name)
        return 'done'
