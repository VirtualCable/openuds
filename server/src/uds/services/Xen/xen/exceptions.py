# -*- coding: utf-8 -*-
#
# Copyright (c) 2014-2024 Virtual Cable S.L.U.
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

import XenAPI  # pyright: ignore

from uds.core.services.generics import exceptions

logger = logging.getLogger(__name__)


class XenFault(exceptions.Error):
    pass


class XenFailure(XenAPI.Failure, XenFault):
    exBadVmPowerState = 'VM_BAD_POWER_STATE'
    exVmMissingPVDrivers = 'VM_MISSING_PV_DRIVERS'
    exHandleInvalid = 'HANDLE_INVALID'
    exHostIsSlave = 'HOST_IS_SLAVE'
    exSRError = 'SR_BACKEND_FAILURE_44'

    def __init__(self, details: typing.Optional[list[typing.Any]] = None):
        details = [] if details is None else details
        super(XenFailure, self).__init__(details)

    def isHandleInvalid(self) -> bool:
        return typing.cast(typing.Any, self.details[0]) == XenFailure.exHandleInvalid

    def needs_xen_tools(self) -> bool:
        return typing.cast(typing.Any, self.details[0]) == XenFailure.exVmMissingPVDrivers

    def bad_power_state(self) -> bool:
        return typing.cast(typing.Any, self.details[0]) == XenFailure.exBadVmPowerState

    def is_slave(self) -> bool:
        return typing.cast(typing.Any, self.details[0]) == XenFailure.exHostIsSlave

    def as_human_readable(self) -> str:
        try:
            error_list = {
                XenFailure.exBadVmPowerState: 'Machine state is invalid for requested operation (needs {2} and state is {3})',
                XenFailure.exVmMissingPVDrivers: 'Machine needs Xen Server Tools to allow requested operation',
                XenFailure.exHostIsSlave: 'The connected host is an slave, try to connect to {1}',
                XenFailure.exSRError: 'Error on SR: {2}',
                XenFailure.exHandleInvalid: 'Invalid reference to {1}',
            }
            err = error_list.get(typing.cast(typing.Any, self.details[0]), 'Error {0}')

            return err.format(*typing.cast(list[typing.Any], self.details))
        except Exception:
            return 'Unknown exception: {0}'.format(self.details)

    def __str__(self) -> str:
        return self.as_human_readable()


class XenException(XenFault):
    def __init__(self, message: typing.Any):
        XenFault.__init__(self, message)
        logger.debug('Exception create: %s', message)


class XenNotFoundError(XenException, exceptions.NotFoundError):
    def __init__(self, message: typing.Any):
        XenException.__init__(self, message)
        logger.debug('Not found exception create: %s', message)

class XenFatalError(XenException, exceptions.FatalError):
    def __init__(self, message: typing.Any):
        XenException.__init__(self, message)
        logger.debug('Fatal exception create: %s', message)