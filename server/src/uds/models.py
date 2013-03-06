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
from django.db.models import signals
from uds.core.jobs.JobsFactory import JobsFactory
from uds.core.Environment import Environment
from uds.core.db.LockingManager import LockingManager
from uds.core.util.State import State
from uds.core.util import log
from uds.core.services.Exceptions import InvalidServiceException
from datetime import datetime, timedelta
from time import mktime

import logging

logger = logging.getLogger(__name__)

NEVER = datetime(1972, 7, 1)
NEVER_UNIX = int(mktime(NEVER.timetuple())) 


def getSqlDatetime(unix=False):
    '''
    Returns the current date/time of the database server.
    
    We use this time as method of keeping all operations betwen different servers in sync.
    
    We support get database datetime for:
      * mysql
      * sqlite
    '''
    from django.db import connection
    cursor = connection.cursor()
    
    if connection.vendor == 'mysql':
        cursor.execute('SELECT NOW()')
        date = cursor.fetchone()[0]
    else:
        date = datetime.now() # If not know how to get database datetime, returns local datetime (this is fine for sqlite, which is local)
    
    if unix:
        return int(mktime(date.timetuple()))
    else:
        return date
    
def optimizeTable(dbTable):
    from django.db import connection
    cursor = connection.cursor()
    
    if connection.vendor == 'mysql':
        cursor.execute('OPTIMIZE TABLE {0}'.format(dbTable))

# Services
class Provider(models.Model):
    '''
    A Provider represents the Service provider itself, (i.e. a KVM Server or a Terminal Server)
    '''
    name = models.CharField(max_length=128, unique = True)
    data_type = models.CharField(max_length=128)
    data = models.TextField(default='')
    comments = models.CharField(max_length = 256)

    class Meta:
        '''
        Meta class to declare default order
        '''
        ordering = ('name',)

    def getEnvironment(self):
        '''
        Returns an environment valid for the record this object represents
        '''
        return Environment.getEnvForTableElement(self._meta.verbose_name, self.id) 

    def getInstance(self, values = None):
        '''
        Instantiates the object this record contains.
        
        Every single record of Provider model, represents an object.
        
        Args:
           values (list): Values to pass to constructor. If no values are especified,
                          the object is instantiated empty and them de-serialized from stored data.
        
        Returns:
            The instance Instance of the class this provider represents
        
        Raises:
        '''
        spType = self.getType() 
        env = self.getEnvironment()
        sp = spType(env, values)
        
        # Only unserializes if this is not initialized via user interface and
        # data contains something
        if values == None and self.data != None and self.data != '':
            sp.unserialize(self.data)
        return sp

    def getType(self):
        from uds.core import services
        '''
        Get the type of the object this record represents.
        
        The type is Python type, it obtains this type from ServiceProviderFactory and associated record field.
        
        Returns:
            The python type for this record object
        '''
        return services.factory().lookup(self.data_type)
    
    def __unicode__(self):
        return u"{0} of type {1} (id:{2})".format(self.name, self.data_type, self.id)
    
    @staticmethod
    def beforeDelete(sender, **kwargs):
        '''
        Used to invoke the Provider class "Destroy" before deleting it from database.
        
        The main purpuse of this hook is to call the "destroy" method of the object to delete and
        to clear related data of the object (environment data such as own storage, cache, etc...
        
        :note: If destroy raises an exception, the deletion is not taken.
        '''
        toDelete = kwargs['instance']
        # Only tries to get instance if data is not empty
        if toDelete.data != '':
            s = toDelete.getInstance()
            s.destroy()
            s.env().clearRelatedData()
            
        # Clears related logs
        log.clearLogs(toDelete)
        
        logger.debug('Before delete service provider '.format(toDelete))
    
#: Connects a pre deletion signal to Provider
signals.pre_delete.connect(Provider.beforeDelete, sender = Provider)
    
class Service(models.Model):
    '''
    A Service represents an specidied type of service offered to final users, with it configuration (i.e. a KVM Base Machine for cloning 
    or a Terminal Server configuration).
    '''
    provider = models.ForeignKey(Provider, related_name='services')
    name = models.CharField(max_length=128, unique = False)
    data_type = models.CharField(max_length=128)
    data = models.TextField(default='')
    comments = models.CharField(max_length = 256)

    class Meta:
        '''
        Meta class to declare default order and unique multiple field index
        '''
        ordering = ('name',)
        unique_together = (("provider", "name"),)
    
    def getEnvironment(self):
        '''
        Returns an environment valid for the record this object represents
        '''
        from uds.core.util.UniqueMacGenerator import UniqueMacGenerator
        from uds.core.util.UniqueNameGenerator import UniqueNameGenerator
        
        return Environment.getEnvForTableElement(self._meta.verbose_name, self.id, {'mac' : UniqueMacGenerator, 'name' : UniqueNameGenerator }) 
    
    def getInstance(self, values = None):
        '''
        Instantiates the object this record contains.
        
        Every single record of Provider model, represents an object.
        
        Args:
           values (list): Values to pass to constructor. If no values are especified,
                          the object is instantiated empty and them de-serialized from stored data.
        
        Returns:
            The instance Instance of the class this provider represents
        
        Raises:
        '''
        prov = self.provider.getInstance()
        sType = prov.getServiceByType(self.data_type)
        env = self.getEnvironment()
        s = sType(env, prov, values)
        # Only unserializes if this is not initialized via user interface and
        # data contains something
        if values == None and self.data != None and self.data != '':
            s.unserialize(self.data)
        return s
    
    def getType(self):
        '''
        Get the type of the object this record represents.
        
        The type is Python type, it obtains this type from ServiceProviderFactory and associated record field.
        
        Returns:
            The python type for this record object
            
        :note: We only need to get info from this, not access specific data (class specific info)
        '''
        return self.provider.getType().getServiceByType(self.data_type)
    
    def __unicode__(self):
        return u"{0} of type {1} (id:{2})".format(self.name, self.data_type, self.id)
    
    @staticmethod
    def beforeDelete(sender, **kwargs):
        '''
        Used to invoke the Service class "Destroy" before deleting it from database.
        
        The main purpuse of this hook is to call the "destroy" method of the object to delete and
        to clear related data of the object (environment data such as own storage, cache, etc...
        
        :note: If destroy raises an exception, the deletion is not taken.
        '''
        toDelete = kwargs['instance']
        # Only tries to get instance if data is not empty
        if toDelete.data != '':
            s = toDelete.getInstance()
            s.destroy()
            s.env().clearRelatedData()
        
        # Clears related logs
        log.clearLogs(toDelete)
        
        logger.debug('Before delete service '.format(toDelete))
    
#: Connects a pre deletion signal to Service
signals.pre_delete.connect(Service.beforeDelete, sender = Service)


class OSManager(models.Model):
    '''
    An OS Manager represents a manager for responding requests for agents inside services.
    '''
    name = models.CharField(max_length=128, unique = True)
    data_type = models.CharField(max_length=128)
    data = models.TextField(default='')
    comments = models.CharField(max_length = 256)

    class Meta:
        '''
        Meta class to declare default order
        '''
        ordering = ('name',)

    def getEnvironment(self):
        '''
        Returns an environment valid for the record this object represents
        '''
        return Environment.getEnvForTableElement(self._meta.verbose_name, self.id) 

    def getInstance(self, values = None):
        '''
        Instantiates the object this record contains.
        
        Every single record of Provider model, represents an object.
        
        Args:
           values (list): Values to pass to constructor. If no values are especified,
                          the object is instantiated empty and them de-serialized from stored data.
        
        Returns:
            The instance Instance of the class this provider represents
        
        Raises:
        '''
        osType = self.getType()
        env = self.getEnvironment()
        os = osType(env, values)
        # Only unserializes if this is not initialized via user interface and
        # data contains something
        if values == None and self.data != None and self.data != '':
            os.unserialize(self.data)
        return os
    
    def getType(self):
        '''
        Get the type of the object this record represents.
        
        The type is Python type, it obtains this type from ServiceProviderFactory and associated record field.
        
        Returns:
            The python type for this record object
            
        :note: We only need to get info from this, not access specific data (class specific info)
        '''
        # We only need to get info from this, not access specific data (class specific info)
        from uds.core import osmanagers
        return osmanagers.factory().lookup(self.data_type)
        
    
    def __unicode__(self):
        return u"{0} of type {1} (id:{2})".format(self.name, self.data_type, self.id)
    
    def remove(self):
        '''
        Removes this OS Manager only if there is no associated deployed service using it.
        
        Returns:
            True if the object has been removed
            
            False if the object can't be removed because it is being used by some DeployedService
        
        Raises:
        '''
        if self.deployedServices.all().count() > 0:
            return False
        self.delete()
        return True
    
    @staticmethod
    def beforeDelete(sender, **kwargs):
        '''
        Used to invoke the Service class "Destroy" before deleting it from database.
        
        The main purpuse of this hook is to call the "destroy" method of the object to delete and
        to clear related data of the object (environment data such as own storage, cache, etc...
        
        :note: If destroy raises an exception, the deletion is not taken.
        '''
        toDelete = kwargs['instance']
        # Only tries to get instance if data is not empty
        if toDelete.data != '':
            s = toDelete.getInstance()
            s.destroy()
            s.env().clearRelatedData()
        
        logger.debug('Before delete os manager '.format(toDelete))
    
#: Connects a pre deletion signal to OS Manager
signals.pre_delete.connect(OSManager.beforeDelete, sender = OSManager)

class Transport(models.Model):
    '''
    A Transport represents a way of connecting the user with the service.
    
    Sample of transports are RDP, Spice, Web file uploader, etc...
    '''
    name = models.CharField(max_length=128, unique = True)
    data_type = models.CharField(max_length=128)
    data = models.TextField(default='')
    comments = models.CharField(max_length = 256)
    priority = models.IntegerField(default=0, db_index=True)
    nets_positive = models.BooleanField(default=False)

    class Meta:
        '''
        Meta class to declare default order
        '''
        ordering = ('name',)

    def getEnvironment(self):
        '''
        Returns an environment valid for the record this object represents
        '''
        return Environment.getEnvForTableElement(self._meta.verbose_name, self.id) 

    def getInstance(self, values = None):
        '''
        Instantiates the object this record contains.
        
        Every single record of Provider model, represents an object.
        
        Args:
           values (list): Values to pass to constructor. If no values are especified,
                          the object is instantiated empty and them de-serialized from stored data.
        
        Returns:
            The instance Instance of the class this provider represents
        
        Raises:
        '''
        tType = self.getType()
        env = self.getEnvironment()
        tr = tType(env, values)
        # Only unserializes if this is not initialized via user interface and
        # data contains something
        if values == None and self.data != None and self.data != '':
            tr.unserialize(self.data)
        return tr

    def getType(self):
        '''
        Get the type of the object this record represents.
        
        The type is Python type, it obtains this type from ServiceProviderFactory and associated record field.
        
        Returns:
            The python type for this record object
            
        :note: We only need to get info from this, not access specific data (class specific info)
        '''
        from uds.core import transports

        return transports.factory().lookup(self.data_type)
    
    def validForIp(self, ip):
        '''
        Checks if this transport is valid for the specified IP.
        
        Args:
           ip: Numeric ip address to check validity for. (xxx.xxx.xxx.xxx).
        
        Returns:
            True if the ip can access this Transport.
            
            False if the ip can't access this Transport.
            
            The ip check is done this way:
            * If The associated network is empty, the result is always True
            * If the associated network is not empty, and nets_positive (field) is True, the result will be True if
            the ip is contained in any subnet associated with this transport.
            * If the associated network is empty, and nets_positive (field) is False, the result will be True if
            the ip is NOT contained in ANY subnet associated with this transport.
        
        Raises:
        
        :note: Ip addresses has been only tested with IPv4 addresses
        '''
        if self.networks.count() == 0:
            return True
        ip = Network.ipToLong(ip)
        if self.nets_positive:
            return self.networks.filter(net_start__lte=ip, net_end__gte=ip).count() > 0
        else:
            return self.networks.filter(net_start__lte=ip, net_end__gte=ip).count() == 0
    
    def __unicode__(self):
        return u"{0} of type {1} (id:{2})".format(self.name, self.data_type, self.id)
    
    @staticmethod
    def beforeDelete(sender, **kwargs):
        '''
        Used to invoke the Service class "Destroy" before deleting it from database.
        
        The main purpuse of this hook is to call the "destroy" method of the object to delete and
        to clear related data of the object (environment data such as own storage, cache, etc...
        
        :note: If destroy raises an exception, the deletion is not taken.
        '''
        toDelete = kwargs['instance']
        
        # Only tries to get instance if data is not empty
        if toDelete.data != '':
            s = toDelete.getInstance()
            s.destroy()
            s.env().clearRelatedData()
        
        logger.debug('Before delete transport '.format(toDelete))
    
#: Connects a pre deletion signal to OS Manager
signals.pre_delete.connect(Transport.beforeDelete, sender = Transport)

# Authenticators
class Authenticator(models.Model):
    '''
    This class represents an Authenticator inside the platform. 
    Sample authenticators are LDAP, Active Directory, SAML, ...
    '''
    name = models.CharField(max_length=128, unique = True)
    data_type = models.CharField(max_length=128)
    data = models.TextField(default='')
    comments = models.TextField(default='')
    priority = models.IntegerField(default=0, db_index = True)
    small_name = models.CharField(max_length=32, default='', db_index = True)

    class Meta:
        '''
        Meta class to declare default order
        '''
        ordering = ('name',)

    def getEnvironment(self):
        '''
        Returns an environment valid for the record this object represents
        '''
        return Environment.getEnvForTableElement(self._meta.verbose_name, self.id) 

    def getInstance(self, values = None):
        '''
        Instantiates the object this record contains.
        
        Every single record of Provider model, represents an object.
        
        Args:
           values (list): Values to pass to constructor. If no values are especified,
                          the object is instantiated empty and them de-serialized from stored data.
        
        Returns:
            The instance Instance of the class this provider represents
        
        Raises:
        '''
        auType = self.getType()
        env = self.getEnvironment()
        auth = auType(self, env, values)
        # Only unserializes if this is not initialized via user interface and
        # data contains something
        if values == None and self.data != None and self.data != '':
            auth.unserialize(self.data)
        return auth

    def getType(self):
        '''
        Get the type of the object this record represents.
        
        The type is Python type, it obtains this type from ServiceProviderFactory and associated record field.
        
        Returns:
            The python type for this record object
            
        :note: We only need to get info from this, not access specific data (class specific info)
        '''
        from uds.core import auths
        return auths.factory().lookup(self.data_type)
    
    def isOfType(self, type_):
        return self.data_type == type_
    
    def getOrCreateUser(self, username, realName = None):
        '''
        Used to get or create a new user at database associated with this authenticator.
        
        This user has all parameter default, that are:
        * 'real_name':realName
        * 'last_access':NEVER
        * 'state':State.ACTIVE
        
        Args:
           username: The username to create and associate with this auhtenticator
           
           realName: If None, it will be the same that username. If otherwise especified, it will be the default real_name (field)
        
        Returns:
            True if the ip can access this Transport.
            
            False if the ip can't access this Transport.
            
            The ip check is done this way:
            * If The associated network is empty, the result is always True
            * If the associated network is not empty, and nets_positive (field) is True, the result will be True if
            the ip is contained in any subnet associated with this transport.
            * If the associated network is empty, and nets_positive (field) is False, the result will be True if
            the ip is NOT contained in ANY subnet associated with this transport.
        
        Raises:
        
        
        '''
        if realName is None:
            realName = username
        user, _  = self.users.get_or_create( name = username, defaults = { 'real_name':realName, 'last_access':NEVER, 'state':State.ACTIVE } )
        if realName != user.real_name:
            user.real_name = realName
            user.save()
            
        return user
    
    def isValidUser(self, username, falseIfNotExists = True):
        '''
        Checks the validity of an user
        
        Args:
            username: Name of the user to check
            
            falseIfNotExists: Defaults to True. It is used so we can return a value defined by caller.
            
            One example of falseIfNotExists using as True is for checking that the user is active or it doesn't exists.
        
        Returns: 
            True if it exists and is active, falseIfNotExists (param) if it doesn't exists 
        
        This is done so we can check non existing or non blocked users (state != Active, or do not exists)
        '''
        try:
            u = self.users.get(name=username)
            return State.isActive(u.state)
        except Exception:
            return falseIfNotExists
    
    def __unicode__(self):
        return u"{0} of type {1} (id:{2})".format(self.name, self.data_type, self.id)
    
    @staticmethod
    def all():
        '''
        Returns all authenticators ordered by priority
        '''
        return Authenticator.objects.all().order_by('priority')
    
    @staticmethod
    def beforeDelete(sender, **kwargs):
        '''
        Used to invoke the Service class "Destroy" before deleting it from database.
        
        The main purpuse of this hook is to call the "destroy" method of the object to delete and
        to clear related data of the object (environment data such as own storage, cache, etc...
        
        :note: If destroy raises an exception, the deletion is not taken.
        '''
        toDelete = kwargs['instance']
        # Only tries to get instance if data is not empty
        if toDelete.data != '':
            s = toDelete.getInstance()
            s.destroy()
            s.env().clearRelatedData()
        
        # Clears related logs
        log.clearLogs(toDelete)
        
        logger.debug('Before delete auth '.format(toDelete))
    
# Connects a pre deletion signal to Authenticator
signals.pre_delete.connect(Authenticator.beforeDelete, sender = Authenticator)

class User(models.Model):
    '''
    This class represents a single user, associated with one authenticator
    '''
    manager = models.ForeignKey(Authenticator, on_delete=models.CASCADE, related_name='users')
    name = models.CharField(max_length = 128, db_index = True)
    real_name = models.CharField(max_length = 128)
    comments = models.CharField(max_length = 256)
    state = models.CharField(max_length = 1, db_index = True)
    password = models.CharField(max_length = 128, default = '') # Only used on "internal" sources
    staff_member = models.BooleanField(default = False) # Staff members can login to admin
    is_admin = models.BooleanField(default = False) # is true, this is a super-admin
    last_access = models.DateTimeField(default=NEVER)
    
    class Meta:
        '''
        Meta class to declare default order and unique multiple field index
        '''
        unique_together = (("manager", "name"),)
        ordering = ('name',)

    def getUsernameForAuth(self):
        '''
        Return the username transformed for authentication.
        This transformation is used for transports only, not for transforming
        anything at login time. Transports that will need the username, will invoke
        this method.
        The manager (an instance of uds.core.auths.Authenticator), can transform the database stored username
        so we can, for example, add @domain in some cases.
        '''
        return self.getManager().getForAuth(self.name)
    
    def getManager(self):
        '''
        Returns the authenticator object that owns this user.
        
        :note: The returned value is an instance of the authenticator class used to manage this user, not a db record.
        '''
        return self.manager.getInstance()
    
    def isStaff(self):
        '''
        Return true if this user is admin or staff member
        '''
        return self.staff_member or self.is_admin 
    
    def prefs(self, modName):
        '''
        Returns the preferences for this user for the provided module name.
        
        Usually preferences will be associated with transports, but can be preferences registered by ANY module.
        
        Args:
            modName: name of the module to get preferences for
            
        
        Returns:
        
            The preferences for the module specified as a dictionary (can be empty if module is not found).
            
            If the module exists, the preferences will always contain something, but may be the values are the default ones.
        
        '''
        from uds.core.managers.UserPrefsManager import UserPrefsManager
        return UserPrefsManager.manager().getPreferencesForUser(modName, self)
    
    def updateLastAccess(self):
        '''
        Updates the last access for this user with the current time of the sql server 
        '''
        self.last_access = getSqlDatetime()
        self.save()
        
    def logout(self):
        '''
        Invoked to log out this user
        '''
        return self.getManager().logout(self.name)
    
    def getGroups(self):
        '''
        returns the groups (and metagroups) this user belongs to
        '''
        grps = list()
        for g in self.groups.filter(is_meta=False):
            grps += (g.id,)
            yield g
        # Locate metagroups
        for g in Group.objects.filter(manager__id=self.manager.id, is_meta=True):
            gn = g.groups.filter(id__in=grps).count() 
            if gn == g.groups.count(): # If a meta group is empty, all users belongs to it. we can use gn != 0 to check that if it is empty, is not valid
                # This group matches
                yield g
    
    def __unicode__(self):
        return u"User {0}(id:{1}) from auth {2}".format(self.name, self.id, self.manager.name)


    @staticmethod
    def beforeDelete(sender, **kwargs):
        '''
        Used to invoke the Service class "Destroy" before deleting it from database.
        
        In this case, this method ensures that the user has no userServices assigned and, if it has,
        mark those services for removal
        
        :note: If destroy raises an exception, the deletion is not taken.
        '''
        toDelete = kwargs['instance']
        
        # first, we invoke removeUser. If this raises an exception, user will not
        # be removed
        toDelete.getManager().removeUser(toDelete.name)
        
        # Remove related logs
        log.clearLogs(toDelete)
        
        # Removes all user services assigned to this user (unassign it and mark for removal)
        for us in toDelete.userServices.all():
            us.assignToUser(None)
            us.remove()
            
        
        logger.debug('Deleted user {0}'.format(toDelete))
        

signals.pre_delete.connect(User.beforeDelete, sender = User)

class Group(models.Model):
    '''
    This class represents a group, associated with one authenticator
    '''
    manager = models.ForeignKey(Authenticator, on_delete=models.CASCADE, related_name='groups')
    name = models.CharField(max_length = 128, db_index = True)
    state = models.CharField(max_length = 1, default = State.ACTIVE, db_index = True)
    comments = models.CharField(max_length = 256, default = '')
    users = models.ManyToManyField(User, related_name='groups')
    is_meta = models.BooleanField(default=False, db_index=True)
    groups = models.ManyToManyField('self', symmetrical=False)

    class Meta:
        '''
        Meta class to declare default order and unique multiple field index
        '''
        unique_together = (("manager", "name"),)
        ordering = ('name',)

    def getManager(self):
        '''
        Returns the authenticator object that owns this user.
        
        :note: The returned value is an instance of the authenticator class used to manage this user, not a db record.
        '''
        return self.manager.getInstance()

    def __unicode__(self):
        if self.is_meta:
            return "Meta group {0}(id:{1}) with groups {2}".format(self.name, self.id, list(self.groups.all()))
        else:
            return "Group {0}(id:{1}) from auth {2}".format(self.name, self.id, self.manager.name)

    @staticmethod
    def beforeDelete(sender, **kwargs):
        '''
        Used to invoke the Service class "Destroy" before deleting it from database.
        
        In this case, this is a dummy method, waiting for something useful to do :-)
        
        :note: If destroy raises an exception, the deletion is not taken.
        '''
        toDelete = kwargs['instance']
        # Todelete is a group
        
        # We invoke removeGroup. If this raises an exception, group will not
        # be removed
        toDelete.getManager().removeGroup(toDelete.name)

        # Clears related logs
        log.clearLogs(toDelete)
        
        logger.debug('Deleted group {0}'.format(toDelete))

signals.pre_delete.connect(Group.beforeDelete, sender = Group)
    
class UserPreference(models.Model):
    '''
    This class represents a single user preference for an user and a module
    '''
    module = models.CharField(max_length=32, db_index = True)
    name = models.CharField(max_length=32, db_index = True)
    value = models.CharField(max_length=128, db_index = True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name = 'preferences')

# Provisioned services
class DeployedService(models.Model):
    '''
    A deployed service is the Service produced element that is assigned finally to an user (i.e. a Virtual Machine, etc..)
    '''
    name = models.CharField(max_length=128, default = '')
    comments = models.CharField(max_length = 256, default = '')
    service = models.ForeignKey(Service, null=True, blank=True, related_name = 'deployedServices')
    osmanager = models.ForeignKey(OSManager, null=True, blank=True, related_name = 'deployedServices')
    transports = models.ManyToManyField(Transport, related_name='deployedServices', db_table = 'uds__ds_trans')
    assignedGroups = models.ManyToManyField(Group, related_name='deployedServices', db_table = 'uds__ds_grps')
    state = models.CharField(max_length = 1, default = State.ACTIVE, db_index = True)
    state_date = models.DateTimeField(default=NEVER)
    initial_srvs = models.PositiveIntegerField(default = 0)
    cache_l1_srvs = models.PositiveIntegerField(default = 0)
    cache_l2_srvs = models.PositiveIntegerField(default = 0)
    max_srvs = models.PositiveIntegerField(default = 0)
    current_pub_revision = models.PositiveIntegerField(default = 1)

    class Meta:
        '''
        Meta class to declare the name of the table at database
        '''
        db_table = 'uds__deployed_service'

    def getEnvironment(self):
        '''
        Returns an environment valid for the record this object represents
        '''
        return Environment.getEnvForTableElement(self._meta.verbose_name, self.id) 

    def activePublication(self):
        '''
        Returns the current valid publication for this deployed service.
        
        Returns:
            Publication db record if this deployed service has an valid active publication.
            
            None if there is no valid publication for this deployed service.
        '''
        try:
            return self.publications.filter(state=State.USABLE)[0]
        except Exception:
            return None
        
    def transformsUserOrPasswordForService(self):
        return self.osmanager.getType().transformsUserOrPasswordForService()

    def processUserPassword(self, username, password):
        '''
        This method is provided for consistency between UserService and DeployedService
        There is no posibility to check the username and password that a user will use to
        connect to a service at this level, because here there is no relation between both.
        
        The only function of this method is allow Transport to transform username/password in
        getConnectionInfo without knowing if it is requested by a DeployedService or an UserService 
        '''
        return [username, password]

    def isRestrained(self):
        '''
        Maybe this deployed service is having problems, and that may block some task in some
        situations.
        
        To avoid this, we will use a "restrain" policy, where we restrain a deployed service for,
        for example, create new cache elements is reduced.
        
        The policy to check is that if a Deployed Service has 3 errors in the last 20 Minutes (by default), it is
        considered restrained.
        
        The time that a service is in restrain mode is 20 minutes by default (1200 secs), but it can be modified
        at globalconfig variables
        '''
        from uds.core.util.Config import GlobalConfig
        
        if GlobalConfig.RESTRAINT_TIME.getInt() <= 0:
            return False # Do not perform any restraint check if we set the globalconfig to 0 (or less)
        
        date = getSqlDatetime() - timedelta(seconds=GlobalConfig.RESTRAINT_TIME.getInt())
        
        if self.userServices.filter(state=State.ERROR, state_date__gt=date).count() >= GlobalConfig.RESTRAINT_COUNT.getInt():
            return True
        
        return False
        

    def setState(self, state, save = True):
        '''
        Updates the state of this object and, optionally, saves it
        
        Args:
            state: new State to store at record

            save: Defaults to true. If false, record will not be saved to db, just modified
            
        '''
        self.state = state
        self.state_date = getSqlDatetime()
        if save is True:
            self.save()
        
    def remove(self):
        '''
        Marks the deployed service for removing.
        
        The background worker will be the responsible for removing the deployed service
        '''
        self.setState(State.REMOVABLE)

    def removed(self):
        '''
        Mark the deployed service as removed.
        
        A background worker will check for removed deloyed services and clean database of them.
        '''
        self.transports.clear()
        self.assignedGroups.clear()
        self.osmanager = None
        self.service = None
        self.setState(State.REMOVED)

        
    def markOldDeployedServicesAsRemovables(self, activePub):
        '''
        Used when a new publication is finished.
        
        Marks all user deployed services that belongs to this deployed service, that do not belongs 
        to "activePub" and are not in use as removable.
        
        Also cancels all preparing user services
        
        Better see the code, it's easier to understand :-)

        Args:
            activePub: Active publication used as "current" publication to make checks
        '''
        now = getSqlDatetime()
        if activePub == None:
            logger.error('No active publication, don\'t know what to erase!!! (ds = {0})'.format(self))
            return
        for ap in self.publications.exclude(id=activePub.id):
            for u in ap.userServices.filter(state=State.PREPARING):
                u.cancel()
            ap.userServices.exclude(cache_level=0).filter(state=State.USABLE).update(state=State.REMOVABLE, state_date = now)
            ap.userServices.filter(cache_level=0, state=State.USABLE, in_use=False).update(state=State.REMOVABLE, state_date = now)
            
    def validateUser(self, user):
        '''
        Validates that the user has access to this deployed service
        
        Args:
            user: User (db record) to check if has access to this deployed service
            
        Returns:
            True if has access
            
        Raises:
            InvalidUserException() if user do not has access to this deployed service

            InvalidServiceException() if user has rights to access, but the deployed service is not ready (no active publication)
        
        '''
        # We have to check if at least one group from this user is valid for this deployed service
        from uds.core import auths
        
        logger.debug('User: {0}'.format(user.id))
        logger.debug('DeployedService: {0}'.format(self.id))
        if len( set(user.getGroups()) & set(self.assignedGroups.all()) ) == 0:
            raise auths.Exceptions.InvalidUserException()
        if self.activePublication() is None and self.service.getType().publicationType is not None:
            raise InvalidServiceException()
        return True
    
    @staticmethod
    def getDeployedServicesForGroups(groups):
        '''
        Return deployed services with publications for the groups requested.
        
        Args:
            groups: List of groups to check
            
        Returns:
            List of accesible deployed services
        '''
        from uds.core import services
        list1 = DeployedService.objects.filter(assignedGroups__in=groups, assignedGroups__state__exact=State.ACTIVE, state = State.ACTIVE).distinct().annotate(cuenta=models.Count('publications')).exclude(cuenta__eq=0)
        # Now get deployed services that DO NOT NEED publication
        doNotNeedPublishing = [ t.type() for t in services.factory().servicesThatDoNotNeedPublication() ]
        list2 = DeployedService.objects.filter(assignedGroups__in=groups, assignedGroups__state__exact=State.ACTIVE, service__data_type__in=doNotNeedPublishing, state = State.ACTIVE)
        return [ r for r in list1 ] + [ r for r in list2 ]
        
    
    def publish(self):
        '''
        Launches the publication of this deployed service.
        
        No check is done, it simply redirects the request to PublicationManager, where checks are done.
        '''
        from uds.core.managers.PublicationManager import PublicationManager
        PublicationManager.manager().publish(self)
        
    def unpublish(self):
        '''
        Unpublish (removes) current active publcation.
        
        It checks that there is an active publication, and then redirects the request to the publication itself
        '''
        pub = self.activePublication()
        if pub is not None:
            pub.unpublish()

    def cachedUserServices(self):
        '''
        Utility method to access the cached user services (level 1 and 2)
        
        Returns:
            A list of db records (userService) with cached user services
        '''
        return self.userServices.exclude(cache_level=0)
    
    def assignedUserServices(self):
        '''
        Utility method to access the assigned user services
        
        Returns:
            A list of db records (userService) with assinged user services
        '''
        return self.userServices.filter(cache_level=0)
    
    def erroneousUserServices(self):
        '''
        Utility method to locate invalid assigned user services.
        
        If an user deployed service is assigned, it MUST have an user associated.
        
        If it don't has an user associated, the user deployed service is wrong.
        '''
        return self.userServices.filter(cache_level=0, user=None)

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
        
        # Clears related logs
        log.clearLogs(toDelete)
        
        logger.debug('Deleting Deployed Service {0}'.format(toDelete))
        
    def __unicode__(self):
        return u"Deployed service {0}({1}) with {2} as initial, {3} as L1 cache, {4} as L2 cache, {5} as max".format(
                        self.name, self.id, self.initial_srvs, self.cache_l1_srvs, self.cache_l2_srvs, self.max_srvs)
    

# Connects a pre deletion signal to Authenticator
signals.pre_delete.connect(DeployedService.beforeDelete, sender = DeployedService)
    
class DeployedServicePublication(models.Model):
    '''
    A deployed service publication keep track of data needed by services that needs "preparation". (i.e. Virtual machine --> base machine --> children of base machines)
    '''
    deployed_service = models.ForeignKey(DeployedService, on_delete=models.CASCADE, related_name = 'publications')
    publish_date = models.DateTimeField(db_index = True)
    # data_type = models.CharField(max_length=128) # The data type is specified by the service itself
    data = models.TextField(default='')
    # Preparation state. The preparation of a service is a task that runs over time, we need to:
    #   * Prepare it
    #   * Use it
    #   * Remove it
    #   * Mark as failed
    # The responsible class will notify when we have to change state, and a deployed service will only be usable id it has at least 
    # a prepared service "Usable" or it doesn't need to prepare anything (needsDeployment = False)
    state = models.CharField(max_length = 1, default = State.PREPARING, db_index = True)
    state_date = models.DateTimeField()
    revision = models.PositiveIntegerField(default = 1)

    class Meta:
        '''
        Meta class to declare default order and unique multiple field index
        '''
        db_table = 'uds__deployed_service_pub'
        ordering = ('publish_date',)

    def getEnvironment(self):
        '''
        Returns an environment valid for the record this object represents
        '''
        return Environment.getEnvForTableElement(self._meta.verbose_name, self.id)
    
    def getInstance(self):
        '''
        Instantiates the object this record contains.
        
        Every single record of Provider model, represents an object.
        
        Args:
           values (list): Values to pass to constructor. If no values are especified,
                          the object is instantiated empty and them de-serialized from stored data.
        
        Returns:
            The instance Instance of the class this provider represents
        
        Raises:
        '''
        serviceInstance = self.deployed_service.service.getInstance()
        osManagerInstance = self.deployed_service.osmanager
        if osManagerInstance is not None:
            osManagerInstance = osManagerInstance.getInstance()
        # Sanity check, so it's easier to find when we have created
        # a service that needs publication but do not have
         
        if serviceInstance.publicationType is None:
            raise Exception('Tried to get a publication instance for a service that do not needs it')
            
        if serviceInstance.publicationType is None:
            raise Exception('Class {0} do not have defined publicationType but needs to be published!!!'.format(serviceInstance.__class__.__name))
            
        dpl = serviceInstance.publicationType(self.getEnvironment(), service = serviceInstance, osManager = osManagerInstance, revision = self.revision, dsName = self.deployed_service.name )
        # Only invokes deserialization if data has something. '' is nothing
        if self.data != '' and self.data is not None:
            dpl.unserialize(self.data)
        return dpl
    
    def updateData(self, dsp):
        '''
        Updates the data field with the serialized uds.core.services.Publication 
        
        Args:
            dsp: uds.core.services.Publication to serialize
            
        :note: This method do not saves the updated record, just updates the field
        '''
        self.data = dsp.serialize()
        
    def setState(self, state):
        '''
        Updates the state of this object and, optionally, saves it
        
        Args:
            state: new State to store at record

            save: Defaults to true. If false, record will not be saved to db, just modified
            
        '''
        self.state_date = getSqlDatetime()
        self.state = state
        
    def unpublish(self):
        '''
        Tries to remove the publication
        
        No check is done, it simply redirects the request to PublicationManager, where checks are done.
        '''
        from uds.core.managers.PublicationManager import PublicationManager
        PublicationManager.manager().unpublish(self)
        
    def cancel(self):
        '''
        Invoques the cancelation of this publication 
        '''
        from uds.core.managers.PublicationManager import PublicationManager
        PublicationManager.manager().cancel(self)
        

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
        
        # Delete method is invoked directly by PublicationManager,
        # Destroying a publication is not obligatory an 1 step action.
        # It's handled as "publish", and as so, it can be a multi-step process
        
        # Clears related logs
        log.clearLogs(toDelete)
        
        
        logger.debug('Deleted publication {0}'.format(toDelete))
        
        

# Connects a pre deletion signal to Authenticator
signals.pre_delete.connect(DeployedServicePublication.beforeDelete, sender = DeployedServicePublication)

class UserService(models.Model):
    '''
    This is the base model for assigned user service and cached user services.
    This are the real assigned services to users. DeployedService is the container (the group) of this elements.
    '''
    # The reference to deployed service is used to accelerate the queries for different methods, in fact its redundant cause we can access to the deployed service
    # through publication, but queries are much more simple
    deployed_service = models.ForeignKey(DeployedService, on_delete=models.CASCADE, related_name = 'userServices')
    publication = models.ForeignKey(DeployedServicePublication, on_delete=models.CASCADE, null=True, blank=True, related_name = 'userServices')
    
    unique_id = models.CharField(max_length=128, default ='', db_index = True) # User by agents to locate machine
    friendly_name = models.CharField(max_length=128, default = '')
    # We need to keep separated two differents os states so service operations (move beween caches, recover service) do not affects os manager state
    state = models.CharField(max_length=1, default=State.PREPARING, db_index = True) # We set index so filters at cache level executes faster
    os_state = models.CharField(max_length=1, default=State.PREPARING) # The valid values for this field are PREPARE and USABLE
    state_date = models.DateTimeField(auto_now_add=True, db_index = True)
    creation_date = models.DateTimeField(db_index = True)
    data = models.TextField(default='')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name = 'userServices', null=True, blank=True, default = None)
    in_use = models.BooleanField(default=False)
    in_use_date = models.DateTimeField(default=NEVER)
    cache_level = models.PositiveSmallIntegerField(db_index=True, default=0) # Cache level must be 1 for L1 or 2 for L2, 0 if it is not cached service

    src_hostname = models.CharField(max_length=64, default='')
    src_ip = models.CharField(max_length=15, default='')

    objects = LockingManager()

    class Meta:
        '''
        Meta class to declare default order and unique multiple field index
        '''
        db_table = 'uds__user_service'
        ordering = ('creation_date',)

    def getEnvironment(self):
        '''
        Returns an environment valid for the record this object represents.
        
        In the case of the user, there is an instatiation of "generators". 
        Right now, there is two generators provided to child instance objects, that are
        valid for generating unique names and unique macs. In a future, there could be more generators
        
        To access this generators, use the Envirnment class, and the keys 'name' and 'mac'.
        
        (see related classes uds.core.util.UniqueNameGenerator and uds.core.util.UniqueMacGenerator)
        '''
        from uds.core.util.UniqueMacGenerator import UniqueMacGenerator
        from uds.core.util.UniqueNameGenerator import UniqueNameGenerator
        return Environment.getEnvForTableElement(self._meta.verbose_name, self.id, {'mac' : UniqueMacGenerator, 'name' : UniqueNameGenerator } )

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
        try: # We may have deleted publication...
            if self.publication != None:
                publicationInstance = self.publication.getInstance()
        except Exception, e:
            # The publication to witch this item points to, does not exists
            self.publication = None
            logger.error("Got exception at getInstance of an userService {0} : {1}".format(e.__class__, e))
        if serviceInstance.deployedType is None:
            raise Exception('Class {0} needs deployedType but it is not defined!!!'.format(serviceInstance.__class__.__name__))
        us = serviceInstance.deployedType(self.getEnvironment(), service = serviceInstance, publication = publicationInstance, osmanager = osmanagerInstance, dbservice = self)
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
        self.getEnvironment().storage().put(name, value)
    
    def recoverValue(self, name):
        '''
        Recovers a value from custom storage
        
        Args:
            name: Name of values to recover
            
        Returns:
            Stored value, None if no value was stored
        '''
        return self.getEnvironment().storage().get(name)
    
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
    
    def needsOsManager(self):
        return self.deployed_service.osmanager is not None
    
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
        self.state_date = getSqlDatetime()
        self.state = state
        
    def setOsState(self, state):
        '''
        Updates the os state (state of the os) of this object and, optionally, saves it
        
        Args:
            state: new State to store at record

            save: Defaults to true. If false, record will not be saved to db, just modified
            
        '''
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
        if state is False: # Service released, check y we should mark it for removal
            # If our publication is not current, mark this for removal
            UserServiceManager.manager().checkForRemoval(self)
        
        
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

    def remove(self):
        '''
        Mark this user deployed service for removal
        '''
        self.setState(State.REMOVABLE)
        self.save()
        
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
            if us.deployed_service.state != State.ACTIVE: # Do not show removing or removed services
                continue;
            usi = us.getInstance()
            if usi.service().mustAssignManually is False:
                continue
            res.append({ 'id' : us.id, 'name' : usi.getName(), 'transports' : us.deployed_service.transports, 'service' : us })
        return res

    def __unicode__(self):
        return "User service {0}, cache_level {1}, user {2}, name {3}".format(self.id, self.cache_level, self.user, self.friendly_name)

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
        
        # TODO: Check if this invokation goes here
        #toDelete.getInstance()
        
        logger.debug('Deleted user service {0}'.format(toDelete))
        
# Connects a pre deletion signal to Authenticator
signals.pre_delete.connect(UserService.beforeDelete, sender = UserService)

# Especific loggin information for an user service
class Log(models.Model):
    '''
    Log model associated with an object.
    
    This log is mainly used to keep track of log relative to objects
    (such as when a user access a machine, or information related to user logins/logout, errors, ...) 
    '''

    owner_id = models.IntegerField(db_index=True, default=0)
    owner_type = models.SmallIntegerField(db_index=True, default=0)
    
    created = models.DateTimeField(db_index=True)
    source = models.CharField(max_length=16, default='internal', db_index=True)    
    level = models.PositiveSmallIntegerField(default=0, db_index=True)
    data = models.CharField(max_length=255, default='')
    
    
    class Meta:
        '''
        Meta class to declare db table
        '''
        db_table = 'uds_log'
    

    def __unicode__(self):
        return u"Log of {0}({1}): {2} - {3} - {4} - {5}".format(self.owner_type, self.owner_id, self.created, self.source, self.level, self.data)


class StatsCounters(models.Model):
    '''
    Counter statistocs mpdes the counter statistics
    '''
    
    owner_id = models.IntegerField(db_index=True, default=0)
    owner_type = models.SmallIntegerField(db_index=True, default=0)
    counter_type = models.SmallIntegerField(db_index=True, default=0)
    stamp = models.IntegerField(db_index=True, default=0)
    value = models.IntegerField(db_index=True, default=0)
    
    class Meta:
        '''
        Meta class to declare db table
        '''
        db_table = 'uds_stats_c'
    

    @staticmethod
    def get_grouped(owner_type, counter_type, **kwargs):
        '''
        Returns the average stats grouped by interval for owner_type and owner_id (optional)
        
        Note: if someone cant get this more optimized, please, contribute it!
        '''
        
        filt = 'owner_type'
        if type(owner_type) in (list, tuple):
            filt += ' in (' + ','.join((str(x) for x in owner_type)) + ')'
        else:  
            filt += '='+str(owner_type)
        
        owner_id = None
        if kwargs.get('owner_id', None) is not None:
            filt += ' AND OWNER_ID'
            oid = kwargs['owner_id']
            if type(oid) in (list, tuple):
                filt += ' in (' + ','.join(str(x) for x in oid) + ')'
            else:
                filt += '='+str(oid)
        
        filt += ' AND counter_type='+str(counter_type)
        
        since = kwargs.get('since', None)
        to = kwargs.get('to', None)
        
        since = since and int(since) or NEVER_UNIX
        to = to and int(to) or getSqlDatetime(True)    
            
        interval = 600 # By default, group items in ten minutes interval (600 seconds)
        
        limit = kwargs.get('limit', None)
        
        
        if limit is not None:
            limit = int(limit)
            elements = kwargs['limit']
            
            # Protect for division a few lines below... :-)
            if elements < 2:
                elements = 2
            
            if owner_id is None:
                q = StatsCounters.objects.filter(stamp__gte=since, stamp__lte=to)
            else:
                q = StatsCounters.objects.filter(owner_id=owner_id, stamp__gte=since, stamp__lte=to)
                
            if type(owner_type) in (list, tuple):
                q = q.filter(owner_type__in=owner_type)
            else:
                q = q.filter(owner_type=owner_type)
                
            if q.count() > elements:
                first = q.order_by('stamp')[0].stamp
                last = q.order_by('stamp').reverse()[0].stamp
                interval = int((last-first)/(elements-1))

        filt += ' AND stamp>={0} AND stamp<={1} GROUP BY CEIL(stamp/{2}) ORDER BY stamp'.format(
                            since, to, interval)

        fnc = kwargs.get('use_max', False) and 'MAX' or 'AVG'
            
        query = ('SELECT -1 as id,-1 as owner_id,-1 as owner_type,-1 as counter_type,stamp,' 
                        'CEIL({0}(value)) AS value ' 
                 'FROM {1} WHERE {2}').format(fnc, StatsCounters._meta.db_table, filt)
                 
        logger.debug('Stats query: {0}'.format(query))
                 
        # We use result as an iterator
        return StatsCounters.objects.raw(query)

    def __unicode__(self):
        return u"Log of {0}({1}): {2} - {3} - {4}".format(self.owner_type, self.owner_id, self.stamp, self.counter_type, self.value)
    
    
class StatsEvents(models.Model):
    '''
    Counter statistocs mpdes the counter statistics
    '''
    
    owner_id = models.IntegerField(db_index=True, default=0)
    owner_type = models.SmallIntegerField(db_index=True, default=0)
    event_type = models.SmallIntegerField(db_index=True, default=0)
    stamp = models.IntegerField(db_index=True, default=0)
    
    class Meta:
        '''
        Meta class to declare db table
        '''
        db_table = 'uds_stats_e'
    

    def __unicode__(self):
        return u"Log of {0}({1}): {2} - {3} - {4} - {5}".format(self.owner_type, self.owner_id, self.created, self.source, self.level, self.data)



# General utility models, such as a database cache (for caching remote content of slow connections to external services providers for example)
# We could use django cache (and maybe we do it in a near future), but we need to clean up things when objecs owning them are deleted
class Cache(models.Model):
    '''
    General caching model. This model is managed via uds.core.util.Cache.Cache class
    '''
    owner = models.CharField(max_length = 128, db_index = True)
    key = models.CharField(max_length = 64, primary_key = True)
    value = models.TextField(default = '')
    created = models.DateTimeField()                # Date creation or validation of this entry. Set at write time
    validity = models.IntegerField(default = 60)    # Validity of this entry, in seconds
    
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
        expired = datetime.now() > self.created + timedelta(seconds = self.validity)
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
    value = models.TextField(default = '')
    crypt = models.BooleanField(default = False)
    long = models.BooleanField(default = False)
    
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
    owner = models.CharField(max_length = 128, db_index = True)
    key = models.CharField(max_length = 64, primary_key = True)
    data = models.TextField(default = '')
    attr1 = models.CharField(max_length = 64, db_index = True, null=True, blank=True, default = None)
    
    objects = LockingManager()
    
    def __unicode__(self):
        return u"{0} {1} = {2}, {3}".format(self.owner, self.key, self.data, str.join( '/', [self.attr1]))
    
class UniqueId(models.Model):
    '''
    Unique ID Database. Used to store unique names, unique macs, etc...
    Managed via uds.core.util.UniqueIDGenerator.UniqueIDGenerator
    '''
    owner = models.CharField(max_length = 128, db_index = True, default = '')
    basename = models.CharField(max_length = 32, db_index = True)
    seq = models.BigIntegerField(db_index=True)
    assigned = models.BooleanField(db_index=True, default = True)

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
    
    DAY = 60*60*24
    HOUR = 60*60
    MIN = 60
    
    name = models.CharField(max_length = 64, unique = True)
    frecuency = models.PositiveIntegerField(default = DAY)
    last_execution = models.DateTimeField(auto_now_add = True)
    next_execution = models.DateTimeField(default = NEVER, db_index = True)
    owner_server = models.CharField(max_length=64, db_index = True, default = '')
    state = models.CharField(max_length = 1, default = State.FOR_EXECUTE, db_index = True)

    #objects = LockingManager()
    
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
signals.pre_delete.connect(Scheduler.beforeDelete, sender = Scheduler)

    
class DelayedTask(models.Model):
    '''
    A delayed task is a kind of scheduled task. It's a task that has more than is executed at a delay
    specified at record. This is, for example, for publications, service preparations, etc...
    
    The delayed task is different from scheduler in the fact that they are "one shot", meaning this that when the
    specified delay is reached, the task is executed and the record is removed from the table.
    
    This table contains uds.core.util.jobs.DelayedTask references
    '''
    type = models.CharField(max_length=128)
    tag = models.CharField(max_length=64, db_index = True)  # A tag for letting us locate delayed publications...
    instance = models.TextField()
    insert_date = models.DateTimeField(auto_now_add = True)
    execution_delay = models.PositiveIntegerField()
    execution_time = models.DateTimeField(db_index = True)
    
    #objects = LockingManager()

    def __unicode__(self):
        return u"Run Queue task {0} owned by {3},inserted at {1} and with {2} seconds delay".format(self.type, self.insert_date, self.execution_delay, self.owner_server)
    

class Network(models.Model):
    '''
    This model is used for keeping information of networks associated with transports (right now, just transports..)
    '''
    name = models.CharField(max_length = 64, unique = True)
    net_start = models.BigIntegerField(db_index = True)
    net_end = models.BigIntegerField(db_index = True)
    transports = models.ManyToManyField(Transport, related_name='networks', db_table='uds_net_trans')

    @staticmethod
    def ipToLong(ip):
        '''
        convert decimal dotted quad string to long integer
        '''
        try:
            hexn = ''.join(["%02X" % long(i) for i in ip.split('.')])
            return long(hexn, 16)
        except:
            return 0 # Invalid values will map to "0.0.0.0" --> 0
    
    @staticmethod
    def longToIp(n):
        '''
        convert long int to dotted quad string
        '''
        try:
            d = 256 * 256 * 256
            q = []
            while d > 0:
                m,n = divmod(n,d)
                q.append(str(m))
                d = d/256
    
            return '.'.join(q)
        except:
            return '0.0.0.0' # Invalid values will map to "0.0.0.0"

    @staticmethod
    def networksFor(ip):
        '''
        Returns the networks that are valid for specified ip in dotted quad (xxx.xxx.xxx.xxx)
        '''
        ip = Network.ipToLong(ip)
        return Network.objects.filter(net_start__lte=ip, net_end__gte=ip)
    
    @staticmethod
    def create(name, netStart, netEnd):
        '''
        Creates an network record, with the specified net start and net end (dotted quad)
        
        Args:
            netStart: Network start
            
            netEnd: Network end
        '''
        return Network.objects.create(name=name, net_start = Network.ipToLong(netStart), net_end = Network.ipToLong(netEnd)) 

    @property    
    def netStart(self):
        '''
        Property to access the quad dotted format of the stored network start
        
        Returns:
            string representing the dotted quad of this network start
        '''
        return Network.longToIp(self.net_start)
    
    @property
    def netEnd(self):
        '''
        Property to access the quad dotted format of the stored network end
        
        Returns:
            string representing the dotted quad of this network end
        '''
        return Network.longToIp(self.net_end)

    def update(self, name, netStart, netEnd):
        '''
        Updated this network with provided values
        
        Args:
            name: new name of the network
            
            netStart: new Network start (quad dotted)
            
            netEnd: new Network end (quad dotted)
        '''
        self.name = name
        self.net_start = Network.ipToLong(netStart)
        self.net_end = Network.ipToLong(netEnd)
        self.save() 
    
    def __unicode__(self):
        return u'Network {0} from {1} to {2}'.format(self.name, Network.longToIp(self.net_start), Network.longToIp(self.net_end))

