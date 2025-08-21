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
import base64
import codecs
import copy
import datetime
import inspect
import itertools
import logging
import pickle  # nosec: safe usage
import re
import time
import typing
import collections.abc
import abc

from django.conf import settings
from django.utils.translation import gettext
from django.utils.functional import Promise  # To recognize lazy translations


from uds.core import consts, exceptions, types
from uds.core.managers.crypto import UDSK, CryptoManager
from uds.core.util import modfinder, serializer, validators, ensure

logger = logging.getLogger(__name__)

# To simplify choice parameters declaration of fields
_ChoicesParamType: typing.TypeAlias = typing.Union[
    collections.abc.Callable[[], list['types.ui.ChoiceItem']],
    collections.abc.Iterable[str | types.ui.ChoiceItem],
    dict[str, str],
    None,
]


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
    ValuesType = typing.Optional[dict[str, str]]

    ValuesDictType = dict[
        str,
        typing.Union[
            str,
            int,
            bool,
            list[str],
            types.ui.ChoiceItem,
        ],
    ]

    # Static Callbacks simple registry
    # Note that this works fine, even on several servers
    # cause the callbacks are registered on field creation, that is done
    # on clases at server startup, so all servers will have the same
    # callbacks registered
    callbacks: typing.ClassVar[
        dict[
            str,
            collections.abc.Callable[[dict[str, str]], list[types.ui.CallbackResultItem]],
        ]
    ] = {}

    @staticmethod
    def choice_item(id_: 'str|int', text: 'str|Promise|typing.Any') -> 'types.ui.ChoiceItem':
        """
        Helper method to create a single choice item.
        """
        if not isinstance(text, (str, Promise)):
            text = str(text)
        return {
            'id': str(id_),
            'text': typing.cast(str, text),
        }  # Cast to avoid mypy error, Promise is at all effects a str

    @staticmethod
    def choice_image(id_: typing.Union[str, int], text: str, img: str) -> types.ui.ChoiceItem:
        """
        Helper method to create a single choice item with image.
        """
        return {'id': str(id_), 'text': str(text), 'img': img}

    # Helpers
    @staticmethod
    def as_choices(
        vals: _ChoicesParamType,
    ) -> typing.Union[collections.abc.Callable[[], list['types.ui.ChoiceItem']], list['types.ui.ChoiceItem']]:
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
        def _choice_from_value(val: typing.Union[str, types.ui.ChoiceItem]) -> 'types.ui.ChoiceItem':
            if isinstance(val, dict):
                if 'id' not in val or 'text' not in val:
                    raise ValueError(f'Invalid choice dict: {val}')
                return gui.choice_item(val['id'], val['text'])
            # If val is not a dict, and it has not 'id' and 'text', raise an exception
            return gui.choice_item(val, str(val))

        # If is a dict
        if isinstance(vals, dict):
            return [gui.choice_item(str(k), v) for k, v in typing.cast(dict[str, str], vals).items()]

        if isinstance(vals, str):
            return [gui.choice_item(vals, vals)]

        # Vals is an iterable, so we convert it to a list of choice items
        return [_choice_from_value(v) for v in vals]

    @staticmethod
    def sorted_choices(
        choices: collections.abc.Iterable[types.ui.ChoiceItem],
        *,
        by_id: bool = False,
        reverse: bool = False,
        key: typing.Optional[collections.abc.Callable[[types.ui.ChoiceItem], typing.Any]] = None,
    ) -> list[types.ui.ChoiceItem]:
        if by_id:
            key = lambda item: item['id']
        elif key is None:
            key = lambda item: item['text'].lower()
        else:
            key = key
        return sorted(choices, key=key, reverse=reverse)

    @staticmethod
    def as_bool(value: typing.Union[str, bytes, bool, int]) -> bool:
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
    def bool_as_str(bol: bool) -> str:
        """
        Converts a boolean to the string representation. True is converted to
        "true", False to "false". (gui.TRUE and gui.FALSE are the same)

        Args:
            bol: Boolean value (True or false) to convert

        Returns:
            "true" if bol evals to True, "false" if don't.
        """
        return consts.TRUE_STR if bol else consts.FALSE_STR

    @staticmethod
    def as_int(value: typing.Union[str, bytes, bool, int], default: int = 0) -> int:
        """
        Converts the string "true" (case insensitive) to True (boolean).
        Anything else is converted to false

        Args:
            str: Str to convert to boolean

        Returns:
            True if the string is "true" (case insensitive), False else.
        """
        try:
            return int(value)
        except Exception:
            return default

    @staticmethod
    def as_str(value: typing.Any) -> str:
        """
        Converts the value to string.
        """
        return str(value)

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
            * default  (if not included, will be None).
            * readonly if can't be modified once it's created. Aliases for this field is read only

        Any other paremeter needed is indicated in the corresponding field class.

        Also a value field is available, so you can get/set the form field value.
        This property expects always an string, no matter what kind of field it is.

        Take into account also that "value" has precedence over "default",
        so if you use both, the used one will be "value". This is valid for
        all form fields. (Anyway, default is part of the "value" property, so
        if you use "value", you will get the default value if not set)

        Note:
            Currently, old field name is only intended for 4.0 migration, so it has only one value.
            This means that only one rename can be done currently. If needed, we can add a list of old names
            in a future version. (str|list[str]|None instead of str|None)
        """

        _field_info: types.ui.FieldInfo

        def __init__(
            self,
            label: str,
            type: types.ui.FieldType,
            old_field_name: types.ui.OldFieldNameType,
            order: int = 0,
            tooltip: str = '',
            length: typing.Optional[int] = None,
            required: typing.Optional[bool] = None,
            default: typing.Union[collections.abc.Callable[[], typing.Any], typing.Any] = None,
            readonly: typing.Optional[bool] = None,
            value: typing.Any = None,
            tab: typing.Optional[typing.Union[str, types.ui.Tab]] = None,
            **kwargs: typing.Any,
        ) -> None:
            # Length is not used on some kinds of fields, but present in all anyway
            # This property only affects in "modify" operations
            self._field_info = types.ui.FieldInfo(
                old_field_name=old_field_name,
                order=order,
                label=label,
                tooltip=tooltip,
                type=type,
                length=length if length is not None else consts.system.DEFAULT_TEXT_LENGTH,
                required=required,
                default=default,
                readonly=readonly,
                value=value,
                tab=tab,
            )

        @property
        def field_name(self) -> str:
            """
            Returns the name of the field
            """
            return self._field_info.field_name

        @property
        def field_type(self) -> 'types.ui.FieldType':
            return types.ui.FieldType(self._field_info.type)

        @field_type.setter
        def field_type(self, type_: 'types.ui.FieldType') -> None:
            """
            Sets the type of this field.

            Args:
                type: Type to set (from constants of this class)
            """
            self._field_info.type = type_

        def is_type(self, *type_: types.ui.FieldType) -> bool:
            """
            Returns true if this field is of specified type
            """
            return self._field_info.type in type_

        def is_serializable(self) -> bool:
            return True

        def old_field_name(self) -> list[str]:
            """
            Returns the name of the field
            """
            if isinstance(self._field_info.old_field_name, list):
                return self._field_info.old_field_name
            return [self._field_info.old_field_name] if self._field_info.old_field_name else []

        @property
        def value(self) -> typing.Any:
            """
            Obtains the stored value.
            If the stored value is None (this will only happens if value is forced to be so, by default empty value is ''),
            returns default value instead.
            This is mainly used for hidden fields, so we have correctly initialized
            """
            if callable(self._field_info.value):
                return self._field_info.value()
            return self._field_info.value if self._field_info.value is not None else self.default

        @value.setter
        def value(self, value: typing.Any) -> None:
            """
            Stores new value (not the default one)
            """
            self._set_value(value)

        def _set_value(self, value: typing.Any) -> None:
            """
            So we can override value setter at descendants
            """
            self._field_info.value = value

        def gui_description(self) -> types.ui.GuiDescription:
            """
            Returns the dictionary with the description of this item.
            We copy it, cause we need to translate the label and tooltip fields
            and don't want to
            alter original values.
            """
            data = self._field_info.as_dict()
            for i in ('value', 'old_field_name'):
                if i in data:
                    del data[i]  # We don't want to send some values on gui_description
            # Translate label and tooltip
            data['label'] = gettext(data['label']) if data['label'] else ''
            data['tooltip'] = gettext(data['tooltip']) if data['tooltip'] else ''

            # And, if tab is set, translate it too
            if 'tab' in data:
                data['tab'] = gettext(data['tab'])  # Translates tab name

            data['default'] = self.default

            return typing.cast(types.ui.GuiDescription, data)

        @property
        def default(self) -> typing.Any:
            """
            Returns the default value for this field
            """
            default_value = self._field_info.default
            return default_value() if callable(default_value) else default_value

        @default.setter
        def default(self, value: typing.Any) -> None:
            self.set_default(value)

        def set_default(self, value: typing.Any) -> None:
            """
            Sets the default value of the field·

            Args:
                value: Default value (string)
            """
            self._field_info.default = value

        @property
        def label(self) -> str:
            return self._field_info.label

        @label.setter
        def label(self, value: str) -> None:
            self._field_info.label = value

        @property
        def required(self) -> bool:
            return self._field_info.required or False

        @required.setter
        def required(self, value: bool) -> None:
            self._field_info.required = value

        def validate(self) -> bool:
            """
            Validates the value of this field.

            Intended to be overriden by descendants
            """
            return True

        def as_int(self) -> int:
            """
            Return value as integer
            """
            return gui.as_int(self.value)

        def as_str(self) -> str:
            """
            Return value as string
            """
            return gui.as_str(self.value)

        def as_clean_str(self) -> str:
            return self.as_str().strip()

        def as_bool(self) -> bool:
            """
            Checks that the value is true
            """
            return gui.as_bool(self.value)

        def __repr__(self) -> str:
            return f'{self.__class__.__name__}: {repr(self._field_info)}'

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
            default: typing.Union[collections.abc.Callable[[], str], str] = '',
            value: typing.Optional[str] = None,
            pattern: typing.Union[str, types.ui.FieldPatternType] = types.ui.FieldPatternType.NONE,
            lines: int = 0,
            old_field_name: types.ui.OldFieldNameType = None,
        ) -> None:
            super().__init__(
                old_field_name=old_field_name,
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
            self._field_info.lines = min(max(int(lines), 0), 8)
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
                self._field_info.pattern = (
                    pattern
                    if isinstance(pattern, types.ui.FieldPatternType)
                    else types.ui.FieldPatternType(pattern)
                )

        def validate(self) -> bool:
            return super().validate() and self._validate_pattern()

        def _validate_pattern(self) -> bool:
            pattern = self._field_info.pattern
            if isinstance(pattern, types.ui.FieldPatternType):
                try:
                    match pattern:
                        case types.ui.FieldPatternType.NONE:
                            return True
                        case types.ui.FieldPatternType.IPV4:
                            validators.validate_ipv4(self.value)
                        case types.ui.FieldPatternType.IPV6:
                            validators.validate_ipv6(self.value)
                        case types.ui.FieldPatternType.IP:
                            validators.validate_ip(self.value)
                        case types.ui.FieldPatternType.MAC:
                            validators.validate_mac(self.value)
                        case types.ui.FieldPatternType.URL:
                            validators.validate_url(self.value)
                        case types.ui.FieldPatternType.EMAIL:
                            validators.validate_email(self.value)
                        case types.ui.FieldPatternType.FQDN:
                            validators.validate_fqdn(self.value)
                        case types.ui.FieldPatternType.HOSTNAME:
                            validators.validate_hostname(self.value)
                        case types.ui.FieldPatternType.HOST:
                            try:
                                validators.validate_hostname(self.value, allow_domain=True)
                            except exceptions.ui.ValidationError:
                                validators.validate_ip(self.value)
                        case types.ui.FieldPatternType.PATH:
                            validators.validate_path(self.value)
                except exceptions.ui.ValidationError:
                    return False
            else:
                assert isinstance(pattern, str)
                # It's a regex
                return re.match(pattern, self.value) is not None
            return True  # No pattern, so it's valid

        @property
        def value(self) -> str:
            return gui.as_str(super().value)

        @value.setter
        def value(self, value: str) -> None:
            super()._set_value(value)

        def _set_value(self, value: typing.Any) -> None:
            """
            To ensure value is an str
            """
            super()._set_value(gui.as_str(value))

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
            default: typing.Union[collections.abc.Callable[[], str], str] = '',
            value: typing.Optional[str] = None,
            choices: _ChoicesParamType = None,
            old_field_name: types.ui.OldFieldNameType = None,
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
                old_field_name=old_field_name,
            )
            # Update parent type
            self.field_type = types.ui.FieldType.TEXT_AUTOCOMPLETE
            self._field_info.choices = gui.as_choices(choices or [])

        def set_choices(self, values: collections.abc.Iterable[typing.Union[str, types.ui.ChoiceItem]]) -> None:
            """
            Set the values for this choice field
            """
            self._field_info.choices = gui.as_choices(values)

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
                  min_value = 1024, max_value = 65535,
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
            default: typing.Union[collections.abc.Callable[[], int], int] = 0,
            value: typing.Optional[int] = None,
            min_value: typing.Optional[int] = None,
            max_value: typing.Optional[int] = None,
            old_field_name: types.ui.OldFieldNameType = None,
        ) -> None:
            super().__init__(
                old_field_name=old_field_name,
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
            self._field_info.min_value = min_value
            self._field_info.max_value = max_value

        def _set_value(self, value: typing.Any) -> None:
            """
            To ensure value is an int
            """
            super()._set_value(gui.as_int(value))

        @property
        def value(self) -> int:
            return gui.as_int(super().value)

        @value.setter
        def value(self, value: int) -> None:
            self._set_value(value)

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
            default: typing.Optional[
                typing.Union[collections.abc.Callable[[], datetime.date], datetime.date]
            ] = None,
            value: typing.Optional[typing.Union[str, datetime.date]] = None,
            old_field_name: types.ui.OldFieldNameType = None,
        ) -> None:
            super().__init__(
                old_field_name=old_field_name,
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
            return typing.cast(datetime.date, super().value)

        def as_datetime(self) -> datetime.datetime:
            """Alias for "value" property, but as datetime.datetime"""
            # Convert date to datetime
            return datetime.datetime.combine(self.as_date(), datetime.datetime.min.time())

        def as_timestamp(self) -> int:
            """Alias for "value" property, but as timestamp"""
            return int(time.mktime(self.as_date().timetuple()))
            # return int(time.mktime(datetime.datetime.strptime(self.value, '%Y-%m-%d').timetuple()))

        def as_int(self) -> int:
            return self.as_timestamp()

        def as_str(self) -> str:
            return str(self.as_date())

        # Override value setter, so we can convert from datetime.datetime or str to datetime.date
        def _set_value(self, value: typing.Any) -> None:
            if isinstance(value, datetime.datetime):
                value = value.date()
            elif isinstance(value, datetime.date):
                value = value
            elif isinstance(value, str):  # YYYY-MM-DD
                value = datetime.datetime.strptime(value, '%Y-%m-%d').date()
            else:
                raise ValueError(f'Invalid value for date: {value}')

            super()._set_value(value)

        @property
        def value(self) -> datetime.date:
            return self.as_date()

        @value.setter
        def value(self, value: datetime.date | str) -> None:
            self._set_value(value)

        def gui_description(self) -> types.ui.GuiDescription:
            fldgui = super().gui_description()
            # Convert if needed value and default to string (YYYY-MM-DD)
            if 'default' in fldgui:
                fldgui['default'] = str(fldgui['default'])
            return fldgui

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
            default: typing.Union[collections.abc.Callable[[], str], str] = '',
            value: typing.Optional[str] = None,
            old_field_name: types.ui.OldFieldNameType = None,
        ):
            super().__init__(
                old_field_name=old_field_name,
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

        def _set_value(self, value: typing.Any) -> None:
            """
            To ensure value is an str
            """
            super()._set_value(gui.as_str(value))

        def as_str(self) -> str:
            """Returns the password as string (stripped)"""
            return gui.as_str(self.value).strip()

        as_clean_str = as_str  # Alias in facet, for coherence with other string fields

        @property
        def value(self) -> str:
            return gui.as_str(super().value)  # Avoid recursion

        @value.setter
        def value(self, value: str) -> None:
            self._set_value(value)

        def __str__(self) -> str:
            return '********'  # Override so we do not show the password

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


           After that, at init_gui method of module, we can store a value inside
           using value as shown here:

           .. code-block:: python

              def init_gui(self):
                  # always set default using self, cause we only want to store
                  # value for current instance
                  self.hidden.value = self.provider().serialize()
                  # Note, you can use setDefault for legacy compat

        """

        _is_serializable: bool

        def __init__(
            self,
            label: str = '',  # label is optional on hidden fields
            order: int = 0,
            default: typing.Any = None,  # May be also callable
            value: typing.Any = None,
            serializable: bool = False,
            old_field_name: types.ui.OldFieldNameType = None,
        ) -> None:
            super().__init__(
                old_field_name=old_field_name,
                label=label,
                order=order,
                default=default,
                value=value,
                type=types.ui.FieldType.HIDDEN,
            )
            self._is_serializable = serializable

        def is_serializable(self) -> bool:
            return self._is_serializable

        def set_default(self, value: typing.Any) -> None:
            """
            Sets the default value of the field. Overriden for HiddenField

            Args:
                value: Default value (string)
            """
            super().set_default(value)
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
            default: typing.Union[collections.abc.Callable[[], bool], bool] = False,
            value: typing.Optional[bool] = None,
            old_field_name: types.ui.OldFieldNameType = None,
        ):
            super().__init__(
                old_field_name=old_field_name,
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

        def _set_value(self, value: typing.Union[str, bytes, bool]) -> None:
            """
            Override to set value to True or False (bool)
            """
            super()._set_value(gui.as_bool(value))
            # self._fields_info.value = gui.as_bool(value)

        @property
        def value(self) -> bool:
            return gui.as_bool(super().value)

        @value.setter
        def value(self, value: bool) -> None:
            self._set_value(value)

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
          constructor or init_gui using set_values

        There is an extra option available for this kind of field:

           fills: This options is a dictionary that contains this fields:
              * 'callback_name' : Callback name for invocation via the specific
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
                   fills = { 'target': 'choice2', 'callback': fncvalues,
                       'parameters': ['choice1', 'name']}
                   )
               choice2 = gui.ChoiceField(label="Choice 2")

            Here is a more detailed explanation, using the a Test service module as
            sample.

            class TestHelpers(object):
                # ...
                # other stuff
                # ...
                @staticmethod
                def get_machines(parameters):
                    # ...initialization and other stuff...
                    if parameters['resourcePool'] != '':
                        # ... do stuff ...
                    data = [ { 'name' : 'machine', 'choices' : [{'id': 'xxxxxx', 'value': 'yyyy'}] } ]
                    return data

            class ModuleTest(services.Service)
                # ...
                # stuff
                # ...
                resourcepool = gui.ChoiceField(
                    label=_("Resource Pool"), readonly = False, order = 5,
                    fills = {
                        'callback_name' : 'vcFillMachinesFromResource',
                        'function' : VCHelpers.getMachines,
                        'parameters' : ['vc', 'ev', 'resourcePool']
                    },
                    tooltip = _('Resource Pool containing base machine'),
                    required = True
                )

                machine = gui.ChoiceField(label = _("Base Machine"), order = 6,
                    tooltip = _('Base machine for this service'), required = True )

        """

        def __init__(
            self,
            label: str,
            readonly: bool = False,
            order: int = 0,
            tooltip: str = '',
            required: typing.Optional[bool] = None,
            choices: _ChoicesParamType = None,
            fills: typing.Optional[types.ui.Filler] = None,
            tab: typing.Optional[typing.Union[str, types.ui.Tab]] = None,
            default: typing.Union[collections.abc.Callable[[], str], str, None] = None,
            value: typing.Optional[str] = None,
            old_field_name: types.ui.OldFieldNameType = None,
        ) -> None:
            super().__init__(
                old_field_name=old_field_name,
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

            self._field_info.choices = gui.as_choices(choices)
            # if has fillers, set them
            if fills:
                if 'function' not in fills:
                    raise ValueError('Invalid fills parameters')
                fills['callback_name'] = fills.get('callback_name', modfinder.callable_path(fills['function']))
                fnc = fills['function']
                fills.pop('function')
                self._field_info.fills = fills
                # Store it only if not already present
                if fills['callback_name'] not in gui.callbacks:
                    gui.callbacks[fills['callback_name']] = fnc

        def set_choices(self, values: collections.abc.Iterable[typing.Union[str, types.ui.ChoiceItem]]) -> None:
            """
            Set the values for this choice field
            """
            self._field_info.choices = gui.as_choices(values)

        def _set_value(self, value: typing.Any) -> None:
            """
            To ensure value is an str
            """
            super()._set_value(gui.as_str(value))

        def as_str(self) -> str:
            return gui.as_str(self.value)

        @property
        def value(self) -> str:
            return gui.as_str(super().value)

        @value.setter
        def value(self, value: str) -> None:
            self._set_value(value)

    class ImageChoiceField(InputField):
        def __init__(
            self,
            label: str,
            readonly: bool = False,
            order: int = 0,
            tooltip: str = '',
            required: typing.Optional[bool] = None,
            choices: _ChoicesParamType = None,
            tab: typing.Optional[typing.Union[str, types.ui.Tab]] = None,
            default: typing.Union[collections.abc.Callable[[], str], str, None] = None,
            value: typing.Optional[str] = None,
            old_field_name: types.ui.OldFieldNameType = None,
        ):
            super().__init__(
                old_field_name=old_field_name,
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

            self._field_info.choices = gui.as_choices(choices or [])

        def set_choices(self, values: collections.abc.Iterable[typing.Union[str, types.ui.ChoiceItem]]) -> None:
            """
            Set the values for this choice field
            """
            self._field_info.choices = gui.as_choices(values)

        def _set_value(self, value: typing.Any) -> None:
            """
            To ensure value is an str
            """
            super()._set_value(gui.as_str(value))

        def as_str(self) -> str:
            return gui.as_str(self.value)

        @property
        def value(self) -> str:
            return gui.as_str(super().value)

        @value.setter
        def value(self, value: str) -> None:
            self._set_value(value)

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
            choices: _ChoicesParamType = None,
            tab: typing.Optional[typing.Union[str, types.ui.Tab]] = None,
            default: typing.Union[
                collections.abc.Callable[[], str], collections.abc.Callable[[], list[str]], list[str], str, None
            ] = None,
            value: typing.Optional[collections.abc.Iterable[str]] = None,
            old_field_name: types.ui.OldFieldNameType = None,
        ):
            super().__init__(
                old_field_name=old_field_name,
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

            self._field_info.rows = rows
            self._field_info.choices = gui.as_choices(choices or [])

        def set_choices(
            self, choices: collections.abc.Iterable[typing.Union[str, types.ui.ChoiceItem]]
        ) -> None:
            """
            Set the values for this choice field
            """
            self._field_info.choices = gui.as_choices(choices)

        def _set_value(self, value: typing.Any) -> None:
            """
            To ensure value is an list of strings
            """
            if not isinstance(value, collections.abc.Iterable):
                value = [gui.as_str(value)]
            else:  # Is an iterable
                value = [gui.as_str(i) for i in value]  # pyright: ignore[reportUnknownVariableType]
            super()._set_value(value)

        def as_list(self) -> list[str]:
            """
            Return value as list of strings
            """
            if not super().value:
                return []
            try:
                return list(super().value)
            except Exception:
                return []

        @property
        def value(self) -> list[str]:
            return self.as_list()

        @value.setter
        def value(self, value: collections.abc.Iterable[str]) -> None:
            self._set_value(value)

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
              ip_list = gui.EditableList(label=_('List of IPS'))

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
                collections.abc.Callable[[], str], collections.abc.Callable[[], list[str]], list[str], str, None
            ] = None,
            value: typing.Optional[collections.abc.Iterable[str]] = None,
            old_field_name: types.ui.OldFieldNameType = None,
        ) -> None:
            super().__init__(
                old_field_name=old_field_name,
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

        def _set_value(self, value: typing.Any) -> None:
            """
            To ensure value is an list of strings
            """
            if not isinstance(value, collections.abc.Iterable):
                value = [gui.as_str(value)]
            else:
                value = [gui.as_str(i) for i in value]  # pyright: ignore[reportUnknownVariableType]
            super()._set_value(value)

        def as_list(self) -> list[str]:
            """
            Return value as list of strings
            """
            if not super().value:
                return []
            try:
                return list(super().value)
            except Exception:
                return []

        @property
        def value(self) -> list[str]:
            return self.as_list()

        @value.setter
        def value(self, value: collections.abc.Iterable[typing.Any]) -> None:
            self._set_value(value)

    class HelpField(InputField):
        """
        Informational field (no input nor output)

        The current valid info fields are:
           title: 'name' = 'title', 'default' = 'real title'

        """

        def __init__(
            self,
            label: str,
            title: str,
            help: str,
            old_field_name: types.ui.OldFieldNameType = None,
        ) -> None:
            super().__init__(
                label=label, default=[title, help], type=types.ui.FieldType.INFO, old_field_name=old_field_name
            )


class UserInterfaceType(abc.ABCMeta, type):
    """
    Metaclass definition for moving the user interface descriptions to a usable
    better place. This is done this way because we will "deepcopy" these fields
    later, and update references on class 'self' to the new copy. (so everyone has a different copy)
    """

    def __new__(
        mcs: type['UserInterfaceType'],
        classname: str,
        bases: tuple[type, ...],
        namespace: dict[str, typing.Any],
    ) -> 'UserInterfaceType':
        new_class_dict: dict[str, typing.Any] = {}
        _gui: collections.abc.MutableMapping[str, gui.InputField] = {}

        # Make a copy of gui fields description
        # (we will update references on class 'self' to the new copy)
        for attr_name, attr in namespace.items():
            if isinstance(attr, gui.InputField):
                # Ensure we have a copy of the data, so we can modify it without affecting others
                attr._field_info = copy.deepcopy(attr._field_info)
                attr._field_info.field_name = attr_name
                _gui[attr_name] = attr

            new_class_dict[attr_name] = attr
        new_class_dict['_gui_fields_template'] = _gui
        return super().__new__(mcs, classname, bases, new_class_dict)


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
    _gui_fields_template: typing.ClassVar[dict[str, gui.InputField]]

    # instance variable that will hold the gui fields description
    # this allows us to modify the gui fields values at runtime without affecting other instances
    _gui: dict[str, gui.InputField]

    def __init__(self, values: gui.ValuesType = None) -> None:
        # : If there is an array of elements to initialize, simply try to store
        # values on form fields.

        # Generate a deep copy of inherited Gui, so each User Interface instance
        # has its own "field" set, and do not share the "fielset" with others, what
        # can be really dangerous. Till now, nothing bad happened cause there where
        # being used "serialized", but this do not have to be this way

        # Ensure "gui" points to a copy of original gui, not the original one
        # this is done to avoid modifying the original gui description

        self._gui = copy.deepcopy(self._gui_fields_template)

        # If a field has a callable on defined attributes(value, default, choices)
        # update the reference to the new copy
        for fld_name, fld in self._gui.items():  # And refresh self references to them
            setattr(self, fld_name, fld)  # Reference to self._gui[key]

            # Check for "callable" fields and update them if needed
            for field in ['choices', 'default']:  # Update references to self for callable fields
                attr = getattr(fld._field_info, field, None)
                if attr and callable(attr):
                    # val is an InputField derived instance, so it is a reference to self._gui[key]
                    setattr(fld._field_info, field, attr())

            if values is not None:
                if fld_name in values:
                    fld.value = values[fld_name]
                else:
                    logger.warning('Field %s.%s not found in values data, ', self.__class__.__name__, fld_name)
                    if getattr(settings, 'DEBUG', False):
                        for caller in itertools.islice(inspect.stack(), 1, 8):
                            logger.warning('  %s:%s:%s', caller.filename, caller.lineno, caller.function)

    def init_gui(self) -> None:
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

    @classmethod
    def describe_fields(cls: type[typing.Self]) -> list[types.ui.GuiElement]:
        return [
            {
                'name': key,
                'gui': val.gui_description(),
                'value': val.value if val.is_type(types.ui.FieldType.HIDDEN) else None,
            }
            for key, val in cls._gui_fields_template.items()
        ]

    def get_fields_as_dict(self) -> gui.ValuesDictType:
        """
        Returns own data needed for user interaction as a dict of key-names ->
        values. The values returned must be strings.

        Example:
            we have 2 text field, first named "host" and second named "port",
            we can do something like this:

            .. code-block:: python

               return { 'host' : self.host, 'port' : self.port }

            (Just the reverse of :py:meth:`.__init__`, __init__ receives this
            dict, dict_of_values must return the dict)

        Names must coincide with fields declared.

        Returns:
             Dictionary, associated with declared fields.
             Default implementation returns the values stored at the gui form
             fields declared.

        :note: By default, the provided method returns the correct values
               extracted from form fields

        """
        fields: gui.ValuesDictType = {}
        for fld, fld_gui in self._gui.items():
            if fld_gui.is_type(types.ui.FieldType.EDITABLELIST, types.ui.FieldType.MULTICHOICE):
                fields[fld] = ensure.as_list(fld_gui.value)
            else:
                fields[fld] = fld_gui.value
        logger.debug('Values Dict: %s', fields)
        return fields

    def serialize_fields(
        self,
    ) -> bytes:
        """New form serialization

        Returns:
            bytes -- serialized form (zipped)
        """

        # Any unexpected type will raise an exception
        # Note that we always store CURRENT field name, so once migrated forward
        # we cannot reverse it to original... (unless we reverse old_field_name to current, and then current to old)
        # but this is not recommended :)
        fields = [
            (field_name, field.field_type.name, FIELDS_ENCODERS[field.field_type](field))
            for field_name, field in self._all_serializable_fields()
            if FIELDS_ENCODERS[field.field_type](field) is not None
        ]

        return consts.ui.SERIALIZATION_HEADER + consts.ui.SERIALIZATION_VERSION + serializer.serialize(fields)

    def deserialize_fields(
        self,
        values: bytes,
    ) -> bool:
        """New form unserialization

        Args:
            values: list of serilizes (as bytes) values

        Returns:
            bool -- True if values were unserialized using OLD method, False if using new one

        Note:
            If returns True, the manager will try to remarshall the values using the new method

        Note:
            The format of serialized fields is:

            .. code-block:: python

                    SERIALIZATION_HEADER + SERIALIZATION_VERSION + serializer.serialize(fields)

                Where:

                * SERIALIZATION_HEADER: b'GUIZ'  (header)
                * SERIALIZATION_VERSION: b'\001' (serialization version, currently 1)
                * fields: list of tuples (field_name, field_type, field_value)
                * serializer: serializer used (custom one that pickles, compress and encrypts data)
        """

        if not values:
            return False

        if not values.startswith(consts.ui.SERIALIZATION_HEADER):
            # Unserialize with old method, and notify that we need to upgrade
            self.deserialize_from_old_format(values)
            return True

        # For future use, right now we only have one version
        # Prepared for a possible future versioning of data serialization
        _version = values[
            len(consts.ui.SERIALIZATION_HEADER) : len(consts.ui.SERIALIZATION_HEADER)
            + len(consts.ui.SERIALIZATION_VERSION)
        ]

        values = values[len(consts.ui.SERIALIZATION_HEADER) + len(consts.ui.SERIALIZATION_VERSION) :]

        if not values:  # Apart of the header, there is nothing...
            logger.debug('Empty values on unserialize_fields')
            return False

        fields: list[typing.Any] = serializer.deserialize(values) or []

        # Dict of translations from old_field_name to field_name
        field_names_translations: dict[str, str] = self._get_fieldname_translations()

        # Allowed conversions of type
        VALID_CONVERSIONS: typing.Final[dict[types.ui.FieldType, list[types.ui.FieldType]]] = {
            types.ui.FieldType.TEXT: [types.ui.FieldType.PASSWORD]
        }
        

        # Set all values to defaults ones
        for field_name, field in self._all_serializable_fields():
            if field.is_type(types.ui.FieldType.HIDDEN) and field.is_serializable() is False:
                # logger.debug('Field {0} is not unserializable'.format(k))
                continue
            field.value = field.default

        for field_name, field_type, field_value in fields:
            field_name = field_names_translations.get(field_name, field_name)
            if field_name not in self._gui:
                # Probably removed, just to note this in case of debugging
                logger.debug('Field %s not found in form (%s)', field_name, field_value)
                continue
            internal_field_type = self._gui[field_name].field_type
            if internal_field_type not in FIELD_DECODERS:
                logger.warning('Field %s has no decoder', field_name)
                continue

            if field_type != internal_field_type.name:
                if valids_for_field := VALID_CONVERSIONS.get(internal_field_type):
                    if field_type not in [v.name for v in valids_for_field]:
                        # If the field type is not valid for the internal field type, we log a warning
                        # and do not include this field in the form
                        logger.warning(
                            'Field %s has different type than expected: %s != %s. Not included in form',
                            field_name,
                            field_type,
                            internal_field_type.name,
                        )
                        continue

            self._gui[field_name].value = FIELD_DECODERS[internal_field_type](field_value)

        return False

    def deserialize_from_old_format(self, values: bytes) -> None:
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
                if self._gui[k].is_type(types.ui.FieldType.HIDDEN) and self._gui[k].is_serializable() is False:
                    # logger.debug('Field {0} is not unserializable'.format(k))
                    continue
                self._gui[k].value = self._gui[k].default

            values = codecs.decode(values, 'zip')
            if not values:  # Has nothing
                return

            field_names_translations: dict[str, str] = self._get_fieldname_translations()

            for txt in values.split(FIELD_SEPARATOR):
                kb, v = txt.split(NAME_VALUE_SEPARATOR)
                k = kb.decode('utf8')  # Convert name to string
                # convert to new name if needed
                k = field_names_translations.get(k, k)
                if k in self._gui:
                    try:
                        if v.startswith(MULTIVALUE_FIELD):
                            val = pickle.loads(v[1:])
                        elif v.startswith(OLD_PASSWORD_FIELD):
                            val = CryptoManager().aes_decrypt(v[1:], consts.ui.UDSB, True).decode()
                        elif v.startswith(PASSWORD_FIELD):
                            val = CryptoManager().aes_decrypt(v[1:], UDSK, True).decode()
                        else:
                            val = v.decode('utf8')
                    except Exception:
                        logger.exception('Pickling %s from %s', k, self)
                        val = ''
                    self._gui[k].value = val
                # logger.debug('Value for {0}:{1}'.format(k, val))
        except Exception:
            logger.exception('Exception on unserialization on %s', self.__class__)
            # Values can contain invalid characters, so we log every single char
            # logger.info('Invalid serialization data on {0} {1}'.format(self, values.encode('hex')))

    def gui_description(self, *, skip_init_gui: bool = False) -> list[types.ui.GuiElement]:
        """
        This simple method generates the the_gui description needed by the
        administration client, so it can
        represent it at user interface and manage it.

        Args:
            skip_init_gui: If True, init_gui will not be called

        Note:
            skip_init_gui is used to avoid calling init_gui when we are not going to use the result
            This is used, for example, when exporting data, generating the tree, etc...
        """
        if not skip_init_gui:
            self.init_gui()  # We give the "oportunity" to fill necesary theGui data before providing it to client

        res: list[types.ui.GuiElement] = []
        for key, val in self._gui.items():
            # Only add "value" for hidden fields on gui description. Rest of fields will be filled by client
            res.append(
                {
                    'name': key,
                    'gui': val.gui_description(),
                    'value': val.value if val.is_type(types.ui.FieldType.HIDDEN) else None,
                }
            )
        # logger.debug('theGui description: %s', res)
        return res

    def errors(self) -> list[ValidationFieldInfo]:
        found_errors: list[UserInterface.ValidationFieldInfo] = []
        for key, val in self._gui.items():
            if val.required and not val.value:
                found_errors.append(UserInterface.ValidationFieldInfo(key, 'Field is required'))
            if not val.validate():
                found_errors.append(UserInterface.ValidationFieldInfo(key, 'Field is not valid'))

        return found_errors

    def _all_serializable_fields(self) -> collections.abc.Iterable[tuple[str, gui.InputField]]:
        for k, field in self._gui.items():
            yield (k, field)

    def _get_fieldname_translations(self) -> dict[str, str]:
        # Dict of translations from old_field_name to field_name
        # Note that if an old_field_name is repeated on different fields, only the FIRST will be used
        # Also, order of fields is not guaranteed, so we we cannot assure that the first one will be chosen
        field_names_translations: dict[str, str] = {}
        for fld_name, fld in self._all_serializable_fields():
            for fld_old_field_name in fld.old_field_name():
                if fld_old_field_name != fld_name:
                    field_names_translations[fld_old_field_name] = fld_name

        return field_names_translations

    def has_field(self, field_name: str) -> bool:
        """
        So we can check against field existence on "own" instance
        If not redeclared in derived class, it will return False
        """
        return field_name in self._gui


def password_compat_field_decoder(value: str) -> str:
    """
    Compatibility function to decode text fields converted to password fields
    """
    try:
        value = CryptoManager.manager().aes_decrypt(value.encode('utf8'), UDSK, True).decode()
    except Exception:
        pass
    return value


# Dictionaries used to encode/decode fields to be stored on database
FIELDS_ENCODERS: typing.Final[
    collections.abc.Mapping[
        types.ui.FieldType, collections.abc.Callable[[gui.InputField], typing.Optional[str]]
    ]
] = {
    types.ui.FieldType.TEXT: lambda x: x.value,
    types.ui.FieldType.TEXT_AUTOCOMPLETE: lambda x: x.value,
    types.ui.FieldType.NUMERIC: lambda x: str(int(gui.as_int(x.value))),
    types.ui.FieldType.PASSWORD: lambda x: (
        CryptoManager.manager().aes_crypt(x.value.encode('utf8'), UDSK, True).decode()
    ),
    types.ui.FieldType.HIDDEN: (lambda x: None if not x.is_serializable() else x.value),
    types.ui.FieldType.CHOICE: lambda x: x.value,
    types.ui.FieldType.MULTICHOICE: lambda x: base64.b64encode(serializer.serialize(x.value)).decode(),
    types.ui.FieldType.EDITABLELIST: lambda x: base64.b64encode(serializer.serialize(x.value)).decode(),
    types.ui.FieldType.CHECKBOX: lambda x: consts.TRUE_STR if gui.as_bool(x.value) else consts.FALSE_STR,
    types.ui.FieldType.IMAGECHOICE: lambda x: x.value,
    types.ui.FieldType.DATE: lambda x: x.value,
    types.ui.FieldType.INFO: lambda x: None,
}

FIELD_DECODERS: typing.Final[
    collections.abc.Mapping[types.ui.FieldType, collections.abc.Callable[[str], typing.Any]]
] = {
    types.ui.FieldType.TEXT: lambda x: x,
    types.ui.FieldType.TEXT_AUTOCOMPLETE: lambda x: x,
    types.ui.FieldType.NUMERIC: int,
    types.ui.FieldType.PASSWORD: password_compat_field_decoder,
    types.ui.FieldType.HIDDEN: lambda x: x,
    types.ui.FieldType.CHOICE: lambda x: x,
    types.ui.FieldType.MULTICHOICE: lambda x: serializer.deserialize(base64.b64decode(x.encode())),
    types.ui.FieldType.EDITABLELIST: lambda x: serializer.deserialize(base64.b64decode(x.encode())),
    types.ui.FieldType.CHECKBOX: lambda x: x,
    types.ui.FieldType.IMAGECHOICE: lambda x: x,
    types.ui.FieldType.DATE: lambda x: x,
    types.ui.FieldType.INFO: lambda x: None,
}
