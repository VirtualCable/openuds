#
# Copyright (c) 2012-2020 Virtual Cable S.L.U.
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

from uds.core.environment import Environmentable
from uds.core.util.config import Config


logger = logging.getLogger(__name__)


class Job(Environmentable):
    __slots__ = ('frequency',)
    # Default frecuency, once a day. Remenber that precision will be based on "granurality" of Scheduler
    # If a job is used for delayed execution, this attribute is in fact ignored
    frecuency: typing.ClassVar[int] = (
        24 * 3600 + 3
    )  # Defaults to a big one, and i know frecuency is written as frequency, but this is an "historical mistake" :)
    frecuency_cfg: typing.ClassVar[
        typing.Optional[Config.Value]
    ] = None  # If we use a configuration variable from DB, we need to update the frecuency asap, but not before app is ready
    friendly_name: typing.ClassVar[str] = 'Unknown'

    @classmethod
    def setup(cls: typing.Type['Job']) -> None:
        """
        Sets ups frequency from configuration values
        """
        if cls.frecuency_cfg:
            try:
                cls.frecuency = cls.frecuency_cfg.getInt(force=True)
                logger.debug(
                    'Setting frequency from DB setting for %s to %s', cls, cls.frecuency
                )
            except Exception as e:
                logger.error(
                    'Error setting default frequency for %s ()%s. Got default value of %s',
                    cls,
                    e,
                    cls.frecuency,
                )

    def execute(self) -> None:
        try:
            self.run()
        except Exception:
            logger.exception('Job %s raised an exception:', self.__class__)

    def run(self) -> None:
        """
        You must provide your own "run" method to do whatever you need
        """
        logging.debug("Base run of job called for class %s", self.__class__)
