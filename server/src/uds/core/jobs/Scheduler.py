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

'''
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''
from __future__ import unicode_literals

from django.db.models import Q
from django.db import transaction, DatabaseError
from uds.models import Scheduler as dbScheduler, getSqlDatetime
from uds.core.util.State import State
from uds.core.jobs.JobsFactory import JobsFactory
from datetime import timedelta
from socket import gethostname
import threading
import time
import logging

__updated__ = '2014-04-23'

logger = logging.getLogger(__name__)


class JobThread(threading.Thread):
    def __init__(self, jobInstance, dbJob):
        super(JobThread, self).__init__()
        self._jobInstance = jobInstance
        self._dbJobId = dbJob.id

    def run(self):
        try:
            self._jobInstance.execute()
        except Exception:
            logger.debug("Exception executing job {0}".format(self._dbJobId))
        self.jobDone()

    def jobDone(self):
        done = False
        while done is False:
            try:
                self.__updateDb()
                done = True
            except:
                # Databases locked, maybe because we are on a multitask environment, let's try again in a while
                logger.info('Database access locked... Retrying')
                time.sleep(1)

    @transaction.atomic
    def __updateDb(self):
        job = dbScheduler.objects.select_for_update().get(id=self._dbJobId)
        job.state = State.FOR_EXECUTE
        job.owner_server = ''
        job.next_execution = getSqlDatetime() + timedelta(seconds=job.frecuency)
        # Update state and last execution time at database
        job.save()


class Scheduler(object):
    granularity = 2  # We check for cron jobs every THIS seconds

    # to keep singleton Scheduler
    _scheduler = None

    def __init__(self):
        self._hostname = gethostname()
        self._keepRunning = True

    @staticmethod
    def scheduler():
        if Scheduler._scheduler == None:
            Scheduler._scheduler = Scheduler()
        return Scheduler._scheduler

    def notifyTermination(self):
        self._keepRunning = False

    def executeOneJob(self):
        '''
        Looks for a job and executes it
        '''
        jobInstance = None
        try:
            now = getSqlDatetime()  # Datetimes are based on database server times
            fltr = Q(state=State.FOR_EXECUTE) & (Q(last_execution__gt=now) | Q(next_execution__lt=now))
            with transaction.atomic():
                # If next execution is before now or last execution is in the future (clock changed on this server, we take that task as executable)
                # This params are all set inside fltr (look at __init__)
                job = dbScheduler.objects.select_for_update().filter(fltr).order_by('next_execution')[0]
                job.state = State.RUNNING
                job.owner_server = self._hostname
                job.last_execution = now
                job.save()

            jobInstance = job.getInstance()

            if jobInstance == None:
                logger.error('Job instance can\'t be resolved for {0}, removing it'.format(job))
                job.delete()
                return
            logger.debug('Executing job:>{0}<'.format(job.name))
            JobThread(jobInstance, job).start()  # Do not instatiate thread, just run it
        except IndexError:
            # Do nothing, there is no jobs for execution
            return
        except DatabaseError:
            # Whis will happen whenever a connection error or a deadlock error happens
            # This in fact means that we have to retry operation, and retry will happen on main loop
            # Look at this http://dev.mysql.com/doc/refman/5.0/en/innodb-deadlocks.html
            # I have got some deadlock errors, but looking at that url, i found that it is not so abnormal
            logger.debug('Deadlock, no problem at all :-) (sounds hards, but really, no problem, will retry later :-) )')

    @transaction.atomic
    def releaseOwnShedules(self):
        '''
        Releases all scheduleds being executed by this scheduler
        '''
        dbScheduler.objects.select_for_update().filter(owner_server=self._hostname).update(owner_server='', state=State.FOR_EXECUTE)

    def run(self):
        # We ensure that the jobs are also in database so we can
        logger.debug('Run Scheduler thread')
        JobsFactory.factory().ensureJobsInDatabase()
        self.releaseOwnShedules()
        logger.debug("At loop")
        while self._keepRunning:
            try:
                time.sleep(self.granularity)
                self.executeOneJob()
            except Exception, e:
                logger.exception('Unexpected exception at run loop {0}: {1}'.format(e.__class__, e))
