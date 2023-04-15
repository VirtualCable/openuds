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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import typing
import platform
import threading
import time
import logging
from datetime import timedelta

from django.db import transaction, DatabaseError, connections
from django.db.models import Q

from uds.models import Scheduler as DBScheduler, getSqlDatetime
from uds.core.util.state import State
from .jobs_factory import JobsFactory

logger = logging.getLogger(__name__)

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from .job import Job


class JobThread(threading.Thread):
    """
    Class responsible of executing one job.
    This class:
      Ensures that the job is executed in a controlled way (any exception will be catch & processed)
      Ensures that the scheduler db entry is released after run
    """

    _jobInstance: 'Job'
    _dbJobId: int
    _freq: int

    def __init__(self, jobInstance: 'Job', dbJob: DBScheduler) -> None:
        super(JobThread, self).__init__()
        self._jobInstance = jobInstance
        self._dbJobId = dbJob.id
        self._freq = dbJob.frecuency

    def run(self) -> None:
        try:
            self._jobInstance.execute()
        except Exception:
            logger.warning("Exception executing job %s", self._dbJobId)
        finally:
            self.jobDone()

    def jobDone(self) -> None:
        """
        Invoked whenever a job is is finished (with or without exception)
        """
        done = False
        while done is False:
            try:
                self.__updateDb()
                done = True
            except Exception:
                # Databases locked, maybe because we are on a multitask environment, let's try again in a while
                try:
                    connections['default'].close()
                except Exception as e:
                    logger.error('On job executor, closing db connection: %s', e)
                # logger.info('Database access failed... Retrying')
                time.sleep(1)

        # Ensures DB connection is released after job is done
        connections['default'].close()

    def __updateDb(self) -> None:
        """
        Atomically updates the scheduler db to "release" this job
        """
        with transaction.atomic():
            DBScheduler.objects.select_for_update().filter(id=self._dbJobId).update(
                state=State.FOR_EXECUTE,
                owner_server='',
                next_execution=getSqlDatetime() + timedelta(seconds=self._freq),
            )


class Scheduler:
    """
    Class responsible of maintain/execute scheduled jobs
    """

    granularity = 2  # We check for cron jobs every THIS seconds

    # to keep singleton Scheduler
    _scheduler: typing.Optional['Scheduler'] = None

    def __init__(self) -> None:
        self._hostname = platform.node()
        self._keepRunning = True
        logger.info('Initialized scheduler for host "%s"', self._hostname)

    @staticmethod
    def scheduler() -> 'Scheduler':
        """
        Returns a singleton to the Scheduler
        """
        if Scheduler._scheduler is None:
            Scheduler._scheduler = Scheduler()
        return Scheduler._scheduler

    def notifyTermination(self) -> None:
        """
        Invoked to signal that termination of scheduler task(s) is requested
        """
        self._keepRunning = False

    def executeOneJob(self) -> None:
        """
        Looks for the best waiting job and executes it
        """
        jobInstance = None
        try:
            now = getSqlDatetime()  # Datetimes are based on database server times
            fltr = Q(state=State.FOR_EXECUTE) & (
                Q(last_execution__gt=now) | Q(next_execution__lt=now)
            )
            with transaction.atomic():
                # If next execution is before now or last execution is in the future (clock changed on this server, we take that task as executable)
                # This params are all set inside fltr (look at __init__)
                job: DBScheduler = (
                    DBScheduler.objects.select_for_update()
                    .filter(fltr)
                    .order_by('next_execution')[0]# type: ignore  # Slicing is not supported by pylance right now
                )
                if job.last_execution > now:
                    logger.warning(
                        'EXecuted %s due to last_execution being in the future!',
                        job.name,
                    )
                job.state = State.RUNNING
                job.owner_server = self._hostname
                job.last_execution = now
                job.save(update_fields=['state', 'owner_server', 'last_execution'])

            jobInstance = job.getInstance()

            if jobInstance is None:
                logger.error('Job instance can\'t be resolved for %s, removing it', job)
                job.delete()
                return
            logger.debug('Executing job:>%s<', job.name)
            JobThread(jobInstance, job).start()  # Do not instatiate thread, just run it
        except IndexError:
            # Do nothing, there is no jobs for execution
            return
        except DatabaseError as e:
            # Whis will happen whenever a connection error or a deadlock error happens
            # This in fact means that we have to retry operation, and retry will happen on main loop
            # Look at this http://dev.mysql.com/doc/refman/5.0/en/innodb-deadlocks.html
            # I have got some deadlock errors, but looking at that url, i found that it is not so abnormal
            # logger.debug('Deadlock, no problem at all :-) (sounds hards, but really, no problem, will retry later :-) )')
            raise DatabaseError(
                f'Database access problems. Retrying connection ({e})'
            ) from e

    @staticmethod
    def releaseOwnShedules() -> None:
        """
        Releases all scheduleds being executed by this server
        """
        logger.debug('Releasing all owned scheduled tasks')
        with transaction.atomic():
            DBScheduler.objects.select_for_update().filter(
                owner_server=platform.node()
            ).update(
                owner_server=''
            )  # @UndefinedVariable
            DBScheduler.objects.select_for_update().filter(
                last_execution__lt=getSqlDatetime() - timedelta(minutes=15),
                state=State.RUNNING,
            ).update(
                owner_server='', state=State.FOR_EXECUTE
            )  # @UndefinedVariable
            DBScheduler.objects.select_for_update().filter(owner_server='').update(
                state=State.FOR_EXECUTE
            )  # @UndefinedVariable

    def run(self) -> None:
        """
        Loop that executes scheduled tasks
        Can be executed more than once, in differents threads
        """
        # We ensure that the jobs are also in database so we can
        logger.debug('Run Scheduler thread')
        JobsFactory().ensureJobsInDatabase()
        logger.debug("At loop")
        while self._keepRunning:
            try:
                time.sleep(self.granularity)
                self.executeOneJob()
            except Exception as e:
                # This can happen often on sqlite, and this is not problem at all as we recover it.
                # The log is removed so we do not get increased workers.log file size with no information at all
                if not isinstance(e, DatabaseError):
                    logger.error(
                        'Unexpected exception at run loop %s: %s', e.__class__, e
                    )
                try:
                    connections['default'].close()
                except Exception:
                    logger.exception('Exception clossing connection at delayed task')
        logger.info('Exiting Scheduler because stop has been requested')
        self.releaseOwnShedules()
