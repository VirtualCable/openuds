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

TEMP_ENV = 'temporary'
GLOBAL_ENV = 'global'


class Environment(object):
    '''
    Class to manipulate the associated environment with "environmentable" classes (mainly modules).
    It purpose is to provide an "object owned" environment, so every db record can contain associated values
    not stored with main module data.
    The environment is composed of a "cache" and a "storage". First are volatile data, while second are persistent data.
    '''

    def __init__(self, uniqueKey, idGenerators={}):
        '''
        Initialized the Environment for the specified id
        @param uniqueId: Key for this environment
        @param idGenerators: Hash of generators of ids for this environment. This "generators of ids" feature
            is used basically at User Services to auto-create ids for macs or names, using
            {'mac' : UniqueMacGenerator, 'name' : UniqueNameGenerator } as argument.
        '''
        from uds.core.util.Cache import Cache
        from uds.core.util.Storage import Storage
        self._key = uniqueKey
        self._cache = Cache(uniqueKey)
        self._storage = Storage(uniqueKey)
        self._idGenerators = idGenerators

    @property
    def cache(self):
        '''
        Method to acces the cache of the environment.
        @return: a referente to a Cache instance
        :rtype uds.core.util.Cache.Cache
        '''
        return self._cache

    @property
    def storage(self):
        '''
        Method to acces the cache of the environment.
        @return: a referente to an Storage Instance
        :rtype uds.core.util.Storage.Storage
        '''
        return self._storage

    def idGenerators(self, generatorId):
        '''
        The idea of generator of id is to obtain at some moment Ids with a proper generator.
        If the environment do not contains generators of id, this method will return None.
        The id generator feature is used by User Services to obtain different auto-id generators, as macs or names
        @param generatorId: Id of the generator to obtain
        @return: Generator for that id, or None if no generator for that id is found
        '''
        return self._idGenerators.get(generatorId, None)

    @property
    def key(self):
        '''
        @return: the key used for this environment
        '''
        return self._key

    def clearRelatedData(self):
        '''
        Removes all related information from database for this environment.
        '''
        from uds.core.util.Cache import Cache
        from uds.core.util.Storage import Storage
        Cache.delete(self._key)
        Storage.delete(self._key)
        for __, v in self._idGenerators.iteritems():
            v.release()

    @staticmethod
    def getEnvForTableElement(tblName, id_, idGeneratorsTypes={}):
        '''
        From a table name, and a id, tries to load the associated environment or creates a new
        one if no environment exists at database. The table name and the id are used to obtain the key
        for the environment, so each element at database can have its own environment.
        @param tblName: Table name
        @param id_: Id of the element (normally primary key of the record for which we want an environment)
        @param idGeneratorsTypes: Associated Generators. Defaults to none
        @return: Obtained associated environment (may be empty if none exists at database, but it will be valid)
        '''
        name = 't-' + tblName + '-' + str(id_)
        idGenerators = {}
        for k, v in idGeneratorsTypes.iteritems():
            idGenerators[k] = v(name)
        return Environment(name, idGenerators)

    @staticmethod
    def getEnvForType(type_):
        '''
        Obtains an environment associated with a type instead of a record
        @param type_: Type
        @return Associated Environment
        '''
        return Environment('type-' + str(type_))

    @staticmethod
    def getTempEnv():
        '''
        Provides a temporary environment needed in some calls (test provider, for example)
        It will not make environment persistent
        '''
        return Environment(TEMP_ENV)  # TODO: In fact, we should provide a "null" cache and a "null" storage, but for now this is right

    @staticmethod
    def getGlobalEnv():
        '''
        Provides global environment
        '''
        return Environment(GLOBAL_ENV)  # This environment is a global environment for general utility.


class Environmentable(object):
    '''
    This is a base class provided for all objects that have an environment associated. These are mainly modules
    '''

    def __init__(self, environment):
        '''
        Initialized the element

        Args:
            environment: Environment to associate with
        '''
        self._env = environment

    @property
    def env(self):
        '''
        Utility method to access the envionment contained by this object

        Returns:
            Environmnet for the object
        '''
        return self._env

    @env.setter
    def env(self, environment):
        '''
        Assigns a new environment

        Args:
            environment: Environment to assign
        '''
        self._env = environment

    @property
    def cache(self):
        '''
        Utility method to access the cache of the environment containe by this object

        Returns:
            Cache for the object
        :rtype uds.core.util.Cache.Cache
        '''
        return self._env.cache

    @property
    def storage(self):
        '''
        Utility method to access the storage of the environment containe by this object

        Returns:
            Storage for the object

        :rtype uds.core.util.Storage.Storage
        '''
        return self._env.storage

    def idGenerators(self, generatorId):
        '''
        Utility method to access the id generator of the environment containe by this object

        Args:
            generatorId: Id of the generator to obtain

        Returns:
            Generator for the object and the id specified
        '''
        return self._env.idGenerators(generatorId)
