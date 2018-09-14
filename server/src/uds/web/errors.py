# -*- coding: utf-8 -*-

#
# Copyright (c) 2012 Virtual Cable S.L.
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
from __future__ import unicode_literals

from django.utils.translation import ugettext_lazy as _
from django.shortcuts import render

from django.http import HttpResponseRedirect
from django.urls import reverse

from uds.core.util import encoders
from uds.models import DeployedService, Transport, UserService, Authenticator

import traceback
import logging

logger = logging.getLogger(__name__)

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
BROWSER_NOT_SUPPORTED = 11,
SERVICE_IN_MAINTENANCE = 12
SERVICE_NOT_READY = 13
SERVICE_IN_PREPARATION = 14
SERVICE_CALENDAR_DENIED = 15
PAGE_NOT_FOUND = 16
INTERNAL_SERVER_ERROR = 17

strings = [
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
]


def errorString(errorId):
    errorId = int(errorId)
    if errorId < len(strings):
        return strings[errorId]
    return strings[0]


def errorView(request, error):
    idError = int(error)
    code = (error >> 8) & 0xFF

    errStr = errorString(idError)
    if code != 0:
        errStr += ' (code {0:04X})'.format(code)

    errStr = encoders.encode(str(errStr), 'base64', asText=True)[:-1]

    return HttpResponseRedirect(reverse('page.error', kwargs={'error': errStr}))


def exceptionView(request, exception):
    """
    Tries to render an error page with error information
    """
    from uds.core.auths.Exceptions import InvalidUserException, InvalidAuthenticatorException
    from uds.core.services.Exceptions import InvalidServiceException, MaxServicesReachedError, ServiceInMaintenanceMode, ServiceNotReadyError

    logger.error(traceback.format_exc())

    try:
        raise exception
    except UserService.DoesNotExist:
        return errorView(request, ERR_USER_SERVICE_NOT_FOUND)
    except DeployedService.DoesNotExist:
        return errorView(request, SERVICE_NOT_FOUND)
    except Transport.DoesNotExist:
        return errorView(request, TRANSPORT_NOT_FOUND)
    except Authenticator.DoesNotExist:
        return errorView(request, AUTHENTICATOR_NOT_FOUND)
    except InvalidUserException:
        return errorView(request, ACCESS_DENIED)
    except InvalidServiceException:
        return errorView(request, INVALID_SERVICE)
    except MaxServicesReachedError:
        return errorView(request, MAX_SERVICES_REACHED)
    except InvalidAuthenticatorException:
        return errorView(request, INVALID_CALLBACK)
    except ServiceInMaintenanceMode:
        return errorView(request, SERVICE_IN_MAINTENANCE)
    except ServiceNotReadyError as e:
        # add code as high bits of idError
        return errorView(request, e.code << 8 | SERVICE_NOT_READY)
    except Exception as e:
        logger.exception('Exception cautgh at view!!!')
        raise e


def error(request, error):
    """
    Error view, responsible of error display
    :param request:
    :param idError:
    """
    return render(request, 'uds/modern/index.html', {})

    # idError = int(idError)
    # code = idError >> 8
    # idError &= 0xFF

    # errStr = errorString(idError)
    # if code != 0:
    #     errStr += ' (code {0:04X})'.format(code)

    # return render(request, theme.template('error.html'), {'errorString': errStr})
