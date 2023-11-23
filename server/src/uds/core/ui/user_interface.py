# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2023 Virtual Cable S.L.U.
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
# pylint: disable=too-many-lines
import calendar
import codecs
import copy
import datetime
import inspect
import logging
import pickle  # nosec: safe usage
import re
import time
import typing
import collections.abc
import abc

from django.utils.translation import gettext as _

from uds.core import consts, exceptions, types
from uds.core.managers.crypto import UDSK, CryptoManager
from uds.core.util import serializer, validators, ensure
from uds.core.util.decorators import deprecatedClassValue

logger = logging.getLogger(__name__)

# Old encryption key
UDSB: typing.Final[bytes] = b'udsprotect'

SERIALIZATION_HEADER: typing.Final[bytes] = b'GUIZ'
SERIALIZATION_VERSION: typing.Final[bytes] = b'\001'


class gui:
    """
    This class contains the representations of fields needed by UDS modules and
    administation interface.

    This contains fields types, that modules uses to make a form and interact
    with users.

    The use of this provided fields are as follows:

    The Module is descendant of "BaseModule", which also is inherited from this
    class.

    At class level, we declare the fields needed to interact with the user, as
    this example:

    .. code-block:: python

       class AuthModule(Authenticator):
           # ...
           # Other initializations
           # ...
           users = gui.EditableList(label = 'Users', tooltip = 'Select users',
               order = 1, choices = ['user1', 'user2', 'user3', 'user4'])
           passw = gui.Password(label='Pass', length=32, tooltip='Password',
               order = 2, required = True, default = '12345')
           # ...
           # more fields
           # ...

    At class instantiation, this data is extracted and processed, so the admin
    can access this form to let users
    create new instances of this module.
    """

    # Values dict type
    ValuesType = typing.Optional[typing.Dict[str, str]]

    ValuesDictType = typing.Dict[
        str,
        typing.Union[
            str,
            bool,
            typing.List[str],
            types.ui.ChoiceItem,
        ],
    ]

    # Static Callbacks simple registry
    # Note that this works fine, even on several servers
    # cause the callbacks are registered on field creation, that is done
    # on clases at server startup, so all servers will have the same
    # callbacks registered
    callbacks: typing.ClassVar[
        typing.Dict[
            str,
            typing.Callable[[typing.Dict[str, str]], typing.List[typing.Dict[str, str]]],
        ]
    ] = {}

    @staticmethod
    def choiceItem(id_: typing.Union[str, int], text: typing.Union[str, int]) -> 'types.ui.ChoiceItem':
        """
        Helper method to create a single choice item.

        Args:
            id: Id of the choice to create

            text: Text to assign to the choice to create

        Returns:
            An dictionary, that is the representation of a single choice item,
            with 2 keys, 'id' and 'text'

        :note: Text can be anything, the method converts it first to text before
        assigning to dictionary
        """
        return {'id': str(id_), 'text': str(text)}

    # Helpers
    @staticmethod
    def convertToChoices(
        vals: typing.Union[
            typing.Callable[[], typing.List['types.ui.ChoiceItem']],
            typing.Iterable[typing.Union[str, types.ui.ChoiceItem]],
            typing.Dict[str, str],
            None,
        ]
    ) -> typing.Union[
        typing.Callable[[], typing.List['types.ui.ChoiceItem']], typing.List['types.ui.ChoiceItem']
    ]:
        """
        Helper to convert from array of strings (or dictionaries) to the same dict used in choice,
        multichoice, ..
        """
        if not vals:
            return []

        # If it's a callable, do not evaluate it, just return it
        if callable(vals):
            return vals

        # Helper to convert an item to a dict
        def choiceFromValue(val: typing.Union[str, int, types.ui.ChoiceItem]) -> 'types.ui.ChoiceItem':
            if isinstance(val, dict):
                if 'id' not in val or 'text' not in val:
                    raise ValueError(f'Invalid choice dict: {val}')
                return gui.choiceItem(val['id'], val['text'])
            # If val is not a dict, and it has not 'id' and 'text', raise an exception
            return gui.choiceItem(val, val)

        # If is a dict
        if isinstance(vals, collections.abc.Mapping):
            return [gui.choiceItem(str(k), v) for k, v in vals.items()]

        # if single value, convert to list
        if not isinstance(vals, collections.abc.Iterable) or isinstance(vals, str):
            vals = [vals]

        # If is an iterable
        if isinstance(vals, collections.abc.Iterable):
            return [choiceFromValue(v) for v in vals]

        # This should never happen
        raise ValueError(f'Invalid type for convertToChoices: {vals}')

    @staticmethod
    def choiceImage(id_: typing.Union[str, int], text: str, img: str) -> typing.Dict[str, str]:
        return {'id': str(id_), 'text': str(text), 'img': img}

    @staticmethod
    def sortedChoices(choices: typing.Iterable):
        return sorted(choices, key=lambda item: item['text'].lower())

    @staticmethod
    def toBool(value: typing.Union[str, bytes, bool, int]) -> bool:
        """
        Converts the string "true" (case insensitive) to True (boolean).
        Anything else is converted to false

        Args:
            str: Str to convert to boolean

        Returns:
            True if the string is "true" (case insensitive), False else.
        """
        return value in consts.BOOL_TRUE_VALUES

    @staticmethod
    def fromBool(bol: bool) -> str:
        """
        Converts a boolean to the string representation. True is converted to
        "true", False to "false". (gui.TRUE and gui.FALSE are the same)

        Args:
            bol: Boolean value (True or false) to convert

        Returns:
            "true" if bol evals to True, "false" if don't.
        """
        if bol:
            return consts.TRUE_STR
        return consts.FALSE_STR

    # Classes

    class InputField(abc.ABC):
        """
        Class representing an simple input field.
        This class is not directly usable, must be used by any inherited class
        (fields all of them)
        All fields are inherited from this one

        The data managed for an input field, and their default values are:
            * length: Max length of the field. Defaults to DEFAULT_LENGTH
            * required: If this field is a MUST. defaults to false
            * label: Label used with this field. Defaults to ''
            * dafault: Default value for the field. Defaults to '' (this is
              always an string)
            * readonly: If the field is read only on modification. On creation,
              all fields are "writable". Defaults to False
            * order: order inside the form, defaults to 0 (if two or more fields
              has same order, the output order may be anything)
            * tooltip: Tooltip used in the form, defaults to ''
            * type: type of the input field, defaults to "text box" (TextField)

        In every single field, you must at least indicate:
            * if required or not
            * order
            * label
            * tooltip
            * default  (if not included, will be ''). Alias for this field is defaultValue
            * readonly if can't be modified once it's created. Aliases for this field is readOnly

        Any other paremeter needed is indicated in the corresponding field class.

        Also a value field is available, so you can get/set the form field value.
        This property expects always an string, no matter what kind of field it is.

        Take into account also that "value" has precedence over "default",
        so if you use both, the used one will be "value". This is valid for
        all form fields. (Anyway, default is part of the "value" property, so
        if you use "value", you will get the default value if not set)
        """

        _fieldsInfo: types.ui.FieldInfo

        def __init__(self, label: str, type: types.ui.FieldType, **kwargs) -> None:
            # if defvalue or defaultValue or defValue in kwargs, emit a warning
            # with the new name (that is "default"), but use the old one
            for new_name, old_names in (
                ('default', ('defvalue', 'defaultValue', 'defValue')),
                ('readonly', ('rdonly, readOnly')),
            ):
                for i in old_names:
                    if i in kwargs:
                        try:
                            caller = inspect.stack()[
                                2
                            ]  # bypass this method and the caller (that is a derived class)
                        except IndexError:
                            caller = inspect.stack()[1]  # bypass only this method
                        logger.warning(
                            'Field %s: %s parameter is deprecated, use "%s" instead. Called from %s:%s',
                            label,
                            i,
                            new_name,
                            caller.filename,
                            caller.lineno,
                        )
                        kwargs[new_name] = kwargs[i]
                        break
            default = kwargs.get('default')
            # Length is not used on some kinds of fields, but present in all anyway
            # This property only affects in "modify" operations
            self._fieldsInfo = types.ui.FieldInfo(
                order=kwargs.get('order') or 0,
                label=label,
                tooltip=kwargs.get('tooltip') or '',
                type=type,
                length=kwargs.get('length'),
                required=kwargs.get('required'),
                default=default if not callable(default) else default,
                readonly=kwargs.get('readonly'),
                value=kwargs.get('value') if kwargs.get('value') is not None else default,
                tab=types.ui.Tab.fromStr(kwargs.get('tab')),
            )

        @property
        def type(self) -> 'types.ui.FieldType':
            return types.ui.FieldType(self._fieldsInfo.type)

        @type.setter
        def type(self, type_: 'types.ui.FieldType') -> None:
            """
            Sets the type of this field.

            Args:
                type: Type to set (from constants of this class)
            """
            self._fieldsInfo.type = type_

        def isType(self, *type_: types.ui.FieldType) -> bool:
            """
            Returns true if this field is of specified type
            """
            return self._fieldsInfo.type in type_

        def isSerializable(self) -> bool:
            return True

        def num(self) -> int:
            try:
                return int(self.value)
            except Exception:
                return -1

        def isTrue(self) -> bool:
            try:
                return gui.toBool(self.value)
            except Exception:
                return False

        @property
        def value(self) -> typing.Any:
            """
            Obtains the stored value.
            If the stored value is None (this will only happens if value is forced to be so, by default empty value is ''),
            returns default value instead.
            This is mainly used for hidden fields, so we have correctly initialized
            """
            if callable(self._fieldsInfo.value):
                return self._fieldsInfo.value()
            return self._fieldsInfo.value if self._fieldsInfo.value is not None else self.default

        @value.setter
        def value(self, value: typing.Any) -> None:
            """
            Stores new value (not the default one)
            """
            self._setValue(value)

        def _setValue(self, value: typing.Any) -> None:
            """
            So we can override value setter at descendants
            """
            self._fieldsInfo.value = value

        def guiDescription(self) -> typing.Dict[str, typing.Any]:
            """
            Returns the dictionary with the description of this item.
            We copy it, cause we need to translate the label and tooltip fields
            and don't want to
            alter original values.
            """
            data = typing.cast(dict, self._fieldsInfo.asDict())
            if 'value' in data:
                del data['value']  # We don't want to send value on guiDescription
            data['label'] = _(data['label']) if data['label'] else ''
            data['tooltip'] = _(data['tooltip']) if data['tooltip'] else ''
            if 'tab' in data:
                data['tab'] = _(data['tab'])  # Translates tab name
            data['default'] = self.default  # We need to translate default value
            return data

        @property
        def default(self) -> typing.Any:
            """
            Returns the default value for this field
            """
            defValue = self._fieldsInfo.default
            return defValue() if callable(defValue) else defValue

        @default.setter
        def default(self, value: typing.Any) -> None:
            self.setDefault(value)

        def setDefault(self, value: typing.Any) -> None:
            """
            Sets the default value of the field·

            Args:
                value: Default value (string)
            """
            self._fieldsInfo.default = value

        @property
        def label(self) -> str:
            return self._fieldsInfo.label

        @label.setter
        def label(self, value: str) -> None:
            self._fieldsInfo.label = value

        @property
        def required(self) -> bool:
            return self._fieldsInfo.required or False

        @required.setter
        def required(self, value: bool) -> None:
            self._fieldsInfo.required = value

        def validate(self) -> bool:
            """
            Validates the value of this field.

            Intended to be overriden by descendants
            """
            return True

        def __str__(self):
            return str(self.value)

        def __repr__(self):
            return f'{self.__class__.__name__}: {repr(self._fieldsInfo)}'

    class TextField(InputField):
        """
        This represents a text field.

        The values of parameters are inherited from :py:class:`InputField`

        Additionally to standard parameters, the length parameter is a
        recommended one for this kind of field.

        You can specify that this is a lines text box with **lines**
        parameter. If it exists, and is greater than 1, indicates how much
        lines will be used to display field. (Max number is 8)

        Example usage:

           .. code-block:: python

              # Declares an text form field, with label "Host", tooltip
              # "Host name for this module", that is required,
              # with max length of 64 chars and order = 1, and is editable
              # after creation.
              host = gui.TextField(length=64, label = _('Host'), order = 1,
                  tooltip = _('Host name for this module'), required = True)

              # Declares an text form field, with label "Other",
              # tooltip "Other info", that is not required, that is not
              # required and that is not editable after creation.
              other = gui.TextField(length=64, label = _('Other'), order = 1,
                  tooltip = _('Other info'), readonly = True)

        """

        def __init__(
            self,
            label: str,
            length: int = consts.system.DEFAULT_TEXT_LENGTH,
            readonly: bool = False,
            order: int = 0,
            tooltip: str = '',
            required: typing.Optional[bool] = None,
            tab: typing.Optional[typing.Union[str, types.ui.Tab]] = None,
            default: typing.Union[typing.Callable[[], str], str] = '',
            value: typing.Optional[str] = None,
            pattern: typing.Union[str, types.ui.FieldPatternType] = types.ui.FieldPatternType.NONE,
            lines: int = 0,
        ) -> None:
            super().__init__(
                label=label,
                length=length,
                readonly=readonly,
                order=order,
                tooltip=tooltip,
                required=required,
                tab=tab,
                default=default,
                value=value,
                type=types.ui.FieldType.TEXT,
            )
            self._fieldsInfo.lines = min(max(int(lines), 0), 8)
            # Pattern to validate the value
            # Can contain an regex or PatternType
            #   - 'ipv4'     # IPv4 address
            #   - 'ipv6'     # IPv6 address
            #   - 'ip'       # IPv4 or IPv6 address
            #   - 'mac'      # MAC address
            #   - 'url'      # URL
            #   - 'email'    # Email
            #   - 'fqdn'     # Fully qualified domain name
            #   - 'hostname' # Hostname (without domain)
            #   - 'host'     # Hostname with or without domain or IP address
            #   - 'path'     # Path (absolute or relative, Windows or Unix)
            # Note:
            #  Checks are performed on admin side, so they are not 100% reliable.
            if pattern:
                self._fieldsInfo.pattern = (
                    pattern
                    if isinstance(pattern, types.ui.FieldPatternType)
                    else types.ui.FieldPatternType(pattern)
                )

        def cleanStr(self):
            return str(self.value).strip()

        def validate(self) -> bool:
            return super().validate() and self._validatePattern()

        def _validatePattern(self) -> bool:
            pattern = self._fieldsInfo.pattern
            if isinstance(pattern, types.ui.FieldPatternType):
                try:
                    if pattern == types.ui.FieldPatternType.IPV4:
                        validators.validateIpv4(self.value)
                    elif pattern == types.ui.FieldPatternType.IPV6:
                        validators.validateIpv6(self.value)
                    elif pattern == types.ui.FieldPatternType.IP:
                        validators.validateIpv4OrIpv6(self.value)
                    elif pattern == types.ui.FieldPatternType.MAC:
                        validators.validateMac(self.value)
                    elif pattern == types.ui.FieldPatternType.URL:
                        validators.validateUrl(self.value)
                    elif pattern == types.ui.FieldPatternType.EMAIL:
                        validators.validateEmail(self.value)
                    elif pattern == types.ui.FieldPatternType.FQDN:
                        validators.validateFqdn(self.value)
                    elif pattern == types.ui.FieldPatternType.HOSTNAME:
                        validators.validateHostname(self.value)
                    elif pattern == types.ui.FieldPatternType.HOST:
                        try:
                            validators.validateHostname(self.value, allowDomain=True)
                        except exceptions.validation.ValidationError:
                            validators.validateIpv4OrIpv6(self.value)
                    elif pattern == types.ui.FieldPatternType.PATH:
                        validators.validatePath(self.value)
                    return True
                except exceptions.validation.ValidationError:
                    return False
            elif isinstance(pattern, str):
                # It's a regex
                return re.match(pattern, self.value) is not None
            return True  # No pattern, so it's valid

        def __str__(self):
            return str(self.value)

    class TextAutocompleteField(TextField):
        """
        This represents a text field that holds autocomplete values.
        Values are a list of strings...
        """

        def __init__(
            self,
            label: str,
            length: int = consts.system.DEFAULT_TEXT_LENGTH,
            readonly: bool = False,
            order: int = 0,
            tooltip: str = '',
            required: typing.Optional[bool] = None,
            tab: typing.Optional[typing.Union[str, types.ui.Tab]] = None,
            default: typing.Union[typing.Callable[[], str], str] = '',
            value: typing.Optional[str] = None,
            choices: typing.Union[
                typing.Callable[[], typing.List['types.ui.ChoiceItem']],
                typing.Iterable[typing.Union[str, types.ui.ChoiceItem]],
                typing.Dict[str, str],
                None,
            ] = None,
        ) -> None:
            super().__init__(
                label=label,
                length=length,
                readonly=readonly,
                order=order,
                tooltip=tooltip,
                required=required,
                tab=tab,
                default=default,
                value=value,
            )
            # Update parent type
            self.type = types.ui.FieldType.TEXT_AUTOCOMPLETE
            self._fieldsInfo.choices = gui.convertToChoices(choices or [])

        def setChoices(self, values: typing.Iterable[typing.Union[str, types.ui.ChoiceItem]]):
            """
            Set the values for this choice field
            """
            self._fieldsInfo.choices = gui.convertToChoices(values)

    class NumericField(InputField):
        """
        This represents a numeric field. It apears with an spin up/down button.

        The values of parameres are inherited from :py:class:`InputField`

        Additionally to standard parameters, the length parameter indicates the
        max number of digits (0-9 values).

        Example usage:

           .. code-block:: python

              # Declares an numeric form field, with max value of 99999, label
              # "Port", that is required,
              # with tooltip "Port (usually 443)" and order 1
              num = gui.NumericField(length=5, label = _('Port'),
                  default = '443', order = 1, tooltip = _('Port (usually 443)'),
                  minVAlue = 1024, maxValue = 65535,
                  required = True)
        """

        def __init__(
            self,
            label: str,
            length: typing.Optional[int] = None,
            readonly: bool = False,
            order: int = 0,
            tooltip: str = '',
            required: typing.Optional[bool] = None,
            tab: typing.Optional[typing.Union[str, types.ui.Tab]] = None,
            default: typing.Union[typing.Callable[[], int], int] = 0,
            value: typing.Optional[int] = None,
            minValue: typing.Optional[int] = None,
            maxValue: typing.Optional[int] = None,
        ) -> None:
            super().__init__(
                label=label,
                length=length,
                readonly=readonly,
                order=order,
                tooltip=tooltip,
                required=required,
                tab=tab,
                default=default,
                value=value,
                type=types.ui.FieldType.NUMERIC,
            )
            self._fieldsInfo.minValue = minValue
            self._fieldsInfo.maxValue = maxValue

        def _setValue(self, value: typing.Any):
            # Internally stores an string
            super()._setValue(value)

        def num(self) -> int:
            """
            Return value as integer
            """
            try:
                return int(self.value)
            except Exception:
                return 0

        @property
        def int_value(self) -> int:
            return self.num()

    class DateField(InputField):
        """
        This represents a date field.

        The values of parameres are inherited from :py:class:`InputField`
        """

        def __init__(
            self,
            label: str,
            length: typing.Optional[int] = None,
            readonly: bool = False,
            order: int = 0,
            tooltip: str = '',
            required: typing.Optional[bool] = None,
            tab: typing.Optional[typing.Union[str, types.ui.Tab]] = None,
            default: typing.Optional[typing.Union[typing.Callable[[], datetime.date], datetime.date]] = None,
            value: typing.Optional[typing.Union[str, datetime.date]] = None,
        ) -> None:
            super().__init__(
                label=label,
                length=length,
                readonly=readonly,
                order=order,
                tooltip=tooltip,
                required=required,
                tab=tab,
                default=default,
                value=value,
                type=types.ui.FieldType.DATE,
            )

        def as_date(self) -> datetime.date:
            """Alias for "value" property"""
            return typing.cast(datetime.date, self.value)

        def as_datetime(self) -> datetime.datetime:
            """Alias for "value" property, but as datetime.datetime"""
            # Convert date to datetime
            return datetime.datetime.combine(
                typing.cast(datetime.date, self.value), datetime.datetime.min.time()
            )

        def stamp(self) -> int:
            """Alias for "value" property, but as timestamp"""
            return int(time.mktime(datetime.datetime.strptime(self.value, '%Y-%m-%d').timetuple()))

        # Override value setter, so we can convert from datetime.datetime or str to datetime.date
        def _setValue(self, value: typing.Any) -> None:
            if isinstance(value, datetime.datetime):
                value = value.date()
            elif isinstance(value, datetime.date):
                value = value
            elif isinstance(value, str):  # YYYY-MM-DD
                value = datetime.datetime.strptime(value, '%Y-%m-%d').date()
            else:
                raise ValueError(f'Invalid value for date: {value}')

            super()._setValue(value)

        def guiDescription(self) -> typing.Dict[str, typing.Any]:
            theGui = super().guiDescription()
            # Convert if needed value and default to string (YYYY-MM-DD)
            if 'default' in theGui:
                theGui['default'] = str(theGui['default'])
            return theGui

        def __str__(self):
            return str(f'Datetime: {self.value}')

    class PasswordField(InputField):
        """
        This represents a password field. It appears with "*" at input, so the contents is not displayed

        The values of parameres are inherited from :py:class:`InputField`

        Additionally to standard parameters, the length parameter is a recommended one for this kind of field.

        Example usage:

           .. code-block:: python

              # Declares an text form field, with label "Password",
              # tooltip "Password of the user", that is required,
              # with max length of 32 chars and order = 2, and is
              # editable after creation.
              passw = gui.PasswordField(length=32, label = _('Password'),
                  order = 4, tooltip = _('Password of the user'),
                  required = True)

        """

        def __init__(
            self,
            label: str,
            length: int = consts.system.DEFAULT_TEXT_LENGTH,
            readonly: bool = False,
            order: int = 0,
            tooltip: str = '',
            required: typing.Optional[bool] = None,
            tab: typing.Optional[typing.Union[str, types.ui.Tab]] = None,
            default: typing.Union[typing.Callable[[], str], str] = '',
            value: typing.Optional[str] = None,
        ):
            super().__init__(
                label=label,
                length=length,
                readonly=readonly,
                order=order,
                tooltip=tooltip,
                required=required,
                tab=tab,
                default=default,
                value=value,
                type=types.ui.FieldType.PASSWORD,
            )

        def cleanStr(self):
            return str(self.value).strip()

        def __str__(self):
            return '********'

    class HiddenField(InputField):
        """
        This represents a hidden field. It is not displayed to the user. It use
        is for keeping info at form needed
        by module, but not editable by user (i.e., one service can keep info
        about the parent provider in hiddens)

        The values of parameres are inherited from :py:class:`InputField`

        These are almost the same as TextFields, but they do not get displayed
        for user interaction.

        Example usage:

           .. code-block:: python

              # Declares an empty hidden field
              hidden = gui.HiddenField()


           After that, at initGui method of module, we can store a value inside
           using value as shown here:

           .. code-block:: python

              def initGui(self):
                  # always set default using self, cause we only want to store
                  # value for current instance
                  self.hidden.value = self.parent().serialize()
                  # Note, you can use setDefault for legacy compat

        """

        _isSerializable: bool

        def __init__(
            self,
            label: str = '',  # label is optional on hidden fields
            order: int = 0,
            default: typing.Any = None,  # May be also callable
            value: typing.Any = None,
            serializable: bool = False,
        ) -> None:
            super().__init__(
                label=label,
                order=order,
                default=default,
                value=value,
                type=types.ui.FieldType.HIDDEN,
            )
            self._isSerializable = serializable

        def isSerializable(self) -> bool:
            return self._isSerializable
        
        def setDefault(self, value: typing.Any) -> None:
            """
            Sets the default value of the field. Overriden for HiddenField

            Args:
                value: Default value (string)
            """
            super().setDefault(value)
            self.value = value
        

    class CheckBoxField(InputField):
        """
        This represents a check box field, with values "true" and "false"

        The values of parameters are inherited from :py:class:`InputField`

        The valid values for this default are: "true" and "false" (as strings)

        Example usage:

           .. code-block:: python

              # Declares an check box field, with label "Use SSL", order 3,
              # tooltip "If checked, will use a ssl connection", default value
              # unchecked (not included, so it's empty, so it's not true :-))
              ssl = gui.CheckBoxField(label = _('Use SSL'), order = 3, tooltip = _('If checked, will use a ssl connection'))

        """

        def __init__(
            self,
            label: str,
            readonly: bool = False,
            order: int = 0,
            tooltip: str = '',
            required: typing.Optional[bool] = None,
            tab: typing.Optional[typing.Union[str, types.ui.Tab]] = None,
            default: typing.Union[typing.Callable[[], bool], bool] = False,
            value: typing.Optional[bool] = None,
        ):
            super().__init__(
                label=label,
                readonly=readonly,
                order=order,
                tooltip=tooltip,
                required=required,
                tab=tab,
                default=default,
                value=value,
                type=types.ui.FieldType.CHECKBOX,
            )

        def _setValue(self, value: typing.Union[str, bytes, bool]):
            """
            Override to set value to True or False (bool)
            """
            self._fieldsInfo.value = gui.toBool(value)

        def isTrue(self):
            """
            Checks that the value is true
            """
            return gui.toBool(self.value)

        def asBool(self) -> bool:
            """
            Returns the value as bool
            """
            return self.isTrue()

        def __str__(self):
            return str(self.isTrue())

    class ChoiceField(InputField):
        """
        This represents a simple combo box with single selection.

        The values of parameters are inherited from :py:class:`InputField`

        ChoiceField needs a function to provide values inside it.

        * We specify the values via "values" option this way:

           Example:

           .. code-block:: python

              choices = gui.ChoiceField(label="choices", choices=[ {'id':'1',
                  'text':'Text 1'}, {'id':'xxx', 'text':'Text 2'}])

           You can specify a multi valuated field via id-values, or a
           single-valued field via id-value

        * We can override choice values at UserInterface derived class
          constructor or initGui using setValues

        There is an extra option available for this kind of field:

           fills: This options is a dictionary that contains this fields:
              * 'callbackName' : Callback name for invocation via the specific
                 method xml-rpc. This name is a name we assign to this callback,
                 and is used to locate the method when callback is invoked from
                 admin interface.
              * 'function' : Function to execute.

                 This funtion receives one parameter, that is a dictionary with
                 all parameters (that, in time, are fields names) that we have
                 requested.

                 The expected return value for this callback is an array of
                 dictionaries with fields and values to set, as
                 example show below shows.
              * 'parameters' : Array of field names to pass back to server so
                 it can obtain the results.

                 Of course, this fields must be part of the module.

           Example:

            .. code-block:: python

               choice1 = gui.ChoiceField(label="Choice 1", values = ....,
                   fills = { 'target': 'choice2', 'callback': fncValues,
                       'parameters': ['choice1', 'name']}
                   )
               choice2 = gui.ChoiceField(label="Choice 2")

            Here is a more detailed explanation, using the VC service module as
            sample.

            .. code-block:: python

               class VCHelpers(object):
                   # ...
                   # other stuff
                   # ...
                   @staticmethod
                   def getMachines(parameters):
                       # ...initialization and other stuff...
                       if parameters['resourcePool'] != '':
                           # ... do stuff ...
                       data = [ { 'name' : 'machine', 'choices' : [{'id': 'xxxxxx', 'value': 'yyyy'}] } ]
                       return data

               class ModuleVC(services.Service)
                  # ...
                  # stuff
                  # ...
                  resourcePool = gui.ChoiceField(
                      label=_("Resource Pool"), readonly = False, order = 5,
                      fills = {
                          'callbackName' : 'vcFillMachinesFromResource',
                          'function' : VCHelpers.getMachines,
                          'parameters' : ['vc', 'ev', 'resourcePool']
                      },
                      tooltip = _('Resource Pool containing base machine'),
                      required = True
                  )

                  machine = gui.ChoiceField(label = _("Base Machine"), order = 6,
                      tooltip = _('Base machine for this service'), required = True )

                  vc = gui.HiddenField()
                  ev = gui.HiddenField() # ....

        """

        def __init__(
            self,
            label: str,
            readonly: bool = False,
            order: int = 0,
            tooltip: str = '',
            required: typing.Optional[bool] = None,
            choices: typing.Union[
                typing.Callable[[], typing.List['types.ui.ChoiceItem']],
                typing.Iterable[typing.Union[str, types.ui.ChoiceItem]],
                typing.Dict[str, str],
                None,
            ] = None,
            fills: typing.Optional[types.ui.Filler] = None,
            tab: typing.Optional[typing.Union[str, types.ui.Tab]] = None,
            default: typing.Union[typing.Callable[[], str], str, None] = None,
            value: typing.Optional[str] = None,
        ) -> None:
            super().__init__(
                label=label,
                readonly=readonly,
                order=order,
                tooltip=tooltip,
                required=required,
                tab=tab,
                default=default,
                value=value,
                type=types.ui.FieldType.CHOICE,
            )

            self._fieldsInfo.choices = gui.convertToChoices(choices or [])
            # if has fillers, set them
            if fills:
                if 'function' not in fills or 'callbackName' not in fills:
                    raise ValueError('Invalid fills parameters')
                fnc = fills['function']
                fills.pop('function')
                self._fieldsInfo.fills = fills
                # Store it only if not already present
                if fills['callbackName'] not in gui.callbacks:
                    gui.callbacks[fills['callbackName']] = fnc

        def setChoices(self, values: typing.Iterable[typing.Union[str, types.ui.ChoiceItem]]):
            """
            Set the values for this choice field
            """
            self._fieldsInfo.choices = gui.convertToChoices(values)

    class ImageChoiceField(InputField):
        def __init__(
            self,
            label: str,
            readonly: bool = False,
            order: int = 0,
            tooltip: str = '',
            required: typing.Optional[bool] = None,
            choices: typing.Union[
                typing.Callable[[], typing.List['types.ui.ChoiceItem']],
                typing.Iterable[typing.Union[str, types.ui.ChoiceItem]],
                typing.Dict[str, str],
                None,
            ] = None,
            tab: typing.Optional[typing.Union[str, types.ui.Tab]] = None,
            default: typing.Union[typing.Callable[[], str], str, None] = None,
            value: typing.Optional[str] = None,
        ):
            super().__init__(
                label=label,
                readonly=readonly,
                order=order,
                tooltip=tooltip,
                required=required,
                tab=tab,
                default=default,
                value=value,
                type=types.ui.FieldType.IMAGECHOICE,
            )

            self._fieldsInfo.choices = gui.convertToChoices(choices or [])

        def setChoices(self, values: typing.Iterable[typing.Union[str, types.ui.ChoiceItem]]):
            """
            Set the values for this choice field
            """
            self._fieldsInfo.choices = gui.convertToChoices(values)

    class MultiChoiceField(InputField):
        """
        Multichoices are list of items that are multi-selectable.

        There is a new parameter here, not covered by InputField:
            * 'rows' to tell gui how many rows to display (the length of the
              displayable list)

        "default"  is expresed as a comma separated list of ids

        This class do not have callback support, as ChoiceField does.

        The values is an array of dictionaries, in the form [ { 'id' : 'a',
        'text': b }, ... ]

        Example usage:

           .. code-block:: python

              # Declares a multiple choices field, with label "Datastores", that
              is editable, with 5 rows for displaying
              # data at most in user interface, 8th in order, that is required
              and has tooltip "Datastores where to put incrementals",
              # this field is required and has 2 selectable items: "datastore0"
              with id "0" and "datastore1" with id "1"
              datastores =  gui.MultiChoiceField(label = _("Datastores"),
                  readonly = False, rows = 5, order = 8,
                  tooltip = _('Datastores where to put incrementals'),
                  required = True,
                  choices = [ {'id': '0', 'text': 'datastore0' },
                      {'id': '1', 'text': 'datastore1' } ]
                  )
        """

        def __init__(
            self,
            label: str,
            readonly: bool = False,
            rows: typing.Optional[int] = None,
            order: int = 0,
            tooltip: str = '',
            required: typing.Optional[bool] = None,
            choices: typing.Union[
                typing.Callable[[], typing.List['types.ui.ChoiceItem']],
                typing.Iterable[typing.Union[str, types.ui.ChoiceItem]],
                typing.Dict[str, str],
                None,
            ] = None,
            tab: typing.Optional[typing.Union[str, types.ui.Tab]] = None,
            default: typing.Union[
                typing.Callable[[], str], typing.Callable[[], typing.List[str]], typing.List[str], str, None
            ] = None,
            value: typing.Optional[typing.Iterable[str]] = None,
        ):
            super().__init__(
                label=label,
                readonly=readonly,
                order=order,
                tooltip=tooltip,
                required=required,
                tab=tab,
                type=types.ui.FieldType.MULTICHOICE,
                default=default,
                value=value,
            )

            self._fieldsInfo.rows = rows
            self._fieldsInfo.choices = gui.convertToChoices(choices or [])

        def setChoices(self, choices: typing.Iterable[typing.Union[str, types.ui.ChoiceItem]]):
            """
            Set the values for this choice field
            """
            self._fieldsInfo.choices = gui.convertToChoices(choices)

    class EditableListField(InputField):
        """
        Editables list are lists of editable elements (i.e., a list of IPs, macs,
        names, etcc) treated as simple strings with no id

        The struct used to pass values is an array of strings, i.e. ['1', '2',
        'test', 'bebito', ...]

        This list don't have "selected" items, so its default field is simply
        ignored.

        We only nee to pass in "label" and, maybe, "values" to set default
        content for the list.

        Keep in mind that this is an user editable list, so the user can insert
        values and/or import values from files, so
        by default it will probably have no content at all.

        Example usage:

           .. code-block:: python

              #
              ipList = gui.EditableList(label=_('List of IPS'))

        """

        def __init__(
            self,
            label: str,
            readonly: bool = False,
            order: int = 0,
            tooltip: str = '',
            required: typing.Optional[bool] = None,
            tab: typing.Optional[typing.Union[str, types.ui.Tab]] = None,
            default: typing.Union[
                typing.Callable[[], str], typing.Callable[[], typing.List[str]], typing.List[str], str, None
            ] = None,
            value: typing.Optional[typing.Iterable[str]] = None,
        ) -> None:
            super().__init__(
                label=label,
                readonly=readonly,
                order=order,
                tooltip=tooltip,
                required=required,
                tab=tab,
                default=default,
                value=value,
                type=types.ui.FieldType.EDITABLELIST,
            )

        def _setValue(self, value):
            """
            So we can override value setting at descendants
            """
            super()._setValue(value)

    class InfoField(InputField):
        """
        Informational field (no input nor output)

        The current valid info fields are:
           title: 'name' = 'title', 'default' = 'real title'

        """

        def __init__(self, label: str, default: str) -> None:
            super().__init__(label=label, default=default, type=types.ui.FieldType.INFO)


class UserInterfaceType(type):
    """
    Metaclass definition for moving the user interface descriptions to a usable
    better place. This is done this way because we will "deepcopy" these fields
    later, and update references on class 'self' to the new copy. (so everyone has a different copy)
    """

    def __new__(
        mcs: typing.Type['UserInterfaceType'],
        classname: str,
        bases: typing.Tuple[type, ...],
        namespace: typing.Dict[str, typing.Any],
    ) -> 'UserInterfaceType':
        newClassDict = {}
        _gui: typing.MutableMapping[str, gui.InputField] = {}

        # Make a copy of gui fields description
        # (we will update references on class 'self' to the new copy)
        for attrName, attr in namespace.items():
            if isinstance(attr, gui.InputField):
                # Ensure we have a copy of the data, so we can modify it without affecting others
                attr._fieldsInfo = copy.deepcopy(attr._fieldsInfo)
                _gui[attrName] = attr

            newClassDict[attrName] = attr
        newClassDict['_base_gui'] = _gui
        return typing.cast('UserInterfaceType', type.__new__(mcs, classname, bases, newClassDict))


class UserInterface(metaclass=UserInterfaceType):
    """
    This class provides the management for gui descriptions (user forms)

    Once a class is derived from this one, that class can contain Field
    Descriptions,
    that will be managed correctly.

    By default, the values passed to this class constructor are used to fill
    the gui form fields values.
    """

    class ValidationFieldInfo(typing.NamedTuple):
        field: str
        error: str

    # Class variable that will hold the gui fields description
    _base_gui: typing.ClassVar[typing.Dict[str, gui.InputField]]

    # instance variable that will hold the gui fields description
    # this allows us to modify the gui fields values at runtime without affecting other instances
    _gui: typing.Dict[str, gui.InputField]

    def __init__(self, values: gui.ValuesType = None) -> None:
        # : If there is an array of elements to initialize, simply try to store
        # values on form fields.

        # Generate a deep copy of inherited Gui, so each User Interface instance
        # has its own "field" set, and do not share the "fielset" with others, what
        # can be really dangerous. Till now, nothing bad happened cause there where
        # being used "serialized", but this do not have to be this way

        # Ensure "gui" points to a copy of original gui, not the original one
        # this is done to avoid modifying the original gui description

        self._gui = copy.deepcopy(self._base_gui)

        # If a field has a callable on defined attributes(value, default, choices)
        # update the reference to the new copy
        for key, val in self._gui.items():  # And refresh self references to them
            setattr(self, key, val)  # Reference to self._gui[key]

            # Check for "callable" fields and update them if needed
            for field in ['choices', 'default']:  # Update references to self for callable fields
                attr = getattr(val._fieldsInfo, field, None)
                if attr and callable(attr):
                    # val is an InputField derived instance, so it is a reference to self._gui[key]
                    setattr(val._fieldsInfo, field, attr())

        if values is not None:
            for k, v in self._gui.items():
                if k in values:
                    v.value = values[k]
                else:
                    caller = inspect.stack()[1]
                    logger.warning('Field %s not found (invoked from %s:%s)', k, caller.filename, caller.lineno)

    def initGui(self) -> None:
        """
        This method gives the oportunity to initialize gui fields before they
        are send to administration client.
        We need this because at initialization time we probably don't have the
        data for gui.

        :note: This method is used as a "trick" to allow to modify default form
               data for services. Services are child of Service Providers, and
               will probably need data from Provider to fill initial form data.
               The rest of modules will not use this, and this only will be used
               when the user requests a new service or wants to modify existing
               one.
        :note: There is a drawback of this, and it is that there is that this
               method will modify service default data. It will run fast (probably),
               but may happen that two services of same type are requested at same
               time, and returned data will be probable a nonsense. We will take care
               of this posibility in a near version...
        """

    def valuesDict(self) -> gui.ValuesDictType:
        """
        Returns own data needed for user interaction as a dict of key-names ->
        values. The values returned must be strings.

        Example:
            we have 2 text field, first named "host" and second named "port",
            we can do something like this:

            .. code-block:: python

               return { 'host' : self.host, 'port' : self.port }

            (Just the reverse of :py:meth:`.__init__`, __init__ receives this
            dict, valuesDict must return the dict)

        Names must coincide with fields declared.

        Returns:
             Dictionary, associated with declared fields.
             Default implementation returns the values stored at the gui form
             fields declared.

        :note: By default, the provided method returns the correct values
               extracted from form fields

        """
        dic: gui.ValuesDictType = {}
        for k, v in self._gui.items():
            if v.isType(types.ui.FieldType.EDITABLELIST, types.ui.FieldType.MULTICHOICE):
                dic[k] = ensure.is_list(v.value)
            else:
                dic[k] = v.value
        logger.debug('Values Dict: %s', dic)
        return dic

    def serializeForm(
        self,
        opt_serializer: typing.Optional[typing.Callable[[typing.Any], bytes]] = None,
    ) -> bytes:
        """New form serialization

        Returns:
            bytes -- serialized form (zipped)
        """

        def serialize(value: typing.Any) -> bytes:
            if opt_serializer:
                return opt_serializer(value)
            return serializer.serialize(value)

        fw_converters: typing.Mapping[
            types.ui.FieldType, typing.Callable[[gui.InputField], typing.Optional[str]]
        ] = {
            types.ui.FieldType.TEXT: lambda x: x.value,
            types.ui.FieldType.TEXT_AUTOCOMPLETE: lambda x: x.value,
            types.ui.FieldType.NUMERIC: lambda x: str(int(x.num())),
            types.ui.FieldType.PASSWORD: lambda x: (
                CryptoManager().AESCrypt(x.value.encode('utf8'), UDSK, True).decode()
            ),
            types.ui.FieldType.HIDDEN: (lambda x: None if not x.isSerializable() else x.value),
            types.ui.FieldType.CHOICE: lambda x: x.value,
            types.ui.FieldType.MULTICHOICE: lambda x: codecs.encode(serialize(x.value), 'base64').decode(),
            types.ui.FieldType.EDITABLELIST: lambda x: codecs.encode(serialize(x.value), 'base64').decode(),
            types.ui.FieldType.CHECKBOX: lambda x: consts.TRUE_STR if x.isTrue() else consts.FALSE_STR,
            types.ui.FieldType.IMAGECHOICE: lambda x: x.value,
            types.ui.FieldType.DATE: lambda x: x.value,
            types.ui.FieldType.INFO: lambda x: None,
        }
        # Any unexpected type will raise an exception
        arr = [
            (k, v.type.name, fw_converters[v.type](v))
            for k, v in self._gui.items()
            if fw_converters[v.type](v) is not None
        ]

        return SERIALIZATION_HEADER + SERIALIZATION_VERSION + serialize(arr)

    def deserializeForm(
        self,
        values: bytes,
        opt_deserializer: typing.Optional[typing.Callable[[bytes], typing.Any]] = None,
    ) -> None:
        """New form unserialization

        Arguments:
            values {bytes} -- serialized form (zipped)

        Keyword Arguments:
            serializer {typing.Optional[typing.Callable[[str], typing.Any]]} -- deserializer (default: {None})
        """

        def deserialize(value: bytes) -> typing.Any:
            if opt_deserializer:
                return opt_deserializer(value)
            return serializer.deserialize(value) or []

        if not values:
            return

        if not values.startswith(SERIALIZATION_HEADER):
            # Unserialize with old method
            self.oldDeserializeForm(values)
            return

        # For future use, right now we only have one version
        version = values[  # pylint: disable=unused-variable
            len(SERIALIZATION_HEADER) : len(SERIALIZATION_HEADER) + len(SERIALIZATION_VERSION)
        ]

        values = values[len(SERIALIZATION_HEADER) + len(SERIALIZATION_VERSION) :]

        if not values:
            return

        arr = deserialize(values)

        # Set all values to defaults ones
        for k in self._gui:
            if self._gui[k].isType(types.ui.FieldType.HIDDEN) and self._gui[k].isSerializable() is False:
                # logger.debug('Field {0} is not unserializable'.format(k))
                continue
            self._gui[k].value = self._gui[k].default

        converters: typing.Mapping[types.ui.FieldType, typing.Callable[[str], typing.Any]] = {
            types.ui.FieldType.TEXT: lambda x: x,
            types.ui.FieldType.TEXT_AUTOCOMPLETE: lambda x: x,
            types.ui.FieldType.NUMERIC: int,
            types.ui.FieldType.PASSWORD: lambda x: (
                CryptoManager().AESDecrypt(x.encode(), UDSK, True).decode()
            ),
            types.ui.FieldType.HIDDEN: lambda x: None,
            types.ui.FieldType.CHOICE: lambda x: x,
            types.ui.FieldType.MULTICHOICE: lambda x: deserialize(codecs.decode(x.encode(), 'base64')),
            types.ui.FieldType.EDITABLELIST: lambda x: deserialize(codecs.decode(x.encode(), 'base64')),
            types.ui.FieldType.CHECKBOX: lambda x: x,
            types.ui.FieldType.IMAGECHOICE: lambda x: x,
            types.ui.FieldType.DATE: lambda x: x,
            types.ui.FieldType.INFO: lambda x: None,
        }

        for k, t, v in arr:
            if k not in self._gui:
                logger.warning('Field %s not found in form', k)
                continue
            field_type = self._gui[k].type
            if field_type not in converters:
                logger.warning('Field %s has no converter', k)
                continue
            if t != field_type.name:
                logger.warning('Field %s has different type than expected', k)
                continue
            self._gui[k].value = converters[field_type](v)

    def oldDeserializeForm(self, values: bytes) -> None:
        """
        This method deserializes the values previously obtained using
        :py:meth:`serializeForm`, and stores
        the valid values form form fileds inside its corresponding field
        """
        # Separators for fields, old implementation
        MULTIVALUE_FIELD: typing.Final[bytes] = b'\001'
        OLD_PASSWORD_FIELD: typing.Final[bytes] = b'\004'
        PASSWORD_FIELD: typing.Final[bytes] = b'\005'

        FIELD_SEPARATOR: typing.Final[bytes] = b'\002'
        NAME_VALUE_SEPARATOR: typing.Final[bytes] = b'\003'

        if not values:  # Has nothing
            return

        try:
            # Set all values to defaults ones
            for k in self._gui:
                if self._gui[k].isType(types.ui.FieldType.HIDDEN) and self._gui[k].isSerializable() is False:
                    # logger.debug('Field {0} is not unserializable'.format(k))
                    continue
                self._gui[k].value = self._gui[k].default

            values = codecs.decode(values, 'zip')
            if not values:  # Has nothing
                return

            for txt in values.split(FIELD_SEPARATOR):
                kb, v = txt.split(NAME_VALUE_SEPARATOR)
                k = kb.decode('utf8')  # Convert name to string
                if k in self._gui:
                    try:
                        if v.startswith(MULTIVALUE_FIELD):
                            val = pickle.loads(  # nosec: safe pickle, controlled
                                v[1:]
                            )  # nosec: secure pickled by us for sure
                        elif v.startswith(OLD_PASSWORD_FIELD):
                            val = CryptoManager().AESDecrypt(v[1:], UDSB, True).decode()
                        elif v.startswith(PASSWORD_FIELD):
                            val = CryptoManager().AESDecrypt(v[1:], UDSK, True).decode()
                        else:
                            val = v
                            # Ensure "legacy bytes" values are loaded correctly as unicode
                            if isinstance(val, bytes):
                                val = val.decode('utf8')
                    except Exception:
                        logger.exception('Pickling %s from %s', k, self)
                        val = ''
                    self._gui[k].value = val
                # logger.debug('Value for {0}:{1}'.format(k, val))
        except Exception:
            logger.exception('Exception on unserialization on %s', self.__class__)
            # Values can contain invalid characters, so we log every single char
            # logger.info('Invalid serialization data on {0} {1}'.format(self, values.encode('hex')))

    def guiDescription(self) -> typing.List[typing.MutableMapping[str, typing.Any]]:
        """
        This simple method generates the theGui description needed by the
        administration client, so it can
        represent it at user interface and manage it.

        Args:
            obj: If any, object that will get its "initGui" invoked
                    This will only happen (not to be None) in Services.
        """
        self.initGui()  # We give the "oportunity" to fill necesary theGui data before providing it to client

        res: typing.List[typing.MutableMapping[str, typing.Any]] = []
        for key, val in self._gui.items():
            # Only add "value" for hidden fields on gui description. Rest of fields will be filled by client
            res.append({'name': key, 'gui': val.guiDescription(), 'value': val.value if val.isType(types.ui.FieldType.HIDDEN) else None })
        # logger.debug('theGui description: %s', res)
        return res

    def errors(self) -> typing.List[ValidationFieldInfo]:
        found_errors: typing.List[UserInterface.ValidationFieldInfo] = []
        for key, val in self._gui.items():
            if val.required and not val.value:
                found_errors.append(UserInterface.ValidationFieldInfo(key, 'Field is required'))
            if not val.validate():
                found_errors.append(UserInterface.ValidationFieldInfo(key, 'Field is not valid'))

        return found_errors
