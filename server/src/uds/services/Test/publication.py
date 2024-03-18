# -*- coding: utf-8 -*-

#
# Copyright (c) 2022 Virtual Cable S.L.U.
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
import random
import string
import logging
import dataclasses
import typing

from django.utils.translation import gettext as _
from uds.core import services, types

logger = logging.getLogger(__name__)

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    pass


class TestPublication(services.Publication):
    """
    Simple test publication 
    """
    suggested_delay = (
        5  # : Suggested recheck time if publication is unfinished in seconds
    )
    
    # Data to store
    @dataclasses.dataclass
    class Data:
        name: str = ''
        state: str = ''
        reason: str = ''
        number: int = -1
        other: str = ''
        other2: str = 'other2'


    data: Data = Data()

    def initialize(self) -> None:
        """
        This method will be invoked by default __init__ of base class, so it gives
        us the oportunity to initialize whataver we need here.

        In our case, we setup a few attributes..
        """

        # We do not check anything at marshal method, so we ensure that
        # default values are correctly handled by marshal.
        self.data.name = ''.join(random.choices(string.ascii_letters, k=8))
        self.data.state = types.states.TaskState.RUNNING
        self.data.reason = 'none'
        self.data.number = 10

    def publish(self) -> types.states.TaskState:
        logger.info('Publishing publication %s: %s remaining',self.data.name, self.data.number)
        self.data.number -= 1

        if self.data.number <= 0:
            self.data.state = types.states.TaskState.FINISHED
        return types.states.TaskState.from_str(self.data.state)

    def finish(self) -> None:
        # Make simply a random string
        logger.info('Finishing publication %s', self.data.name)
        self.data.number = 0
        self.data.state = types.states.TaskState.FINISHED

    def error_reason(self) -> str:
        return self.data.reason

    def destroy(self) -> types.states.TaskState:
        logger.info('Destroying publication %s', self.data.name)
        return types.states.TaskState.FINISHED

    def cancel(self) -> types.states.TaskState:
        logger.info('Canceling publication %s', self.data.name)
        return self.destroy()

    # Here ends the publication needed methods.
    # Methods provided below are specific for this publication
    # and will be used by user deployments that uses this kind of publication

    def get_basename(self) -> str:
        """
        This sample method (just for this sample publication), provides
        the name generater for this publication. This is just a sample, and
        this will do the work
        """
        return self.data.name
