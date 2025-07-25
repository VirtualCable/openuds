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
# pylint: disable=too-many-public-methods

import inspect
import logging
import typing

from django.db import models
from django.utils.translation import gettext as _

from uds.core import consts
from uds.core import exceptions
from uds.core import types
from uds.core.module import Module
from uds.core.util import permissions
from uds.models import ManagedObjectModel, Network

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

    def add_field(
        self, gui: list[typing.Any], field: typing.Union[types.rest.FieldType, list[types.rest.FieldType]]
    ) -> list[typing.Any]:
        """
        Add a field to a "gui" description.
        This method checks that every required field element is in there.
        If not, defaults are assigned
        :param gui: List of "gui" items where the field will be added
        :param field: Field to be added (dictionary)
        """
        if isinstance(field, list):
            for i in field:
                gui = self.add_field(gui, i)
        else:
            if 'values' in field:
                caller = inspect.stack()[1]
                logger.warning(
                    'Field %s has "values" attribute, this is deprecated and will be removed in future versions. Use "choices" instead. Called from %s:%s',
                    field.get('name', ''),
                    caller.filename,
                    caller.lineno,
                )
                choices = field['values']
            else:
                choices = field.get('choices', None)
            # Build gui with non empty values
            gui_description: dict[str, typing.Any] = {}
            # First, mandatory fields
            for fld in ('name', 'type'):
                if fld not in field:
                    caller = inspect.stack()[1]
                    logger.error(
                        'Field %s does not have mandatory field %s. Called from %s:%s',
                        field.get('name', ''),
                        fld,
                        caller.filename,
                        caller.lineno,
                    )
                    raise exceptions.rest.RequestError(
                        f'Field {fld} is mandatory on {field.get("name", "")} field.'
                    )

            if choices:
                gui_description['choices'] = choices
            # "fillable" fields (optional and mandatory on gui)
            for fld in (
                'type',
                'default',
                'required',
                'min_value',
                'max_value',
                'length',
                'lines',
                'tooltip',
                'readonly',
            ):
                if fld in field and field[fld] is not None:
                    gui_description[fld] = field[fld]

            # Order and label optional, but must be present on gui
            gui_description['order'] = field.get('order', 0)
            gui_description['label'] = field.get('label', field['name'])

            v: dict[str, typing.Any] = {
                'name': field.get('name', ''),
                'value': field.get('value', ''),
                'gui': gui_description,
            }
            if field.get('tab', None):
                v['gui']['tab'] = _(str(field['tab']))
            gui.append(v)
        return gui

    def add_default_fields(self, gui: list[typing.Any], flds: list[str]) -> list[typing.Any]:
        """
        Adds default fields (based in a list) to a "gui" description
        :param gui: Gui list where the "default" fielsds will be added
        :param flds: List of fields names requested to be added. Valid values are 'name', 'comments',
                    'priority' and 'small_name', 'short_name', 'tags'
        """
        if 'tags' in flds:
            self.add_field(
                gui,
                {
                    'name': 'tags',
                    'label': _('Tags'),
                    'type': 'taglist',
                    'tooltip': _('Tags for this element'),
                    'order': 0 - 105,
                },
            )
        if 'name' in flds:
            self.add_field(
                gui,
                {
                    'name': 'name',
                    'type': 'text',
                    'required': True,
                    'label': _('Name'),
                    'length': 128,
                    'tooltip': _('Name of this element'),
                    'order': 0 - 100,
                },
            )
        if 'comments' in flds:
            self.add_field(
                gui,
                {
                    'name': 'comments',
                    'label': _('Comments'),
                    'type': 'text',
                    'lines': 3,
                    'tooltip': _('Comments for this element'),
                    'length': 256,
                    'order': 0 - 90,
                },
            )
        if 'priority' in flds:
            self.add_field(
                gui,
                {
                    'name': 'priority',
                    'type': 'numeric',
                    'label': _('Priority'),
                    'tooltip': _('Selects the priority of this element (lower number means higher priority)'),
                    'required': True,
                    'value': 1,
                    'length': 4,
                    'order': 0 - 85,
                },
            )
        if 'small_name' in flds:
            self.add_field(
                gui,
                {
                    'name': 'small_name',
                    'type': 'text',
                    'label': _('Label'),
                    'tooltip': _('Label for this element'),
                    'required': True,
                    'length': 128,
                    'order': 0 - 80,
                },
            )
        if 'networks' in flds:
            self.add_field(
                gui,
                {
                    'name': 'net_filtering',
                    'value': 'n',
                    'choices': [
                        {'id': 'n', 'text': _('No filtering')},
                        {'id': 'a', 'text': _('Allow selected networks')},
                        {'id': 'd', 'text': _('Deny selected networks')},
                    ],
                    'label': _('Network Filtering'),
                    'tooltip': _(
                        'Type of network filtering. Use "Disabled" to disable origin check, "Allow" to only enable for selected networks or "Deny" to deny from selected networks'
                    ),
                    'type': 'choice',
                    'order': 100,  # At end
                    'tab': types.ui.Tab.ADVANCED,
                },
            )
            self.add_field(
                gui,
                {
                    'name': 'networks',
                    'value': [],
                    'choices': sorted(
                        [{'id': x.uuid, 'text': x.name} for x in Network.objects.all()],
                        key=lambda x: x['text'].lower(),
                    ),
                    'label': _('Networks'),
                    'tooltip': _('Networks associated. If No network selected, will mean "all networks"'),
                    'type': 'multichoice',
                    'order': 101,
                    'tab': types.ui.Tab.ADVANCED,
                },
            )

        return gui

    def ensure_has_access(
        self,
        obj: models.Model,
        permission: 'types.permissions.PermissionType',
        root: bool = False,
    ) -> None:
        if not permissions.has_access(self._user, obj, permission, root):
            raise self.access_denied_response()

    def get_permissions(self, obj: models.Model, root: bool = False) -> int:
        return permissions.effective_permissions(self._user, obj, root)

    def type_info(self, type_: type['Module']) -> typing.Optional[types.rest.ExtraTypeInfo]:
        """
        Returns info about the type
        In fact, right now, it returns an empty dict, that will be extended by typeAsDict
        """
        return None

    def type_as_dict(self, type_: type['Module']) -> types.rest.TypeInfoDict:
        """
        Returns a dictionary describing the type (the name, the icon, description, etc...)
        """
        res = types.rest.TypeInfo(
            name=_(type_.mod_name()),
            type=type_.mod_type(),
            description=_(type_.description()),
            icon=type_.icon64().replace('\n', ''),
            extra=self.type_info(type_),
            group=getattr(type_, 'group', None),
        ).as_dict()

        return res

    def process_table_fields(
        self,
        title: str,
        fields: list[typing.Any],
        row_style: types.ui.RowStyleInfo,
        subtitle: typing.Optional[str] = None,
    ) -> dict[str, typing.Any]:
        """
        Returns a dict containing the table fields description
        """
        return {
            'title': title,
            'fields': fields,
            'row-style': row_style.as_dict(),
            'subtitle': subtitle or '',
        }

    def fields_from_params(
        self, fields_list: list[str], *, defaults: 'dict[str, typing.Any]|None' = None
    ) -> dict[str, typing.Any]:
        """
        Reads the indicated fields from the parameters received, and if
        :param fields_list: List of required fields
        :return: A dictionary containing all required fields
        """
        args: dict[str, str] = {}
        default: typing.Optional[str]
        try:
            for key in fields_list:
                if ':' in key:  # optional field? get default if not present
                    k, default = key.split(':')[:2]
                    # Convert "None" to None
                    default = None if default == 'None' else default
                    # If key is not present, and default = _, then it is not required skip it
                    if default == '_' and k not in self._params:
                        continue
                    args[k] = self._params.get(k, default)
                else:
                    try:
                        args[key] = self._params[key]
                    except KeyError:
                        if defaults is not None and key in defaults:
                            args[key] = defaults[key]
                        else:
                            raise

                # del self._params[key]
        except KeyError as e:
            raise exceptions.rest.RequestError(f'needed parameter not found in data {e}')

        return args

    @staticmethod
    def fill_instance_type(item: 'models.Model', dct: types.rest.ManagedObjectDictType) -> None:
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
    def fill_instance_fields(item: 'models.Model', dct: types.rest.ItemDictType) -> None:
        """
        For Managed Objects (db element that contains a serialized object), fills a dictionary with the "field" parameters values.
        For non managed objects, it does nothing

        Args:
            item: Item to fill fields
            dct: Dictionary to fill with fields

        """

        # Cast to allow override typing
        if isinstance(item, ManagedObjectModel):
            res = typing.cast(types.rest.ManagedObjectDictType, dct)
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
    def invalid_request_response(self, message: typing.Optional[str] = None) -> exceptions.rest.HandlerError:
        """
        Raises an invalid request error with a default translated string
        :param message: Custom message to add to exception. If it is None, "Invalid Request" is used
        """
        message = message or _('Invalid Request')
        return exceptions.rest.RequestError(f'{message} {self.__class__}: {self._args}')

    def invalid_response_response(self, message: typing.Optional[str] = None) -> exceptions.rest.HandlerError:
        message = 'Invalid response' if message is None else message
        return exceptions.rest.ResponseError(message)

    def invalid_method_response(self) -> exceptions.rest.HandlerError:
        """
        Raises a NotFound exception with translated "Method not found" string to current locale
        """
        return exceptions.rest.RequestError(_('Method not found in {}: {}').format(self.__class__, self._args))

    def invalid_item_response(self, message: typing.Optional[str] = None) -> exceptions.rest.HandlerError:
        """
        Raises a NotFound exception, with location info
        """
        message = message or _('Item not found')
        return exceptions.rest.NotFound(message)
        # raise NotFound('{} {}: {}'.format(message, self.__class__, self._args))

    def access_denied_response(self, message: typing.Optional[str] = None) -> exceptions.rest.HandlerError:
        return exceptions.rest.AccessDenied(message or _('Access denied'))

    def not_supported_response(self, message: typing.Optional[str] = None) -> exceptions.rest.HandlerError:
        return exceptions.rest.NotSupportedError(message or _('Operation not supported'))

    # Success methods
    def success(self) -> str:
        """
        Utility method to be invoked for simple methods that returns nothing in fact
        """
        logger.debug('Returning success on %s %s', self.__class__, self._args)
        return consts.OK

    def test(self, type_: str) -> str:  # pylint: disable=unused-argument
        """
        Invokes a test for an item
        """
        logger.debug('Called base test for %s --> %s', self.__class__.__name__, self._params)
        raise self.invalid_method_response()
