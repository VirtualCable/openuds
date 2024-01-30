# -*- coding: utf-8 -*-
#
# Copyright (c) 2017-2021 Virtual Cable S.L.U.
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
import collections.abc

from uds.core.services import Publication
from uds.core.types.states import State
from uds.core.util import autoserializable
from uds.core.util.model import sql_datetime

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from .service import OGService

logger = logging.getLogger(__name__)


class OpenGnsysPublication(Publication, autoserializable.AutoSerializable):
    """
    This class provides the publication of a oVirtLinkedService
    """

    suggested_delay = (
        5  # : Suggested recheck time if publication is unfinished in seconds
    )

    def service(self) -> 'OGService':
        return typing.cast('OGService', super().service())

    def publish(self) -> str:
        """
        Realizes the publication of the service, on OpenGnsys, does nothing
        """
        return State.FINISHED

    def check_state(self) -> str:
        """
        Checks state of publication creation
        """
        return State.FINISHED

    def error_reason(self) -> str:
        return 'No error possible :)'

    def destroy(self) -> str:
        return State.FINISHED

    def cancel(self) -> str:
        return self.destroy()
