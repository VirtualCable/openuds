# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2019 Virtual Cable S.L.
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
import datetime
import logging
import typing

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from .Job import Job


class JobsFactory:
    _factory: typing.Optional['JobsFactory'] = None
    _jobs: typing.Dict[str, typing.Type['Job']]

    def __init__(self):
        self._jobs = {}

    @staticmethod
    def factory() -> 'JobsFactory':
        if not JobsFactory._factory:
            JobsFactory._factory = JobsFactory()
        return JobsFactory._factory

    def jobs(self) -> typing.Dict[str, typing.Type['Job']]:
        return self._jobs

    def insert(self, name, type_):
        logger.debug('Inserting job %s of type_ %s', name, type_)
        try:
            self._jobs[name] = type_
        except Exception as e:
            logger.debug('Exception at insert in JobsFactory: %s, %s', e.__class__, e)

    def ensureJobsInDatabase(self) -> None:
        from uds.models import Scheduler, getSqlDatetime
        from uds.core.util.State import State
        from uds.core import workers

        try:
            logger.debug('Ensuring that jobs are registered inside database')
            workers.initialize()
            for name, type_ in self._jobs.items():
                try:
                    type_.setup()
                    # We use database server datetime
                    now = getSqlDatetime()
                    next_ = now
                    job = Scheduler.objects.create(name=name, frecuency=type_.frecuency, last_execution=now, next_execution=next_, state=State.FOR_EXECUTE)
                except Exception:  # already exists
                    logger.debug('Already added %s', name)
                    job = Scheduler.objects.get(name=name)
                    job.frecuency = type_.frecuency
                    if job.next_execution > job.last_execution + datetime.timedelta(seconds=type_.frecuency):
                        job.next_execution = job.last_execution + datetime.timedelta(seconds=type_.frecuency)
                    job.save()
        except Exception as e:
            logger.debug('Exception at ensureJobsInDatabase in JobsFactory: %s, %s', e.__class__, e)

    def lookup(self, typeName: str) -> typing.Optional[typing.Type['Job']]:
        try:
            return self._jobs[typeName]
        except KeyError:
            return None
