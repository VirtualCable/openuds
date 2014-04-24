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
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
'''

from __future__ import unicode_literals

__updated__ = '2014-04-24'

from django.db import models
from django.db.models import signals

from uds.core.util.State import State
from uds.core.Environment import Environment
from uds.core.jobs.JobsFactory import JobsFactory

from uds.models.Util import NEVER

import logging

logger = logging.getLogger(__name__)


class Scheduler(models.Model):
    '''
    Class that contains scheduled tasks.

    The scheduled task are keep at database so:
    * We can access them from any host
    * We have a persistence for them

    The Scheduler contains jobs, that are clases that manages the job.
    Jobs are not serialized/deserialized, they are just Task delegated to certain clases.

    In order for a task to work, it must first register itself for "names" that that class handles using the
    JobsFactory
    '''

    DAY = 60 * 60 * 24
    HOUR = 60 * 60
    MIN = 60

    name = models.CharField(max_length=64, unique=True)
    frecuency = models.PositiveIntegerField(default=DAY)
    last_execution = models.DateTimeField(auto_now_add=True)
    next_execution = models.DateTimeField(default=NEVER, db_index=True)
    owner_server = models.CharField(max_length=64, db_index=True, default='')
    state = models.CharField(max_length=1, default=State.FOR_EXECUTE, db_index=True)

    class Meta:
        '''
        Meta class to declare default order and unique multiple field index
        '''
        app_label = 'uds'


    def getEnvironment(self):
        '''
        Returns an environment valid for the record this object represents
        '''
        return Environment.getEnvForTableElement(self._meta.verbose_name, self.id)

    def getInstance(self):
        '''
        Returns an instance of the class that this record of the Scheduler represents. This clas is derived
        of uds.core.jobs.Job.Job
        '''
        jobInstance = JobsFactory.factory().lookup(self.name)
        if jobInstance != None:
            env = self.getEnvironment()
            return jobInstance(env)
        else:
            return None

    @staticmethod
    def beforeDelete(sender, **kwargs):
        '''
        Used to remove environment for sheduled task
        '''
        toDelete = kwargs['instance']
        logger.debug('Deleting sheduled task {0}'.format(toDelete))
        toDelete.getEnvironment().clearRelatedData()

    def __unicode__(self):
        return u"Scheduled task {0}, every {1}, last execution at {2}, state = {3}".format(self.name, self.frecuency, self.last_execution, self.state)

# Connects a pre deletion signal to Scheduler
signals.pre_delete.connect(Scheduler.beforeDelete, sender=Scheduler)
