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
import datetime

MAX_FATAL_ERROR_RETRIES: typing.Final[int] = 16
MAX_RETRAYABLE_ERROR_RETRIES: typing.Final[int] = 8192  # Max retries before giving up at most 72 hours
# Retries to stop again or to shutdown again in STOPPING_GROUP or DELETING_GROUP
RETRIES_TO_RETRY: typing.Final[int] = 32
MAX_DELETIONS_AT_ONCE: typing.Final[int] = 32

# For every operation that takes more than this time, multiplay CHECK_INTERVAL by (time / TIME_THRESHOLD)
OPERATION_DELAY_THRESHOLD: typing.Final[int] = 2
MAX_DELAY_RATE: typing.Final[float] = 4.0

# This interval is how long will take to check again for deletion, stopping, etc...
# That is, once a machine is deleted, every CHECK_INTERVAL seconds will be check that it has been deleted
CHECK_INTERVAL: typing.Final[datetime.timedelta] = datetime.timedelta(seconds=11)  # Check interval
FATAL_ERROR_INTERVAL_MULTIPLIER: typing.Final[int] = 2  # Multiplier for fatal errors

# TO_STOP_GROUP: typing.Final[str] = 'to_stop'
# STOPPING_GROUP: typing.Final[str] = 'stopping'
# TO_DELETE_GROUP: typing.Final[str] = 'to_delete'
# DELETING_GROUP: typing.Final[str] = 'deleting'

