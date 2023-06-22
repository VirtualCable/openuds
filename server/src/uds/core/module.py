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
import sys
import os.path
import codecs
import logging
import typing


from django.utils.translation import gettext as _

from uds.core.ui.user_interface import UserInterface

from .serializable import Serializable
from .environment import Environment, Environmentable

logger = logging.getLogger(__name__)


class Module(UserInterface, Environmentable, Serializable):
    """
    Base class for all modules used by UDS.
    This base module provides all the needed methods that modules must implement

    All modules must, at least, implement the following:

    * Attributes:
       * :py:attr:`.typeName`:
         Name for this type of module (human readable) to assign to the module (string)
         This name will be used to let the administrator identify this module.
       * :py:attr:`.typeType`:
         Name for this type of module (machine only) to assing to the module (string)
         This name will be used internally to identify when a serialized module corresponds with this class.
       * :py:attr:`.typeDescription`:
         Description for this type of module.
         This descriptio will be used to let the administrator identify what this module provides
       * :py:attr:`.iconFile`: This is an icon file, in png format, used at administration client to identify this module.
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
       * :py:meth:`from from uds.core.ui.valuesDict`
         This method, by default, provides the values contained in the form fields. If you don't override the marshal and
         unmarshal, this method should be fine as is for you also.


    Environmentable is a base class that provides utility method to access a separate Environment for every single
    module.
    """

    __slots__ = ['_uuid']
    # Import variable indicating this module is a base class not a real module
    # Note that Module is not a real module, but a base class for all modules so isBase is not used on this class
    isBase: typing.ClassVar[bool] = False

    # Types
    ValuesType = typing.Optional[
        typing.Dict[str, typing.Any]
    ]  # values type value will be str or list[str] int most cases

    # : Which coded to use to encode module by default.
    # : Basic name used to provide the administrator an "huma readable" form for the module
    typeName: typing.ClassVar[str] = 'Base Module'
    # : Internal type name, used by system to locate this module
    typeType: typing.ClassVar[str] = 'BaseModule'
    # : Description of this module, used at admin level
    typeDescription: typing.ClassVar[str] = 'Base Module'
    # : Icon file, relative to module folders
    iconFile: typing.ClassVar[
        str
    ] = 'base.png'  # This is expected to be png, use this format always

    # Not defined, but declared. If module is groupable, this value will contain to which group belongs
    group: typing.ClassVar[str]

    @classmethod
    def name(cls: typing.Type['Module']) -> str:
        """
        Returns "translated" typeName, using gettext for transforming
        cls.typeName

        Args:
            cls: This is a class method, so cls is the class

        Returns:
            Translated type name (using gettext)
        """
        return _(cls.typeName)

    @classmethod
    def type(cls: typing.Type['Module']) -> str:
        """
        Returns typeType

        Args:
            cls: This is a class method, so cls is the class

        Returns:
            the typeType of this class (or derived class)
        """
        return cls.typeType

    @classmethod
    def description(cls: typing.Type['Module']) -> str:
        """
        This method returns the "translated" description, that is, using
        gettext for transforming cls.typeDescription.

        Args:
            cls: This is a class method, so cls is the class

        Returns:
            Translated description (using gettext)

        """
        return _(cls.typeDescription)

    @classmethod
    def icon(cls: typing.Type['Module']) -> bytes:
        """
        Reads the file specified by iconFile at module folder, and returns it content.
        This is used to obtain an icon so administration can represent it.

        Args:
            cls: Class

            inBase64: If true, the image will be returned as base 64 encoded

        Returns:
            Base 64 encoded or raw image, obtained from the specified file at
            'iconFile' class attribute
        """
        try:
            with open(
                os.path.dirname(typing.cast(str, sys.modules[cls.__module__].__file__))
                + '/'
                + cls.iconFile,
                'rb',
            ) as f:
                data = f.read()
        except Exception as e:
            logger.error('Error reading icon file for module %s: %s', cls.type(), e)
            # blank png bytes
            data = codecs.decode(
                (
                    b'iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAAY0lEQVR42u3QAREAAAQEMJKL'
                    b'/nI4W4R1KlOPtQABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAg'
                    b'AABAgQIECBAgAABAgQIECBAgAABAgQIEHDfAvLdn4FABR1mAAAAAElFTkSuQmCC'
                ),
                'base64',
            )

        return data

    @classmethod
    def icon64(cls: typing.Type['Module']) -> str:
        return codecs.encode(cls.icon(), 'base64').decode()

    @staticmethod
    def test(env: Environment, data: typing.Dict[str, str]) -> typing.List[typing.Any]:  # pylint: disable=unused-argument
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
        return [True, _("No connection checking method is implemented.")]

    def __init__(
        self,
        environment: Environment,
        values: ValuesType = None,
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
        valuesDict, you must also take account of values (dict) provided at the
        __init__ method of your class.
        """
        UserInterface.__init__(self, values)
        Environmentable.__init__(self, environment)
        Serializable.__init__(self)
        self._uuid = uuid or ''

    def __str__(self):
        return "Base Module"

    def isDirty(self) -> bool:
        """
        This method informs the core if the module has changed serializable data,
        and that must be re-serialized

        Default implemetation is that on every method call, module will be dirty

        Note: The implementation of this is a work in progress, so right now the module will be serialized out on every access
        """
        return True

    def marshal(self) -> bytes:
        """
        By default and if not overriden by descendants, this method, overridden
        from Serializable, and returns the serialization of
        form field stored values.
        """
        return self.serializeForm()

    def unmarshal(self, data: bytes) -> None:
        """
        By default and if not overriden by descendants, this method recovers
        data serialized using serializeForm
        """
        self.deserializeForm(data)

    def check(self) -> str:
        """
        Method that will provide the "check" capability for the module.

        The return value that this method must provide is simply an string,
        preferable internacionalizated.

        Returns:
            Internacionalized (using gettext) string of result of the check.
        """
        return _("No check method provided.")

    def getUuid(self) -> str:
        return self._uuid

    def setUuid(self, uuid: typing.Optional[str]) -> None:
        self._uuid = uuid or ''

    def destroy(self) -> None:
        """
        Invoked before deleting an module from database.

        Do whatever needed here, as deleting associated data if needed
        (no example come to my head right now... :-) )

        Returns:
            Nothing
        """
