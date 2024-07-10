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
import abc
import logging
import os.path
import sys
import typing

from django.utils.translation import gettext as _

from uds.core import types
from uds.core.ui.user_interface import UserInterface
from uds.core.util import utils, log

from .environment import Environment, Environmentable
from .serializable import Serializable

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from uds.models.uuid_model import UUIDModel


class Module(UserInterface, Environmentable, Serializable, abc.ABC):
    """
    Base class for all modules used by UDS.
    This base module provides all the needed methods that modules must implement

    All modules must, at least, implement the following:

    * Attributes:
       * :py:attr:`.type_name`:
         Name for this type of module (human readable) to assign to the module (string)
         This name will be used to let the administrator identify this module.
       * :py:attr:`.type_type`:
         Name for this type of module (machine only) to assing to the module (string)
         This name will be used internally to identify when a serialized module corresponds with this class.
       * :py:attr:`.type_description`:
         Description for this type of module.
         This descriptio will be used to let the administrator identify what this module provides
       * :py:attr:`.icon_file`: This is an icon file, in png format, used at administration client to identify this module.
         This parameter may be optionall if you override the "icon" method.
    * Own Methods:
       * :py:meth:`.__init__`
         The default constructor. The environment value is always provided (see Environment), but the
         default values provided can be None.
         Remember to allow the instantiation of the module with default params, because when deserialization is done,
         the process is first instatiate with an environment but no parameters and then call "unmarshal" from Serializable.
       * :py:meth:`.test`
       * :py:meth:`.check`
       * :py:meth:`.destroy`: Optional
       * :py:meth:`.icon`: Optional, if you provide an icon file, this method loads it from module folder,
         but you can override this so the icon is obtained from other source.
       * :py:meth:`.marshal`
         By default, this method serializes the values provided by user in form fields. You can override it,
         but now it's not needed because you can access config vars using Form Fields.

         Anyway, if you override this method, you must also override next one
       * :py:meth:`.unmarshal`
         By default, this method de-serializes the values provided by user in form fields. You can override it,
         but now it's not needed because you can access config vars using Form Fields.

         Anyway, if you override this method, you must also override previous one

    * UserInterface Methods:
       * :py:meth:`from from uds.core.ui.dict_of_values`
         This method, by default, provides the values contained in the form fields. If you don't override the marshal and
         unmarshal, this method should be fine as is for you also.


    Environmentable is a base class that provides utility method to access a separate Environment for every single
    module.
    """

    # Import variable indicating this module is a base class not a real module
    # Note that Module is not a real module, but a base class for all modules so is_base is not used on this class
    # This means that is_base is set as a default here, but not checked for Module NEVER (but for subclasses)
    is_base: typing.ClassVar[bool] = False

    # : Which coded to use to encode module by default.
    # : Basic name used to provide the administrator an "huma readable" form for the module
    type_name: typing.ClassVar[str] = 'Base Module'
    # : Internal type name, used by system to locate this module
    type_type: typing.ClassVar[str] = 'BaseModule'
    # : Description of this module, used at admin level
    type_description: typing.ClassVar[str] = 'Base Module'
    # : Icon file, relative to module folders
    # This is expected to be png, use this format always
    icon_file: typing.ClassVar[str] = 'base.png'

    # if this modules is marked as "Experimental"
    experimental: typing.ClassVar[bool] = False

    # uuid of this module, if any
    # Maybe used by some modules to identify themselves
    _uuid: str

    def __init__(
        self,
        environment: Environment,
        values: 'types.core.ValuesType' = None,
        uuid: typing.Optional[str] = None,
    ):
        """
        Do not forget to invoke this in your derived class using
        "super(self.__class__, self).__init__(environment, values)".

        We want to use the env, cache and storage methods outside class.
        If not called, you must implement your own methods.

        cache and storage are "convenient" methods to access _env.cache and
        _env.storage

        The values param is passed directly to UserInterface base.

        The environment param is passed directly to environment.

        Values are passed to __initialize__ method. It this is not None,
        the values contains a dictionary of values received from administration gui,
        that contains the form data requested from user.

        If you override marshal, unmarshal and inherited UserInterface method
        dict_of_values, you must also take account of values (dict) provided at the
        __init__ method of your class.
        """
        UserInterface.__init__(self, values)
        Environmentable.__init__(self, environment)
        Serializable.__init__(self)
        self._uuid = uuid or ''

    def marshal(self) -> bytes:
        """
        By default and if not overriden by descendants, this method, overridden
        from Serializable, and returns the serialization of
        form field stored values.
        """
        return self.serialize_fields()

    def unmarshal(self, data: bytes) -> None:
        """
        By default and if not overriden by descendants, this method recovers
        data serialized using serializeForm
        """
        if self.deserialize_fields(data):  # If upgrade of format requested
            self.mark_for_upgrade()  # Flag for upgrade

    def check(self) -> str:
        """
        Method that will provide the "check" capability for the module.

        The return value that this method must provide is simply an string,
        preferable internacionalizated.

        Returns:
            Internacionalized (using gettext) string of result of the check.
        """
        return _("No check method provided.")

    def get_uuid(self) -> str:
        return self._uuid

    def set_uuid(self, uuid: typing.Optional[str]) -> None:
        self._uuid = uuid or ''

    def destroy(self) -> None:
        """
        Invoked before deleting an module from database.

        Do whatever needed here, as deleting associated data if needed
        (no example come to my head right now... :-) )

        Returns:
            Nothing
        """
        pass

    @abc.abstractmethod
    def db_obj(self) -> 'UUIDModel':
        """
        Returns the database object associated with this module.
        Can return "null()" if no database object is associated with this module.
        """
        ...

    def do_log(
        self,
        level: 'types.log.LogLevel',
        message: str,
        source: types.log.LogSource = types.log.LogSource.MODULE,
    ) -> None:
        """
        Logs a message at the level specified.

        Args:
            level: Level of the message
            message: Message to log
        """
        dbobj = self.db_obj()
        if dbobj.is_null():
            logger.error('Trying to log a message for a null object')
            return
        log.log(dbobj, level, message, source)

    @classmethod
    def mod_name(cls: type['Module']) -> str:
        """
        Returns "translated" type_name, using gettext for transforming
        cls.type_name

        Args:
            cls: This is a class method, so cls is the class

        Returns:
            Translated type name (using gettext)
        """
        return _(cls.type_name)

    @classmethod
    def mod_type(cls: type['Module']) -> str:
        """
        Returns type_type

        Args:
            cls: This is a class method, so cls is the class

        Returns:
            the type_type of this class (or derived class)
        """
        return cls.type_type

    @classmethod
    def description(cls: type['Module']) -> str:
        """
        This method returns the "translated" description, that is, using
        gettext for transforming cls.type_description.

        Args:
            cls: This is a class method, so cls is the class

        Returns:
            Translated description (using gettext)

        """
        return _(cls.type_description)

    @classmethod
    def icon(cls: type['Module']) -> bytes:
        """
        Reads the file specified by icon_file at module folder, and returns it content.
        This is used to obtain an icon so administration can represent it.

        Args:
            cls: Class

            inBase64: If true, the image will be returned as base 64 encoded

        Returns:
            Base 64 encoded or raw image, obtained from the specified file at
            'icon_file' class attribute
        """
        return utils.load_icon(
            os.path.dirname(typing.cast(str, sys.modules[cls.__module__].__file__)) + '/' + cls.icon_file
        )

    @classmethod
    def icon64(cls: type['Module']) -> str:
        return utils.load_icon_b64(
            os.path.dirname(typing.cast(str, sys.modules[cls.__module__].__file__)) + '/' + cls.icon_file
        )

    @staticmethod
    def test(env: 'Environment', data: 'types.core.ValuesType') -> 'types.core.TestResult':
        """
        Test if the connection data is ok.

        Returns an array, first value indicates "Ok" if true, "Bad" or "Error"
        if false. Second is a string describing operation

        Args:
            env: environment passed for testing (temporal environment passed)

            data: data passed for testing (data obtained from the form
            definition)

        Returns:
            Array of two elements, first is True of False, depending on test
            (True is all right, false is error),
            second is an String with error, preferably internacionalizated..
        """
        return types.core.TestResult(success=True, error=_("No connection checking method is implemented."))

    def __str__(self) -> str:
        return "Base Module"
