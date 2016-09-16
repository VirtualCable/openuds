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

# pylint: disable=model-missing-unicode, too-many-public-methods

from __future__ import unicode_literals

from django.db import models
from django.db.models import signals
from django.utils.encoding import python_2_unicode_compatible

from uds.core.Environment import Environment
from uds.core.util import log
from uds.core.util import unique
from uds.core.util.State import State
from uds.models.UUIDModel import UUIDModel

from uds.models.ServicesPool import DeployedService
from uds.models.ServicesPoolPublication import DeployedServicePublication

from uds.models.User import User

from uds.models.Util import NEVER
from uds.models.Util import getSqlDatetime

import six
import pickle
import logging

__updated__ = '2016-09-16'


logger = logging.getLogger(__name__)


@python_2_unicode_compatible
class UserService(UUIDModel):
    '''
    This is the base model for assigned user service and cached user services.
    This are the real assigned services to users. DeployedService is the container (the group) of this elements.
    '''

    # The reference to deployed service is used to accelerate the queries for different methods, in fact its redundant cause we can access to the deployed service
    # through publication, but queries are much more simple
    deployed_service = models.ForeignKey(DeployedService, on_delete=models.CASCADE, related_name='userServices')
    publication = models.ForeignKey(DeployedServicePublication, on_delete=models.CASCADE, null=True, blank=True, related_name='userServices')

    unique_id = models.CharField(max_length=128, default='', db_index=True)  # User by agents to locate machine
    friendly_name = models.CharField(max_length=128, default='')
    # We need to keep separated two differents os states so service operations (move beween caches, recover service) do not affects os manager state
    state = models.CharField(max_length=1, default=State.PREPARING, db_index=True)  # We set index so filters at cache level executes faster
    os_state = models.CharField(max_length=1, default=State.PREPARING)  # The valid values for this field are PREPARE and USABLE
    state_date = models.DateTimeField(auto_now_add=True, db_index=True)
    creation_date = models.DateTimeField(db_index=True)
    data = models.TextField(default='')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='userServices', null=True, blank=True, default=None)
    in_use = models.BooleanField(default=False)
    in_use_date = models.DateTimeField(default=NEVER)
    cache_level = models.PositiveSmallIntegerField(db_index=True, default=0)  # Cache level must be 1 for L1 or 2 for L2, 0 if it is not cached service

    src_hostname = models.CharField(max_length=64, default='')
    src_ip = models.CharField(max_length=15, default='')

    cluster_node = models.CharField(max_length=128, default=None, blank=True, null=True, db_index=True)

    # "Secret" url used to communicate (send message) to services
    # if This is None, communication is not possible
    # The communication is done using POST via REST & Json
    # comms_url = models.CharField(max_length=256, default=None, null=True, blank=True)

    # objects = LockingManager() This model is on an innoDb table, so we do not need the locking manager anymore

    class Meta(UUIDModel.Meta):
        '''
        Meta class to declare default order and unique multiple field index
        '''
        db_table = 'uds__user_service'
        ordering = ('creation_date',)
        app_label = 'uds'
        index_together = (
            'deployed_service',
            'cache_level',
            'state'
        )

    def getEnvironment(self):
        '''
        Returns an environment valid for the record this object represents.

        In the case of the user, there is an instatiation of "generators".
        Right now, there is two generators provided to child instance objects, that are
        valid for generating unique names and unique macs. In a future, there could be more generators

        To access this generators, use the Envirnment class, and the keys 'name' and 'mac'.

        (see related classes uds.core.util.UniqueNameGenerator and uds.core.util.UniqueMacGenerator)
        '''
        return Environment.getEnvForTableElement(
            self._meta.verbose_name,
            self.id,
            {
                'mac': unique.UniqueMacGenerator,
                'name': unique.UniqueNameGenerator,
                'id': unique.UniqueGIDGenerator,
            }
        )

    def getInstance(self):
        '''
        Instantiates the object this record contains. In this case, the instantiated object needs also
        the os manager and the publication, so we also instantiate those here.

        Every single record of UserService model, represents an object.

        Args:
           values (list): Values to pass to constructor. If no values are especified,
                          the object is instantiated empty and them de-serialized from stored data.

        Returns:
            The instance Instance of the class this provider represents

        Raises:
        '''
        # We get the service instance, publication instance and osmanager instance
        ds = self.deployed_service
        serviceInstance = ds.service.getInstance()
        if serviceInstance.needsManager is False:
            osmanagerInstance = None
        else:
            osmanagerInstance = ds.osmanager.getInstance()
        # We get active publication
        publicationInstance = None
        try:  # We may have deleted publication...
            if self.publication is not None:
                publicationInstance = self.publication.getInstance()
        except Exception as e:
            # The publication to witch this item points to, does not exists
            self.publication = None
            logger.error("Got exception at getInstance of an userService {0} : {1}".format(e.__class__, e))
        if serviceInstance.deployedType is None:
            raise Exception('Class {0} needs deployedType but it is not defined!!!'.format(serviceInstance.__class__.__name__))
        us = serviceInstance.deployedType(self.getEnvironment(), service=serviceInstance, publication=publicationInstance, osmanager=osmanagerInstance, dbservice=self)
        if self.data != '' and self.data is not None:
            us.unserialize(self.data)
        return us

    def updateData(self, us):
        '''
        Updates the data field with the serialized :py:class:uds.core.services.UserDeployment

        Args:
            dsp: :py:class:uds.core.services.UserDeployment to serialize

        :note: This method do not saves the updated record, just updates the field
        '''
        self.data = us.serialize()

    def getName(self):
        '''
        Returns the name of the user deployed service
        '''
        if self.friendly_name == '':
            si = self.getInstance()
            self.friendly_name = si.getName()
            self.updateData(si)

        return self.friendly_name

    def getUniqueId(self):
        '''
        Returns the unique id of the user deployed service
        '''
        if self.unique_id == '':
            si = self.getInstance()
            self.unique_id = si.getUniqueId()
            self.updateData(si)
        return self.unique_id

    def storeValue(self, name, value):
        '''
        Stores a value inside custom storage

        Args:
            name: Name of the value to store
            value: Value of the value to store
        '''
        # Store value as a property
        self.setProperty(name, value)

    def recoverValue(self, name):
        '''
        Recovers a value from custom storage

        Args:
            name: Name of values to recover

        Returns:
            Stored value, None if no value was stored
        '''
        val = self.getProperty(name)

        # To transition between old stor at storage table and new properties table
        # If value is found on property, use it, else, try to recover it from storage
        if val is None:
            val = self.getEnvironment().storage.get(name)
        return val

    def setConnectionSource(self, ip, hostname=''):
        '''
        Notifies that the last access to this service was initiated from provided params

        Args:
            ip: Ip from where the connection was initiated
            hostname: Hostname from where the connection was initiated

        Returns:
            Nothing
        '''
        self.src_ip = ip
        self.src_hostname = hostname
        self.save()

    def getConnectionSource(self):
        '''
        Returns stored connection source data (ip & hostname)

        Returns:
            An array of two elements, first is the ip & second is the hostname

        :note: If the transport did not notified this data, this may be "empty"
        '''
        return [self.src_ip, self.src_hostname]

    def getOsManager(self):
        return self.deployed_service.osmanager

    def needsOsManager(self):
        '''
        Returns True if this User Service needs an os manager (i.e. parent services pools is marked to use an os manager)
        '''
        return self.getOsManager() is not None

    def transformsUserOrPasswordForService(self):
        '''
        If the os manager changes the username or the password, this will return True
        '''
        return self.deployed_service.transformsUserOrPasswordForService()

    def processUserPassword(self, username, password):
        '''
        Before accessing a service by a transport, we can request
        the service to "transform" the username & password that the transport
        will use to connect to that service.

        This method is here so transport USE it before using the username/password
        provided by user or by own transport configuration.

        Args:
            username: the username that will be used to connect to service
            password: the password that will be used to connect to service

        Return:
            An array of two elements, first is transformed username, second is
            transformed password.

        :note: This method MUST be invoked by transport before using credentials passed to getHtml.
        '''
        ds = self.deployed_service
        serviceInstance = ds.service.getInstance()
        if serviceInstance.needsManager is False:
            return [username, password]

        return ds.osmanager.getInstance().processUserPassword(self, username, password)

    def setState(self, state):
        '''
        Updates the state of this object and, optionally, saves it

        Args:
            state: new State to store at record

            save: Defaults to true. If false, record will not be saved to db, just modified

        '''
        if state != self.state:
            self.state_date = getSqlDatetime()
            self.state = state

    def setOsState(self, state):
        '''
        Updates the os state (state of the os) of this object and, optionally, saves it

        Args:
            state: new State to store at record

            save: Defaults to true. If false, record will not be saved to db, just modified

        '''
        if state != self.os_state:
            self.state_date = getSqlDatetime()
            self.os_state = state

    def assignToUser(self, user):
        '''
        Assigns this user deployed service to an user.

        Args:
            user: User to assing to (db record)
        '''
        self.cache_level = 0
        self.state_date = getSqlDatetime()
        self.user = user

    def setInUse(self, state):
        '''
        Set the "in_use" flag for this user deployed service

        Args:
            state: State to set to the "in_use" flag of this record

        :note: If the state is Fase (set to not in use), a check for removal of this deployed service is launched.
        '''
        from uds.core.managers.UserServiceManager import UserServiceManager
        self.in_use = state
        self.in_use_date = getSqlDatetime()

        # Start/stop accouting
        if state is True:
            self.startUsageAccounting()
        else:
            self.stopUsageAccounting()

        if state is False:  # Service released, check y we should mark it for removal
            # If our publication is not current, mark this for removal
            UserServiceManager.manager().checkForRemoval(self)

    def startUsageAccounting(self):
        # 1.- If do not have any accounter associated, do nothing
        # 2.- If called but already accounting, do nothing
        # 3.- If called and not accounting, start accounting
        if self.deployed_service.account is None:
            return

        try:
            accountStart = self.getProperty('usageAccountStart', None)
            if accountStart is None:
                self.setProperty('usageAccountStart', pickle.dumps(getSqlDatetime()))
        except Exception:  # Invalid values, etc...
            pass

    def stopUsageAccounting(self):
        # 1.- If do not have any accounter associated, do nothing
        # 2.- If called but not accounting, do nothing
        # 3.- If called and accounting, stop accounting
        if self.deployed_service.account is None:
            return

        try:
            accountStart = self.getProperty('usageAccountStart', None)
            if accountStart is not None:
                self.deployed_service.saveAccounting(self, pickle.loads(accountStart), getSqlDatetime())
        except Exception:  # Invalid values, etc...
            pass

    def isUsable(self):
        '''
        Returns if this service is usable
        '''
        return State.isUsable(self.state)

    def isPreparing(self):
        '''
        Returns if this service is in preparation (not ready to use, but in its way to be so...)
        '''
        return State.isPreparing(self.state)

    def isReady(self):
        '''
        Returns if this service is ready (not preparing or marked for removal)
        '''
        # Call to isReady of the instance
        from uds.core.managers.UserServiceManager import UserServiceManager
        return UserServiceManager.manager().isReady(self)

    def isInMaintenance(self):
        return self.deployed_service.isInMaintenance()

    def remove(self):
        '''
        Mark this user deployed service for removal
        '''
        self.setState(State.REMOVABLE)
        self.save()

    def release(self):
        '''
        A much more convenient method that "remove"
        '''
        self.remove()

    def cancel(self):
        '''
        Asks the UserServiceManager to cancel the current operation of this user deployed service.
        '''
        from uds.core.managers.UserServiceManager import UserServiceManager
        UserServiceManager.manager().cancel(self)

    def removeOrCancel(self):
        '''
        Marks for removal or cancels it, depending on state
        '''
        if self.isUsable():
            self.remove()
        else:
            self.cancel()

    def moveToLevel(self, cacheLevel):
        '''
        Moves cache items betwen levels, managed directly

        Args:
            cacheLevel: New cache level to put object in
        '''
        from uds.core.managers.UserServiceManager import UserServiceManager
        UserServiceManager.manager().moveToLevel(self, cacheLevel)

    @staticmethod
    def getUserAssignedServices(user):
        '''
        Return DeployedUserServices (not deployed services) that this user owns and are assignable
        For this to happen, we locate all user services assigned to this user, and we keep those that:
        * Must assign service manually
        This method is probably slow, but i don't think a user will have more than a bunch of services assigned
        @returns and array of dicts with id, name and transports
        '''
        logger.debug("Filtering assigned services for user {0}".format(user))
        res = []
        for us in UserService.objects.filter(user=user):
            if us.deployed_service.state != State.ACTIVE:  # Do not show removing or removed services
                continue
            usi = us.getInstance()
            if usi.service().mustAssignManually is False:
                continue
            res.append({'id': us.id, 'name': usi.getName(), 'transports': us.deployed_service.transports, 'service': us})
        return res

    def getProperty(self, propName, default=None):
        try:
            val = self.properties.get(name=propName).value
            return val if val is not '' else default  # Empty string is null
        except Exception:
            return default

    def getProperties(self):
        '''
        Retrieves all properties as a dictionary
        The number of properties per item is expected to be "relatively small" (no more than 5 items?)
        '''
        dct = {}
        for v in self.properties.all():
            dct[v.name] = v.value
        return dct

    def setProperty(self, propName, propValue):
        prop, _ = self.properties.get_or_create(name=propName)
        prop.value = propValue if propValue is not None else ''
        prop.save()

    def setCommsUrl(self, commsUrl=None):
        self.setProperty('comms_url', commsUrl)

    def getCommsUrl(self):
        return self.getProperty('comms_url', None)

    def logIP(self, ip=None):
        self.setProperty('ip', ip)

    def getLoggedIP(self):
        return self.getProperty('ip', '0.0.0.0')

    def isValidPublication(self):
        '''
        Returns True if this user service does not needs an publication, or if this deployed service publication is the current one
        '''
        return self.deployed_service.service.getType().publicationType is None or self.publication == self.deployed_service.activePublication()

    def __str__(self):
        return "User service {0}, cache_level {1}, user {2}, name {3}, state {4}:{5}".format(self.id, self.cache_level, self.user, self.friendly_name,
                                                                                             State.toString(self.state), State.toString(self.os_state))

    @staticmethod
    def beforeDelete(sender, **kwargs):
        '''
        Used to invoke the Service class "Destroy" before deleting it from database.

        The main purpuse of this hook is to call the "destroy" method of the object to delete and
        to clear related data of the object (environment data such as own storage, cache, etc...

        :note: If destroy raises an exception, the deletion is not taken.
        '''
        toDelete = kwargs['instance']
        toDelete.getEnvironment().clearRelatedData()

        # Clear related logs to this user service
        log.clearLogs(toDelete)

        logger.debug('Deleted user service {0}'.format(toDelete))

# Connects a pre deletion signal to Authenticator
signals.pre_delete.connect(UserService.beforeDelete, sender=UserService)
