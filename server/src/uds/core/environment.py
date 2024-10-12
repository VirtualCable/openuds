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
import secrets
import collections.abc

from uds.core.util import unique_name_generator, unique_gid_generator, unique_mac_generator

if typing.TYPE_CHECKING:
    from uds.core.util.cache import Cache
    from uds.core.util.storage import Storage
    from uds.core.util.unique_id_generator import UniqueGenerator


TEST_ENV = 'testing_env'
COMMON_ENV = 'global'

# Generators of ids
GENERATORS_TYPES: typing.Final[collections.abc.Mapping[str, type['UniqueGenerator']]] = {
    'mac': unique_mac_generator.UniqueMacGenerator,
    'name': unique_name_generator.UniqueNameGenerator,
    'id': unique_gid_generator.UniqueGIDGenerator,
}


class Environment:
    """
    Class to manipulate the associated environment with "environmentable" classes (mainly modules).
    It purpose is to provide an "object owned" environment, so every db record can contain associated values
    not stored with main module data.
    The environment is composed of a "cache" and a "storage". First are volatile data, while second are persistent data.
    """

    __slots__ = ['_key', '_cache', '_storage', '_id_generators']

    _key: str
    _cache: 'Cache'
    _storage: 'Storage'
    _id_generators: dict[str, 'UniqueGenerator']

    def __init__(
        self,
        unique_key: str,
    ):
        """
        Initialized the Environment for the specified id

        Args:
            unique_key: Unique key for the environment
        """
        # Avoid circular imports
        from uds.core.util.cache import Cache  # pylint: disable=import-outside-toplevel
        from uds.core.util.storage import Storage  # pylint: disable=import-outside-toplevel

        self._key = unique_key
        self._cache = Cache(unique_key)
        self._storage = Storage(unique_key)

        self._id_generators = {k: v(self._key) for k, v in GENERATORS_TYPES.items()}

    @property
    def cache(self) -> 'Cache':
        """
        Method to acces the cache of the environment.
        @return: a referente to a Cache instance
        """
        return self._cache

    @property
    def storage(self) -> 'Storage':
        """
        Method to acces the cache of the environment.
        @return: a referente to an Storage Instance
        """
        return self._storage

    def id_generator(self, generator_id: str) -> 'UniqueGenerator':
        """
        The idea of generator of id is to obtain at some moment Ids with a proper generator.
        If the environment do not contains generators of id, this method will return None.
        The id generator feature is used by User Services to obtain different auto-id generators, as macs or names
        @param generatorId: Id of the generator to obtain
        @return: Generator for that id, or None if no generator for that id is found
        """
        if not self._id_generators or generator_id not in self._id_generators:
            raise Exception(f'No generator found for {generator_id}')
        return self._id_generators[generator_id]

    @property
    def key(self) -> str:
        """
        @return: the key used for this environment
        """
        return self._key

    def clean_related_data(self) -> None:
        """
        Removes all related information from database for this environment.
        """
        self._cache.clear()
        self._storage.clear()
        for _, v in self._id_generators.items():
            v.release()

    @staticmethod
    def environment_for_table_record(
        table_name: str,
        record_id: 'str|int|None' = None,
    ) -> 'Environment':
        """
        From a table name, and a id, tries to load the associated environment or creates a new
        one if no environment exists at database. The table name and the id are used to obtain the key
        for the environment, so each element at database can have its own environment.
        @param tblName: Table name
        @param id_: Id of the element (normally primary key of the record for which we want an environment)
        @param idGeneratorsTypes: Associated Generators. Defaults to none
        @return: Obtained associated environment (may be empty if none exists at database, but it will be valid)
        """

        if isinstance(record_id, int):  # So we keep zero int value
            record_id = str(record_id)
        record_id = record_id or ''  # If no record id, get environment for table instead of record

        name = 't-' + table_name + '-' + record_id
        return Environment(name)

    @staticmethod
    def type_environment(type_: typing.Type[typing.Any]) -> 'Environment':
        """
        Obtains an environment associated with a type instead of a record
        @param type_: Type
        @return Associated Environment
        """
        return Environment('type-' + str(type_))

    @staticmethod
    def private_environment(owner: typing.Any) -> 'Environment':
        """
        Obtains an environment with an unique identifier
        @return: An environment with an unique identifier
        """
        return Environment('#_#' + str(owner) + '#^#')

    @staticmethod
    def temporary_environment() -> 'Environment':
        """
        Obtains an enviromnet with an unique identifier

        Returns:
            An environment with an unique identifier

        Note:
            Use this with "with" statement to ensure that environment is cleared after use
        """
        return Environment(
            '#_#' + secrets.token_hex(16) + '#^#'
        )  # Weird enough name to be unique, unless you try hard :)

    @staticmethod
    def testing_environment() -> 'Environment':
        """
        Provides a temporary environment needed in some calls (test provider, for example)
        It will not make environment persistent
        """
        env = Environment(TEST_ENV)
        env.clean_related_data()
        return env

    @staticmethod
    def common_environment() -> 'Environment':
        """
        Provides global environment
        """
        return Environment(COMMON_ENV)  # This environment is a global environment for general utility.

    def __enter__(self) -> 'Environment':
        return self

    def __exit__(self, exc_type: typing.Any, exc_value: typing.Any, traceback: typing.Any) -> None:
        if self._key == TEST_ENV or (self._key.startswith('#_#') and self._key.endswith('#^#')):
            self.clean_related_data()


class Environmentable:
    """
    This is a base class provided for all objects that have an environment associated. These are mainly modules
    """

    __slots__ = ['_env']

    _env: Environment

    def __init__(self, environment: 'Environment'):
        """
        Initialized the element

        Args:
            environment: Environment to associate with
        """
        self._env = environment

    @property
    def env(self) -> 'Environment':
        """
        Utility method to access the envionment contained by this object

        Returns:
            Environmnet for the object
        """
        return self._env

    @env.setter
    def env(self, environment: 'Environment') -> None:
        """
        Assigns a new environment

        Args:
            environment: Environment to assign
        """
        self._env = environment

    @property
    def cache(self) -> 'Cache':
        """
        Utility method to access the cache of the environment containe by this object

        Returns:
            Cache for the object
        :rtype uds.core.util.cache.Cache
        """
        return self._env.cache

    @property
    def storage(self) -> 'Storage':
        """
        Utility method to access the storage of the environment containe by this object

        Returns:
            Storage for the object

        :rtype uds.core.util.storage.Storage
        """
        return self._env.storage

    def id_generator(self, generatorId: str) -> 'UniqueGenerator':
        """
        Utility method to access the id generator of the environment containe by this object

        Args:
            generatorId: Id of the generator to obtain

        Returns:
            Generator for the object and the id specified
        """
        return self._env.id_generator(generatorId)
