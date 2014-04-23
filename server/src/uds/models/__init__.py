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

from django.db import models
from django.db import IntegrityError
from django.db.models import signals
from uds.core.jobs.JobsFactory import JobsFactory
from uds.core.Environment import Environment
from uds.core.db.LockingManager import LockingManager
from uds.core.util.State import State
from uds.core.util import log
from uds.core.util import net
from uds.core.services.Exceptions import InvalidServiceException
from datetime import datetime, timedelta
from time import mktime

import logging

logger = logging.getLogger(__name__)

__updated__ = '2014-04-23'


# Utility
from uds.models.Util import getSqlDatetime
from uds.models.Util import optimizeTable
from uds.models.Util import NEVER
from uds.models.Util import NEVER_UNIX

# Services
from uds.models.Provider import Provider
from uds.models.Service import Service

# Os managers
from uds.models.OSManager import OSManager

# Transports
from uds.models.Transport import Transport
from uds.models.Network import Network


# Authenticators
from uds.models.Authenticator import Authenticator
from uds.models.User import User
from uds.models.UserPreference import UserPreference
from uds.models.Group import Group


# Provisioned services
from uds.models.ServicesPool import DeployedService
from uds.models.ServicesPoolPublication import DeployedServicePublication
from uds.models.UserService import UserService

# Especific log information for an user service
from uds.models.Log import Log

# Stats
from uds.models.StatsCounters import StatsCounters
from uds.models.StatsEvents import StatsEvents


# General utility models, such as a database cache (for caching remote content of slow connections to external services providers for example)
# We could use django cache (and maybe we do it in a near future), but we need to clean up things when objecs owning them are deleted
class Cache(models.Model):
    '''
    General caching model. This model is managed via uds.core.util.Cache.Cache class
    '''
    owner = models.CharField(max_length=128, db_index=True)
    key = models.CharField(max_length=64, primary_key=True)
    value = models.TextField(default='')
    created = models.DateTimeField()  # Date creation or validation of this entry. Set at write time
    validity = models.IntegerField(default=60)  # Validity of this entry, in seconds

    class Meta:
        '''
        Meta class to declare the name of the table at database
        '''
        db_table = 'uds_utility_cache'

    @staticmethod
    def cleanUp():
        '''
        Purges the cache items that are no longer vaild.
        '''
        from django.db import connection, transaction
        con = connection
        cursor = con.cursor()
        logger.info("Purging cache items")
        cursor.execute('DELETE FROM uds_utility_cache WHERE created + validity < now()')
        transaction.commit_unless_managed()

    def __unicode__(self):
        expired = datetime.now() > self.created + timedelta(seconds=self.validity)
        if expired:
            expired = "Expired"
        else:
            expired = "Active"
        return u"{0} {1} = {2} ({3})".format(self.owner, self.key, self.value, expired)


class Config(models.Model):
    '''
    General configuration values model. Used to store global and specific modules configuration values.
    This model is managed via uds.core.util.Config.Config class
    '''
    section = models.CharField(max_length=128, db_index=True)
    key = models.CharField(max_length=64, db_index=True)
    value = models.TextField(default='')
    crypt = models.BooleanField(default=False)
    long = models.BooleanField(default=False)

    class Meta:
        '''
        Meta class to declare default order and unique multiple field index
        '''
        db_table = 'uds_configuration'
        unique_together = (('section', 'key'),)

    def __unicode__(self):
        return u"Config {0} = {1}".format(self.key, self.value)


class Storage(models.Model):
    '''
    General storage model. Used to store specific instances (transport, service, servicemanager, ...) persinstent information
    not intended to be serialized/deserialized everytime one object instance is loaded/saved.
    '''
    owner = models.CharField(max_length=128, db_index=True)
    key = models.CharField(max_length=64, primary_key=True)
    data = models.TextField(default='')
    attr1 = models.CharField(max_length=64, db_index=True, null=True, blank=True, default=None)

    objects = LockingManager()

    def __unicode__(self):
        return u"{0} {1} = {2}, {3}".format(self.owner, self.key, self.data, str.join('/', [self.attr1]))


class UniqueId(models.Model):
    '''
    Unique ID Database. Used to store unique names, unique macs, etc...
    Managed via uds.core.util.UniqueIDGenerator.UniqueIDGenerator
    '''
    owner = models.CharField(max_length=128, db_index=True, default='')
    basename = models.CharField(max_length=32, db_index=True)
    seq = models.BigIntegerField(db_index=True)
    assigned = models.BooleanField(db_index=True, default=True)
    stamp = models.IntegerField(db_index=True, default=0)

    objects = LockingManager()

    class Meta:
        '''
        Meta class to declare default order and unique multiple field index
        '''
        unique_together = (('basename', 'seq'),)
        ordering = ('-seq',)

    def __unicode__(self):
        return u"{0} {1}.{2}, assigned is {3}".format(self.owner, self.basename, self.seq, self.assigned)


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

    # objects = LockingManager()

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


class DelayedTask(models.Model):
    '''
    A delayed task is a kind of scheduled task. It's a task that has more than is executed at a delay
    specified at record. This is, for example, for publications, service preparations, etc...

    The delayed task is different from scheduler in the fact that they are "one shot", meaning this that when the
    specified delay is reached, the task is executed and the record is removed from the table.

    This table contains uds.core.util.jobs.DelayedTask references
    '''
    type = models.CharField(max_length=128)
    tag = models.CharField(max_length=64, db_index=True)  # A tag for letting us locate delayed publications...
    instance = models.TextField()
    insert_date = models.DateTimeField(auto_now_add=True)
    execution_delay = models.PositiveIntegerField()
    execution_time = models.DateTimeField(db_index=True)

    # objects = LockingManager()

    def __unicode__(self):
        return u"Run Queue task {0} owned by {3},inserted at {1} and with {2} seconds delay".format(self.type, self.insert_date, self.execution_delay, self.execution_time)

