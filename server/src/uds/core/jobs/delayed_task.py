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

from uds.core.environment import Environmentable, Environment

logger = logging.getLogger(__name__)


class DelayedTask(Environmentable):
    """
    This class represents a single delayed task object.
    This is an object that represents an execution to be done "later"
    """
    __slots__ = ()

    def __init__(self, environment: typing.Optional[Environment] = None) -> None:
        """
        Remember to invoke parent init in derived clases using super(myClass,self).__init__() to let this initialize its own variables
        """
        super().__init__(environment or Environment.getEnvForType(self.__class__))

    def execute(self) -> None:
        """
        Executes the job
        """
        try:
            self.run()
        except Exception as e:
            logger.error('Job %s raised an exception: %s', self.__class__, e)

    def run(self) -> None:
        """
        Run method, executes your code. Override this on your classes
        """
        logging.error("Base run of job called for class")
        raise NotImplementedError

    def register(self, suggestedTime: int, tag: str = '', check: bool = True) -> None:
        """
        Utility method that allows to register a Delayedtask
        """
        from .delayed_task_runner import DelayedTaskRunner  # pylint: disable=import-outside-toplevel

        if check and DelayedTaskRunner.runner().checkExists(tag):
            return

        DelayedTaskRunner.runner().insert(self, suggestedTime, tag)
