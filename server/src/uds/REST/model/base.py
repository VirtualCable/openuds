# -*- coding: utf-8 -*-
#
# Copyright (c) 2014-2023 Virtual Cable S.L.U.
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

import logging
import typing

from django.db import models
from django.utils.translation import gettext as _

from uds.core import consts
from uds.core import exceptions
from uds.core import types
from uds.core.module import Module
from uds.core.util import permissions
from uds.models import ManagedObjectModel

from ..handlers import Handler

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# pylint: disable=unused-argument
class BaseModelHandler(Handler, typing.Generic[types.rest.T_Item]):
    """
    Base Handler for Master & Detail Handlers
    """

    def check_access(
        self,
        obj: models.Model,
        permission: 'types.permissions.PermissionType',
        root: bool = False,
    ) -> None:
        if not permissions.has_access(self._user, obj, permission, root):
            raise self.access_denied_response()

    def get_permissions(self, obj: models.Model, root: bool = False) -> int:
        return permissions.effective_permissions(self._user, obj, root)

    def extra_type_info(self, type_: type['Module']) -> types.rest.ExtraTypeInfo | None:
        """
        Returns info about the type
        In fact, right now, it returns an empty dict, that will be extended by typeAsDict
        """
        return None

    def as_typeinfo(self, type_: type['Module']) -> types.rest.TypeInfo:
        """
        Returns a dictionary describing the type (the name, the icon, description, etc...)
        """
        return types.rest.TypeInfo(
            name=_(type_.mod_name()),
            type=type_.mod_type(),
            description=_(type_.description()),
            icon=type_.icon64().replace('\n', ''),
            extra=self.extra_type_info(type_),
            group=getattr(type_, 'group', None),
        )

    def table_info(
        self,
        title: str,
        fields: list[typing.Any],
        row_style: types.ui.RowStyleInfo,
        subtitle: str | None = None,
    ) -> types.rest.TableInfo:
        """
        Returns a dict containing the table fields description
        """
        return types.rest.TableInfo(
            title=title,
            fields=fields,
            row_style=row_style,
            subtitle=subtitle,
        )

    def fields_from_params(
        self, fields_list: list[str], *, defaults: dict[str, typing.Any] | None = None
    ) -> dict[str, typing.Any]:
        """
        Reads the indicated fields from the parameters received, and if
        :param fields_list: List of required fields
        :return: A dictionary containing all required fields
        """
        args: dict[str, str] = {}
        default: str | None = None
        try:
            for key in fields_list:
                # if : is in the field, it is an optional field, with an "static" default value
                if ':' in key:  # optional field? get default if not present
                    k, default = key.split(':')[:2]
                    # Convert "None" to None
                    default = None if default == 'None' else default
                    # If key is not present, and default = _, then it is not required skip it
                    if default == '_' and k not in self._params:
                        continue
                    args[k] = self._params.get(k, default)
                else:  # Required field, with a possible default on defaults dict
                    if key not in self._params:
                        if defaults and key in defaults:
                            args[key] = defaults[key]
                        else:
                            raise exceptions.rest.RequestError(f'needed parameter not found in data {key}')
                    else:
                        # Set the value
                        args[key] = self._params[key]

                # del self._params[key]
        except KeyError as e:
            raise exceptions.rest.RequestError(f'needed parameter not found in data {e}')

        return args

    @staticmethod
    def fill_instance_type(item: 'models.Model', dct: types.rest.ManagedObjectItem) -> None:
        """
        For Managed Objects (db element that contains a serialized object), fills a dictionary with the "type" and "type_name" parameters values.
        For non managed objects, it does nothing

        Args:
            item: Item to fill type
            dct: Dictionary to fill with type

        """
        if isinstance(item, ManagedObjectModel):
            kind = item.get_type()
            typing.cast(dict[str, typing.Any], dct)['type'] = kind.mod_type()
            typing.cast(dict[str, typing.Any], dct)['type_name'] = kind.mod_name()

    @staticmethod
    def fill_instance_fields(item: 'models.Model', dct: types.rest.BaseRestItem) -> None:
        """
        For Managed Objects (db element that contains a serialized object), fills a dictionary with the "field" parameters values.
        For non managed objects, it does nothing

        Args:
            item: Item to fill fields
            dct: Dictionary to fill with fields

        """

        # Cast to allow override typing
        if isinstance(item, ManagedObjectModel):
            res = typing.cast(types.rest.ManagedObjectItem, dct)
            i = item.get_instance()
            i.init_gui()  # Defaults & stuff
            fields = i.get_fields_as_dict()

            # TODO: This will be removed in future versions, as it will be overseed by "instance" key
            typing.cast(typing.Any, res).update(fields)  # Add fields to dict
            res['type'] = i.mod_type()  # Add type
            res['type_name'] = i.mod_name()  # Add type name
            # Future inmplementation wil insert instace fields into "instance" key
            # For now, just repeat the fields
            res['instance'] = fields

    # Exceptions
    def invalid_request_response(self, message: str | None = None) -> exceptions.rest.HandlerError:
        """
        Raises an invalid request error with a default translated string
        :param message: Custom message to add to exception. If it is None, "Invalid Request" is used
        """
        message = message or _('Invalid Request')
        return exceptions.rest.RequestError(f'{message} {self.__class__}: {self._args}')

    def invalid_response_response(self, message: str | None = None) -> exceptions.rest.HandlerError:
        message = 'Invalid response' if message is None else message
        return exceptions.rest.ResponseError(message)

    def invalid_method_response(self) -> exceptions.rest.HandlerError:
        """
        Raises a NotFound exception with translated "Method not found" string to current locale
        """
        return exceptions.rest.RequestError(_('Method not found in {}: {}').format(self.__class__, self._args))

    def invalid_item_response(self, message: str | None = None) -> exceptions.rest.HandlerError:
        """
        Raises a NotFound exception, with location info
        """
        message = message or _('Item not found')
        return exceptions.rest.NotFound(message)
        # raise NotFound('{} {}: {}'.format(message, self.__class__, self._args))

    def access_denied_response(self, message: str | None = None) -> exceptions.rest.HandlerError:
        return exceptions.rest.AccessDenied(message or _('Access denied'))

    def not_supported_response(self, message: str | None = None) -> exceptions.rest.HandlerError:
        return exceptions.rest.NotSupportedError(message or _('Operation not supported'))

    # Success methods
    def success(self) -> str:
        """
        Utility method to be invoked for simple methods that returns a simple OK response
        """
        logger.debug('Returning success on %s %s', self.__class__, self._args)
        return consts.OK

    def test(self, type_: str) -> str:  # pylint: disable=unused-argument
        """
        Invokes a test for an item
        """
        logger.debug('Called base test for %s --> %s', self.__class__.__name__, self._params)
        raise self.invalid_method_response()
