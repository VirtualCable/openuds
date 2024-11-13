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

import functools
import logging
import typing
import collections.abc
import contextlib

import XenAPI  # pyright: ignore

from uds.core import exceptions

logger = logging.getLogger(__name__)


class XenFault(exceptions.services.generics.Error):
    pass


class XenFailure(XenAPI.Failure, XenFault):
    ex_bad_vm_power_state = 'VM_BAD_POWER_STATE'
    ex_vm_missing_pv_drivers = 'VM_MISSING_PV_DRIVERS'
    ex_handle_invalid = 'HANDLE_INVALID'
    ex_host_is_slave = 'HOST_IS_SLAVE'
    ex_sr_error = 'SR_BACKEND_FAILURE_44'
    ex_vm_lacks_feature= 'VM_LACKS_FEATUREVM_LACKS_FEATURE'

    def __init__(self, details: typing.Optional[list[typing.Any]] = None):
        details = [] if details is None else details
        super(XenFailure, self).__init__(details)

    def is_valid_handle(self) -> bool:
        return typing.cast(typing.Any, self.details[0]) == XenFailure.ex_handle_invalid

    def needs_xen_tools(self) -> bool:
        return typing.cast(typing.Any, self.details[0]) == XenFailure.ex_vm_missing_pv_drivers

    def bad_power_state(self) -> bool:
        return typing.cast(typing.Any, self.details[0]) == XenFailure.ex_bad_vm_power_state

    def is_slave(self) -> bool:
        return typing.cast(typing.Any, self.details[0]) == XenFailure.ex_host_is_slave

    def as_human_readable(self) -> str:
        try:
            error_list = {
                XenFailure.ex_bad_vm_power_state: 'Machine state is invalid for requested operation (needs {2} and state is {3})',
                XenFailure.ex_vm_missing_pv_drivers: 'Machine needs Xen Server Tools to allow requested operation',
                XenFailure.ex_host_is_slave: 'The connected host is an slave, try to connect to {1}',
                XenFailure.ex_sr_error: 'Error on SR: {2}',
                XenFailure.ex_handle_invalid: 'Invalid reference to {1}',
            }
            err = error_list.get(typing.cast(typing.Any, self.details[0]), 'Error {0}')

            return err.format(*typing.cast(list[typing.Any], self.details))
        except Exception:
            return 'Unknown exception: {}'.format(typing.cast(typing.Any, self.details))

    def __str__(self) -> str:
        return self.as_human_readable()


class XenException(XenFault):
    def __init__(self, message: typing.Any):
        XenFault.__init__(self, message)
        logger.debug('Exception create: %s', message)


class XenNotFoundError(XenException, exceptions.services.generics.NotFoundError):
    def __init__(self, message: typing.Any):
        XenException.__init__(self, message)
        logger.debug('Not found exception create: %s', message)


class XenFatalError(XenException, exceptions.services.generics.FatalError):
    def __init__(self, message: typing.Any):
        XenException.__init__(self, message)
        logger.debug('Fatal exception create: %s', message)


class XenRetryableError(XenException, exceptions.services.generics.RetryableError):
    def __init__(self, message: typing.Any):
        XenException.__init__(self, message)
        logger.debug('Retryable exception create: %s', message)


@contextlib.contextmanager
def translator() -> typing.Generator[None, None, None]:
    try:
        yield
    except XenException:
        raise  # No need to translate
    except XenAPI.Failure as e:
        if e.details[0] == 'HANDLE_INVALID':
            raise XenNotFoundError(e.details[1:]) from e
        raise XenFailure(typing.cast(typing.Any, e.details)) from e
    except TimeoutError:  # Retryable error
        raise XenRetryableError('Timeout error') from None
    except Exception as e:
        raise XenException(str(e)) from e


T = typing.TypeVar('T')
P = typing.ParamSpec('P')


# decorator for translator
def catched(f: collections.abc.Callable[P, T]) -> collections.abc.Callable[P, T]:

    @functools.wraps(f)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        with translator():
            return f(*args, **kwargs)

    return wrapper
