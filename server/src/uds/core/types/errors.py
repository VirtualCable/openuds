# -*- coding: utf-8 -*-

#
# Copyright (c) 2024 Virtual Cable S.L.U.
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
import enum
import logging
import traceback

from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


class Error(enum.IntEnum):
    UNKNOWN_ERROR = 0
    TRANSPORT_NOT_FOUND = 1
    SERVICE_NOT_FOUND = 2
    ACCESS_DENIED = 3
    INVALID_SERVICE = 4
    MAX_SERVICES_REACHED = 5
    COOKIES_NEEDED = 6
    ERR_USER_SERVICE_NOT_FOUND = 7
    AUTHENTICATOR_NOT_FOUND = 8
    INVALID_CALLBACK = 9
    INVALID_REQUEST = 10
    BROWSER_NOT_SUPPORTED = 11
    SERVICE_IN_MAINTENANCE = 12
    SERVICE_NOT_READY = 13
    SERVICE_IN_PREPARATION = 14
    SERVICE_CALENDAR_DENIED = 15
    PAGE_NOT_FOUND = 16
    INTERNAL_SERVER_ERROR = 17
    RELOAD_NOT_SUPPORTED = 18
    INVALID_MFA_CODE = 19

    @property
    def message(self) -> str:
        try:
            return ERROR_STRINGS[self.value]
        except IndexError:
            return ERROR_STRINGS[0]

    @staticmethod
    def from_int(value: int) -> 'Error':
        try:
            return Error(value)
        except ValueError:
            return Error.UNKNOWN_ERROR

    @staticmethod
    def from_exception(exception: Exception) -> 'Error':
        from uds.core.exceptions.auth import (
            InvalidUserException,
            InvalidAuthenticatorException,
        )
        from uds.core.services.exceptions import (
            InvalidServiceException,
            MaxServicesReachedError,
            ServiceInMaintenanceMode,
            ServiceNotReadyError,
        )
        from uds.models import UserService, Transport, ServicePool, Authenticator

        trans_dct: dict[type, Error] = {
            InvalidUserException: Error.ACCESS_DENIED,
            InvalidAuthenticatorException: Error.INVALID_CALLBACK,
            InvalidServiceException: Error.INVALID_SERVICE,
            MaxServicesReachedError: Error.MAX_SERVICES_REACHED,
            ServiceInMaintenanceMode: Error.SERVICE_IN_MAINTENANCE,
            ServiceNotReadyError: Error.SERVICE_NOT_READY,
            UserService.DoesNotExist: Error.ERR_USER_SERVICE_NOT_FOUND,
            Transport.DoesNotExist: Error.TRANSPORT_NOT_FOUND,
            ServicePool.DoesNotExist: Error.SERVICE_NOT_FOUND,
            Authenticator.DoesNotExist: Error.AUTHENTICATOR_NOT_FOUND,
        }

        try:
            return trans_dct[type(exception)]
        except KeyError:
            logger.error('Unexpected exception: %s, traceback: %s', exception, traceback.format_exc())
            return Error.UNKNOWN_ERROR


ERROR_STRINGS: typing.Final[list[str]] = [
    _('Unknown error'),
    _('Transport not found'),
    _('Service not found'),
    _('Access denied'),
    _('Invalid service. The service is not available at this moment. Please, try later'),
    _('Maximum services limit reached. Please, contact administrator'),
    _('You need to enable cookies to let this application work'),
    _('User service not found'),
    _('Authenticator not found'),
    _('Invalid authenticator'),
    _('Invalid request received'),
    _('Your browser is not supported. Please, upgrade it to a modern HTML5 browser like Firefox or Chrome'),
    _('The requested service is in maintenance mode'),
    _('The service is not ready.\nPlease, try again in a few moments.'),
    _('Preparing service'),
    _('Service access denied by calendars'),
    _('Page not found'),
    _('Unexpected error'),
    _('Reloading this page is not supported. Please, reopen service from origin.'),
    _('Invalid Multi-Factor Authentication code'),
]
