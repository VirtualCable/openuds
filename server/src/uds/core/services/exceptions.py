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

from uds.core.exceptions import UDSException

if typing.TYPE_CHECKING:
    from uds.models import UserService, Transport


class ServiceException(UDSException):
    """
    Base class for all service exceptions
    """

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        # Eats "kwargs" to avoid "unexpected keyword argument" error
        super().__init__(*args, **kwargs)


class UnsupportedException(ServiceException):
    """
    Reflects that we request an operation that is not supported, i.e. Cancel a publication with snapshots
    """


class OperationException(ServiceException):
    """
    Reflects that the operation requested can't be acomplished, i.e. remove an snapshot without snapshot reference, cancel non running operation, etc...
    """


class PublishException(ServiceException):
    """
    Reflects thate the publication can't be done for causes we don't know in advance
    """


class DeploymentException(ServiceException):
    """
    Reflects that a deployment of a service (at cache, or assigned to user) can't be done for causes we don't know in advance
    """


class CancelException(ServiceException):
    """
    Reflects that a "cancel" operation can't be done for some reason
    """


class InvalidServiceException(ServiceException):
    """
    Invalid service specified. The service is not ready
    """


class MaxServicesReachedError(ServiceException):
    """
    Number of maximum services has been reached, and no more services
    can be created for users.
    """


class ServiceInMaintenanceMode(ServiceException):
    """
    The service is in maintenance mode and can't be accesed right now
    """


class ServiceAccessDeniedByCalendar(ServiceException):
    """
    This service can't be accessed right now, probably due to date-time restrictions
    """


class ServiceNotReadyError(ServiceException):
    """
    The service is not ready
    Can include an optional code error
    """

    code: int
    user_service: typing.Optional['UserService']
    transport: typing.Optional['Transport']

    def __init__(
        self,
        *,
        code: int = 0x0000,
        user_service: typing.Optional['UserService'] = None,
        transport: typing.Optional['Transport'] = None
    ):
        super().__init__()
        self.code = code
        self.user_service = user_service
        self.transport = transport
