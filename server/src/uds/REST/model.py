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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
# pylint: disable=too-many-public-methods

import abc
import fnmatch
import inspect
import logging
import re
import typing
import collections.abc
from types import GeneratorType

from django.db import IntegrityError, models
from django.utils.translation import gettext as _

from uds.core import consts
from uds.core import exceptions
from uds.core import types
from uds.core.module import Module
from uds.core.util import log, permissions
from uds.core.util.model import process_uuid
from uds.models import ManagedObjectModel, Network, Tag, TaggingMixin
from uds.REST.utils import rest_result

from .handlers import Handler

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.models import User

logger = logging.getLogger(__name__)

# a few constants
OVERVIEW: typing.Final[str] = 'overview'
TYPES: typing.Final[str] = 'types'
TABLEINFO: typing.Final[str] = 'tableinfo'
GUI: typing.Final[str] = 'gui'
LOG: typing.Final[str] = 'log'

FieldType = collections.abc.Mapping[str, typing.Any]


# pylint: disable=unused-argument
class BaseModelHandler(Handler):
    """
    Base Handler for Master & Detail Handlers
    """

    def add_field(
        self, gui: list[typing.Any], field: typing.Union[FieldType, list[FieldType]]
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
            guiDesc: dict[str, typing.Any] = {}
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
                guiDesc['choices'] = choices
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
                    guiDesc[fld] = field[fld]

            # Order and label optional, but must be present on gui
            guiDesc['order'] = field.get('order', 0)
            guiDesc['label'] = field.get('label', field['name'])

            v = {
                'name': field.get('name', ''),
                'value': field.get('value', ''),
                'gui': guiDesc,
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

    def type_info(self, type_: type['Module']) -> dict[str, typing.Any]:  # pylint: disable=unused-argument
        """
        Returns info about the type
        In fact, right now, it returns an empty dict, that will be extended by typeAsDict
        """
        return {}

    def type_as_dict(self, type_: type['Module']) -> types.rest.TypeInfoDict:
        """
        Returns a dictionary describing the type (the name, the icon, description, etc...)
        """
        res = types.rest.TypeInfo(
            name=_(type_.name()),
            type=type_.get_type(),
            description=_(type_.description()),
            icon=type_.icon64().replace('\n', ''),
        ).as_dict(**self.type_info(type_))
        if hasattr(type_, 'group'):
            res['group'] = _(type_.group)  # Add group info is it is contained
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

    def fields_from_params(self, fldList: list[str]) -> dict[str, typing.Any]:
        """
        Reads the indicated fields from the parameters received, and if
        :param fldList: List of required fields
        :return: A dictionary containing all required fields
        """
        args: dict[str, str] = {}
        default: typing.Optional[str]
        try:
            for key in fldList:
                if ':' in key:  # optional field? get default if not present
                    k, default = key.split(':')[:2]
                    # Convert "None" to None
                    default = None if default == 'None' else default
                    # If key is not present, and default = _, then it is not required skip it
                    if default == '_' and k not in self._params:
                        continue
                    args[k] = self._params.get(k, default)
                else:
                    args[key] = self._params[key]
                # del self._params[key]
        except KeyError as e:
            raise exceptions.rest.RequestError(f'needed parameter not found in data {e}')

        return args

    def fill_instance_fields(self, item: 'models.Model', res: dict[str, typing.Any]) -> dict[str, typing.Any]:
        """
        For Managed Objects (db element that contains a serialized object), fills a dictionary with the "field" parameters values.
        For non managed objects, it does nothing
        :param item: Item to extract fields
        :param res: Dictionary to "extend" with instance key-values pairs
        """
        if isinstance(item, ManagedObjectModel):
            i = item.get_instance()
            i.init_gui()  # Defaults & stuff
            res.update(i.get_fields_as_dict())
        return res

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


# Details do not have types at all
# so, right now, we only process details petitions for Handling & tables info
# noinspection PyMissingConstructor
class DetailHandler(BaseModelHandler):
    """
    Detail handler (for relations such as provider-->services, authenticators-->users,groups, deployed services-->cache,assigned, groups, transports
    Urls recognized for GET are:
    [path] --> get Items (all items, this call is delegated to get_items)
    [path]/overview
    [path]/ID
    [path]/gui
    [path]/gui/TYPE
    [path]/types
    [path]/types/TYPE
    [path]/tableinfo
    ....?filter=[filter],[filter]..., filters are simple unix files filters, with ^ and $ supported
    For PUT:
    [path] --> create NEW item
    [path]/ID --> Modify existing item
    For DELETE:
    [path]/ID

    Also accepts GET methods for "custom" methods
    """

    custom_methods: typing.ClassVar[list[str]] = []
    _parent: typing.Optional['ModelHandler']
    _path: str
    _params: typing.Any  # _params is deserialized object from request
    _args: tuple[str, ...]
    _kwargs: dict[str, typing.Any]
    _user: 'User'

    def __init__(
        self,
        parent_handler: 'ModelHandler',
        path: str,
        params: typing.Any,
        *args: str,
        **kwargs: typing.Any,
    ):  # pylint: disable=super-init-not-called
        """
        Detail Handlers in fact "disabled" handler most initialization, that is no needed because
        parent modelhandler has already done it (so we must access through parent handler)
        """
        # Parent init not invoked because their methos are not used on detail handlers (only on parent handlers..)
        self._parent = parent_handler
        self._path = path
        self._params = params
        self._args = args
        self._kwargs = kwargs
        self._user = kwargs.get('user', None)

    def _check_is_custom_method(self, check: str, parent: models.Model, arg: typing.Any = None) -> typing.Any:
        """
        checks curron methods
        :param check: Method to check
        :param parent: Parent Model Element
        :param arg: argument to pass to custom method
        """
        logger.debug('Checking custom method %s', check)
        if check in self.custom_methods:
            operation = getattr(self, check)

            if not arg:
                return operation(parent)
            return operation(parent, arg)

        return None

    # pylint: disable=too-many-branches,too-many-return-statements
    def get(self) -> typing.Any:
        """
        Processes GET method for a detail Handler
        """
        # Process args
        logger.debug('Detail args for GET: %s', self._args)
        nArgs = len(self._args)

        parent: models.Model = self._kwargs['parent']

        if nArgs == 0:
            return self.get_items(parent, None)

        # if has custom methods, look for if this request matches any of them
        r = self._check_is_custom_method(self._args[0], parent)
        if r is not None:
            return r

        if nArgs == 1:
            if self._args[0] == OVERVIEW:
                return self.get_items(parent, None)
            # if self._args[0] == GUI:
            #     gui = self.get_gui(parent, None)
            #     return sorted(gui, key=lambda f: f['gui']['order'])
            if self._args[0] == TYPES:
                types_ = self.get_types(parent, None)
                logger.debug('Types: %s', types_)
                return types_
            if self._args[0] == GUI:
                # Gui without type, valid
                gui = self.get_gui(parent, '')  # No type
                return sorted(gui, key=lambda f: f['gui']['order'])
            if self._args[0] == TABLEINFO:
                return self.process_table_fields(
                    self.get_title(parent),
                    self.get_fields(parent),
                    self.get_row_style(parent),
                )

            # try to get id
            return self.get_items(parent, process_uuid(self._args[0]))

        if nArgs == 2:
            if self._args[0] == GUI:
                gui = self.get_gui(parent, self._args[1])
                return sorted(gui, key=lambda f: f['gui']['order'])
            if self._args[0] == TYPES:
                types_ = self.get_types(parent, self._args[1])
                logger.debug('Types: %s', types_)
                return types_
            if self._args[1] == LOG:
                return self.get_logs(parent, self._args[0])

            r = self._check_is_custom_method(self._args[1], parent, self._args[0])
            if r is not None:
                return r

        return self.fallback_get()

    def put(self) -> typing.Any:
        """
        Process the "PUT" operation, making the correspondent checks.
        Evaluates if it is a new element or a "modify" operation (based on if it has parameter),
        and invokes "save_item" with parent & item (that can be None for a new Item)
        """
        logger.debug('Detail args for PUT: %s, %s', self._args, self._params)

        parent: models.Model = self._kwargs['parent']

        # Create new item unless 1 param received (the id of the item to modify)
        item = None
        if len(self._args) == 1:
            item = self._args[0]
        elif len(self._args) > 1:  # PUT expects 0 or 1 parameters. 0 == NEW, 1 = EDIT
            raise self.invalid_request_response()

        logger.debug('Invoking proper saving detail item %s', item)
        self.save_item(parent, item)
        # Empty response
        return rest_result(consts.OK)

    def post(self) -> typing.Any:
        """
        Process the "POST" operation
        Post can be used for, for example, testing.
        Right now is an invalid method for Detail elements
        """
        raise self.invalid_request_response('This method does not accepts POST')

    def delete(self) -> typing.Any:
        """
        Process the "DELETE" operation, making the correspondent checks.
        Extracts the item id and invokes delete_item with parent item and item id (uuid)
        """
        logger.debug('Detail args for DELETE: %s', self._args)

        parent = self._kwargs['parent']

        if len(self._args) != 1:
            raise self.invalid_request_response()

        self.delete_item(parent, self._args[0])

        return consts.OK

    def fallback_get(self) -> typing.Any:
        """
        Invoked if default get can't process request.
        Here derived classes can process "non default" (and so, not understood) GET constructions
        """
        raise self.invalid_request_response('Fallback invoked')

    # Override this to provide functionality
    # Default (as sample) get_items
    def get_items(self, parent: models.Model, item: typing.Optional[str]) -> types.rest.ManyItemsDictType:
        """
        This MUST be overridden by derived classes
        Excepts to return a list of dictionaries or a single dictionary, depending on "item" param
        If "item" param is None, ALL items are expected to be returned as a list of dictionaries
        If "Item" param has an id (normally an uuid), one item is expected to be returned as dictionary
        """
        # if item is None:  # Returns ALL detail items
        #     return []
        # return {}  # Returns one item
        raise NotImplementedError(f'Must provide an get_items method for {self.__class__} class')

    # Default save
    def save_item(self, parent: models.Model, item: typing.Optional[str]) -> None:
        """
        Invoked for a valid "put" operation
        If this method is not overridden, the detail class will not have "Save/modify" operations.
        Parameters (probably object fields) must be retrieved from "_params" member variable
        :param parent: Parent of this detail (parent DB Object)
        :param item: Item id (uuid)
        :return: Normally "success" is expected, but can throw any "exception"
        """
        logger.debug('Default save_item handler caller for %s', self._path)
        raise self.invalid_request_response()

    # Default delete
    def delete_item(self, parent: models.Model, item: str) -> None:
        """
        Invoked for a valid "delete" operation.
        If this method is not overriden, the detail class will not have "delete" operation.
        :param parent: Parent of this detail (parent DB Object)
        :param item: Item id (uuid)
        :return: Normally "success" is expected, but can throw any "exception"
        """
        raise self.invalid_request_response()

    # A detail handler must also return title & fields for tables
    def get_title(self, parent: models.Model) -> str:  # pylint: disable=no-self-use
        """
        A "generic" title for a view based on this detail.
        If not overridden, defaults to ''
        :param parent: Parent object
        :return: Expected to return an string that is the "title".
        """
        return ''

    def get_fields(self, parent: models.Model) -> list[typing.Any]:
        """
        A "generic" list of fields for a view based on this detail.
        If not overridden, defaults to emty list
        :param parent: Parent object
        :return: Expected to return a list of fields
        """
        return []

    def get_row_style(self, parent: models.Model) -> types.ui.RowStyleInfo:
        """
        A "generic" row style based on row field content.
        If not overridden, defaults to {}

        Args:
            parent (models.Model): Parent object

        Return:
            dict[str, typing.Any]: A dictionary with 'field' and 'prefix' keys
        """
        return types.ui.RowStyleInfo.null()

    def get_gui(self, parent: models.Model, forType: str) -> collections.abc.Iterable[typing.Any]:
        """
        Gets the gui that is needed in order to "edit/add" new items on this detail
        If not overriden, means that the detail has no edit/new Gui
        :param parent: Parent object
        :param forType: Type of object needing gui
        :return: a "gui" (list of gui fields)
        """
        # raise RequestError('Gui not provided for this type of object')
        return []

    def get_types(
        self, parent: models.Model, for_type: typing.Optional[str]
    ) -> collections.abc.Iterable[types.rest.TypeInfoDict]:
        """
        The default is that detail element will not have any types (they are "homogeneous")
        but we provided this method, that can be overridden, in case one detail needs it
        :param parent: Parent object
        :param forType: Request argument in fact
        :return: list of dictionaries describing type/types
        """
        return []  # Default is that details do not have types

    def get_logs(self, parent: models.Model, item: str) -> list[typing.Any]:
        """
        If the detail has any log associated with it items, provide it overriding this method
        :param parent:
        :param item:
        :return: a list of log elements (normally got using "uds.core.util.log.get_logs" method)
        """
        raise self.invalid_method_response()


class ModelHandler(BaseModelHandler):
    """
    Basic Handler for a model
    Basically we will need same operations for all models, so we can
    take advantage of this fact to not repeat same code again and again...

    Urls treated are:
    [path] --> Returns all elements for this path (including INSTANCE variables if it has it). (example: .../providers)
    [path]/overview --> Returns all elements for this path, not including INSTANCE variables. (example: .../providers/overview)
    [path]/ID --> Returns an exact element for this path. (example: .../providers/4)
    [path/ID/DETAIL --> Delegates to Detail, if it has details. (example: .../providers/4/services/overview, .../providers/5/services/9/gui, ....

    Note: Instance variables are the variables declared and serialized by modules.
          The only detail that has types within is "Service", child of "Provider"
    """

    # Authentication related
    authenticated = True
    needs_staff = True

    # Which model does this manage, must be a django model ofc
    model: 'typing.ClassVar[type[models.Model]]'
    # If the model is filtered (for overviews)
    model_filter: 'typing.ClassVar[typing.Optional[collections.abc.Mapping[str, typing.Any]]]' = None
    # Same, but for exclude
    model_exclude: 'typing.ClassVar[typing.Optional[collections.abc.Mapping[str, typing.Any]]]' = None

    # By default, filter is empty
    fltr: typing.Optional[str] = None

    # This is an array of tuples of two items, where first is method and second inticates if method needs parent id (normal behavior is it needs it)
    # For example ('services', True) -- > .../id_parent/services
    #             ('services', False) --> ..../services
    custom_methods: typing.ClassVar[list[tuple[str, bool]]] = (
        []
    )  # If this model respond to "custom" methods, we will declare them here
    # If this model has details, which ones
    detail: typing.ClassVar[typing.Optional[dict[str, type[DetailHandler]]]] = (
        None  # Dictionary containing detail routing
    )
    # Fields that are going to be saved directly
    # * If a field is in the form "field:default" and field is not present in the request, default will be used
    # * If the "default" is the string "None", then the default will be None
    # * If the "default" is _ (underscore), then the field will be ignored (not saved) if not present in the request
    # Note that these fields has to be present in the model, and they can be "edited" in the pre_save method
    save_fields: typing.ClassVar[list[str]] = []
    # Put removable fields before updating
    remove_fields: typing.ClassVar[list[str]] = []
    # Table info needed fields and title
    table_fields: typing.ClassVar[list[typing.Any]] = []
    table_row_style: typing.ClassVar[types.ui.RowStyleInfo] = types.ui.RowStyleInfo.null()
    table_title: typing.ClassVar[str] = ''
    table_subtitle: typing.ClassVar[str] = ''

    # This methods must be override, depending on what is provided

    # Data related
    def item_as_dict(self, item: models.Model) -> types.rest.ItemDictType:
        """
        Must be overriden by descendants.
        Expects the return of an item as a dictionary
        """
        return {}

    def item_as_dict_overview(self, item: models.Model) -> dict[str, typing.Any]:
        """
        Invoked when request is an "overview"
        default behavior is return item_as_dict
        """
        return self.item_as_dict(item)

    # types related
    def enum_types(self) -> collections.abc.Iterable[type['Module']]:  # override this
        """
        Must be overriden by desdencents if they support types
        Excpetcs the list of types that the handler supports
        """
        return []

    def get_types(
        self, *args: typing.Any, **kwargs: typing.Any
    ) -> typing.Generator[types.rest.TypeInfoDict, None, None]:
        for type_ in self.enum_types():
            yield self.type_as_dict(type_)

    def get_type(self, type_: str) -> types.rest.TypeInfoDict:
        found = None
        for v in self.get_types():
            if v['type'] == type_:
                found = v
                break

        if found is None:
            raise exceptions.rest.NotFound('type not found')

        logger.debug('Found type %s', found)
        return found

    # log related
    def get_logs(self, item: models.Model) -> list[dict[typing.Any, typing.Any]]:
        self.ensure_has_access(item, types.permissions.PermissionType.READ)
        try:
            return log.get_logs(item)
        except Exception as e:
            logger.warning('Exception getting logs for %s: %s', item, e)
            return []

    # gui related
    def get_gui(self, type_: str) -> list[typing.Any]:
        return []
        # raise self.invalidRequestException()

    # Delete related, checks if the item can be deleted
    # If it can't be so, raises an exception
    def validate_delete(self, item: models.Model) -> None:
        pass

    # Save related, checks if the item can be saved
    # If it can't be saved, raises an exception
    def validate_save(self, item: models.Model) -> None:
        pass

    # Invoked to possibily fix fields (or add new one, or check
    def pre_save(self, fields: dict[str, typing.Any]) -> None:
        pass

    # Invoked right after saved an item (no matter if new or edition)
    def post_save(self, item: models.Model) -> None:
        pass

    # End overridable

    def extract_filter(self) -> None:
        # Extract filter from params if present
        self.fltr = None
        if 'filter' in self._params:
            self.fltr = self._params['filter']
            del self._params['filter']  # Remove parameter
            logger.debug('Found a filter expression (%s)', self.fltr)

    def filter(self, data: typing.Any) -> typing.Any:
        # Right now, filtering only supports a single filter, in a future
        # we may improve it
        if self.fltr is None:
            return data

        # Filtering a non iterable (list or tuple)
        if not isinstance(data, (list, tuple, GeneratorType)):
            return data

        logger.debug('data: %s, fltr: %s', data, self.fltr)
        try:
            fld, pattern = self.fltr.split('=')
            s, e = '', ''
            if pattern[0] == '^':
                pattern = pattern[1:]
                s = '^'
            if pattern[-1] == '$':
                pattern = pattern[:-1]
                e = '$'

            r = re.compile(s + fnmatch.translate(pattern) + e, re.RegexFlag.IGNORECASE)

            def fltr_function(item: collections.abc.MutableMapping[str, typing.Any]) -> bool:
                try:
                    if fld not in item or r.match(item[fld]) is None:
                        return False
                except Exception:
                    return False
                return True

            res = list(filter(fltr_function, data))

            logger.debug('After filtering: %s', res)
            return res
        except Exception as e:
            logger.exception('Exception:')
            logger.info('Filtering expression %s is invalid!', self.fltr)
            raise exceptions.rest.RequestError(f'Filtering expression {self.fltr} is invalid') from e

    # Helper to process detail
    # Details can be managed (writen) by any user that has MANAGEMENT permission over parent
    def process_detail(self) -> typing.Any:
        logger.debug('Processing detail %s for with params %s', self._path, self._params)
        try:
            item: models.Model = self.model.objects.filter(uuid=self._args[0])[0]
            # If we do not have access to parent to, at least, read...

            if self._operation in ('put', 'post', 'delete'):
                requiredPermission = types.permissions.PermissionType.MANAGEMENT
            else:
                requiredPermission = types.permissions.PermissionType.READ

            if permissions.has_access(self._user, item, requiredPermission) is False:
                logger.debug(
                    'Permission for user %s does not comply with %s',
                    self._user,
                    requiredPermission,
                )
                raise self.access_denied_response()

            if not self.detail:
                raise self.invalid_request_response()

            # pylint: disable=unsubscriptable-object
            detailCls = self.detail[self._args[1]]
            args = list(self._args[2:])
            path = self._path + '/' + '/'.join(args[:2])
            detail = detailCls(self, path, self._params, *args, parent=item, user=self._user)
            method = getattr(detail, self._operation)

            return method()
        except IndexError as e:
            raise self.invalid_item_response() from e
        except (KeyError, AttributeError) as e:
            raise self.invalid_method_response() from e
        except exceptions.rest.HandlerError:
            raise
        except Exception as e:
            logger.error('Exception processing detail: %s', e)
            raise self.invalid_request_response() from e

    def get_items(
        self, *args: typing.Any, **kwargs: typing.Any
    ) -> typing.Generator[types.rest.ItemDictType, None, None]:
        if 'overview' in kwargs:
            overview = kwargs['overview']
            del kwargs['overview']
        else:
            overview = True

        if 'prefetch' in kwargs:
            prefetch = kwargs['prefetch']
            logger.debug('Prefetching %s', prefetch)
            del kwargs['prefetch']
        else:
            prefetch = []

        if 'query' in kwargs:
            query = kwargs['query']  # We are using a prebuilt query on args
            logger.debug('Got query: %s', query)
            del kwargs['query']
        else:
            logger.debug('Args: %s, kwargs: %s', args, kwargs)
            query = self.model.objects.filter(*args, **kwargs).prefetch_related(*prefetch)

        if self.model_filter is not None:
            query = query.filter(**self.model_filter)

        if self.model_exclude is not None:
            query = query.exclude(**self.model_exclude)

        for item in query:
            try:
                if (
                    permissions.has_access(
                        self._user,
                        item,
                        types.permissions.PermissionType.READ,
                    )
                    is False
                ):
                    continue
                if overview:
                    yield self.item_as_dict_overview(item)
                else:
                    res = self.item_as_dict(item)
                    self.fill_instance_fields(item, res)
                    yield res
            except Exception as e:  # maybe an exception is thrown to skip an item
                logger.debug('Got exception processing item from model: %s', e)
                # logger.exception('Exception getting item from {0}'.format(self.model))

    def get(self) -> typing.Any:
        """
        Wraps real get method so we can process filters if they exists
        """
        # Extract filter from params if present
        self.extract_filter()
        return self.filter(self.process_get())

    #  pylint: disable=too-many-return-statements
    def process_get(self) -> typing.Any:
        logger.debug('method GET for %s, %s', self.__class__.__name__, self._args)
        nArgs = len(self._args)

        if nArgs == 0:
            return list(self.get_items(overview=False))

        # if has custom methods, look for if this request matches any of them
        for cm in self.custom_methods:
            if nArgs > 1 and cm[1] is True:  # Method needs parent (existing item)
                if self._args[1] == cm[0]:
                    item = operation = None
                    try:
                        operation = getattr(self, self._args[1])
                        item = self.model.objects.get(uuid=self._args[0].lower())
                    except Exception as e:
                        logger.error(
                            'Invalid custom method exception %s/%s/%s: %s',
                            self.__class__.__name__,
                            self._args,
                            self._params,
                            e,
                        )
                        raise self.invalid_method_response()

                    return operation(item)

            elif self._args[0] == cm[0]:
                operation = None
                try:
                    operation = getattr(self, self._args[0])
                except Exception as e:
                    raise self.invalid_method_response() from e

                return operation()

        if nArgs == 1:
            if self._args[0] == OVERVIEW:
                return list(self.get_items())
            if self._args[0] == TYPES:
                return list(self.get_types())
            if self._args[0] == TABLEINFO:
                return self.process_table_fields(
                    self.table_title,
                    self.table_fields,
                    self.table_row_style,
                    self.table_subtitle,
                )
            if self._args[0] == GUI:
                return self.get_gui('')

            # get item ID
            try:
                item = self.model.objects.get(uuid=self._args[0].lower())

                self.ensure_has_access(item, types.permissions.PermissionType.READ)

                res = self.item_as_dict(item)
                self.fill_instance_fields(item, res)
                return res
            except Exception as e:
                logger.exception('Got Exception looking for item')
                raise self.invalid_item_response() from e

        # nArgs > 1
        # Request type info or gui, or detail
        if self._args[0] == OVERVIEW:
            if nArgs != 2:
                raise self.invalid_request_response()
        elif self._args[0] == TYPES:
            if nArgs != 2:
                raise self.invalid_request_response()
            return self.get_type(self._args[1])
        elif self._args[0] == GUI:
            if nArgs != 2:
                raise self.invalid_request_response()
            gui = self.get_gui(self._args[1])
            return sorted(gui, key=lambda f: f['gui']['order'])
        elif self._args[1] == LOG:
            if nArgs != 2:
                raise self.invalid_request_response()
            try:
                # DB maybe case sensitive??, anyway, uuids are stored in lowercase
                item = self.model.objects.get(
                    uuid=self._args[0].lower()
                )
                return self.get_logs(item)
            except Exception as e:
                raise self.invalid_item_response() from e

        # If has detail and is requesting detail
        if self.detail is not None:
            return self.process_detail()

        raise self.invalid_request_response()  # Will not return

    def post(self) -> typing.Any:
        """
        Processes a POST request
        """
        # right now
        logger.debug('method POST for %s, %s', self.__class__.__name__, self._args)
        if len(self._args) == 2:
            if self._args[0] == 'test':
                return self.test(self._args[1])

        raise self.invalid_method_response()  # Will not return

    def put(self) -> typing.Any:
        """
        Processes a PUT request
        """
        logger.debug('method PUT for %s, %s', self.__class__.__name__, self._args)

        # Append request to _params, may be needed by some classes
        # I.e. to get the user IP, server name, etc..
        self._params['_request'] = self._request

        deleteOnError = False

        if len(self._args) > 1:  # Detail?
            return self.process_detail()

        # Here, self.model() indicates an "django model object with default params"
        self.ensure_has_access(
            self.model(), types.permissions.PermissionType.ALL, root=True
        )  # Must have write permissions to create, modify, etc..

        try:
            # Extract fields
            args = self.fields_from_params(self.save_fields)
            logger.debug('Args: %s', args)
            self.pre_save(args)
            # If tags is in save fields, treat it "specially"
            if 'tags' in self.save_fields:
                tags = args['tags']
                del args['tags']
            else:
                tags = None

            deleteOnError = False
            item: models.Model
            if not self._args:  # create new?
                item = self.model.objects.create(**args)
                deleteOnError = True
            else:  # Must have 1 arg
                # We have to take care with this case, update will efectively update records on db
                item = self.model.objects.get(uuid=self._args[0].lower())
                for v in self.remove_fields:
                    if v in args:
                        del args[v]
                # Upadte fields from args
                for k, v in args.items():
                    setattr(item, k, v)

            # Now if tags, update them
            if isinstance(item, TaggingMixin):
                if tags:
                    logger.debug('Updating tags: %s', tags)
                    item.tags.set([Tag.objects.get_or_create(tag=val)[0] for val in tags if val != ''])
                elif isinstance(tags, list):  # Present, but list is empty (will be proccesed on "if" else)
                    item.tags.clear()

            if not deleteOnError:
                self.validate_save(
                    item
                )  # Will raise an exception if item can't be saved (only for modify operations..)

            # Store associated object if requested (data_type)
            try:
                if isinstance(item, ManagedObjectModel):
                    data_type: typing.Optional[str] = self._params.get('data_type', self._params.get('type'))
                    if data_type:
                        item.data_type = data_type
                        item.data = item.get_instance(self._params).serialize()

                item.save()

                res = self.item_as_dict(item)
                self.fill_instance_fields(item, res)
            except Exception:
                logger.exception('Exception on put')
                if deleteOnError:
                    item.delete()
                raise

            self.post_save(item)

            return res

        except self.model.DoesNotExist:
            raise exceptions.rest.NotFound('Item not found') from None
        except IntegrityError:  # Duplicate key probably
            raise exceptions.rest.RequestError('Element already exists (duplicate key error)') from None
        except (exceptions.rest.SaveException, exceptions.ui.ValidationError) as e:
            raise exceptions.rest.RequestError(str(e)) from e
        except (exceptions.rest.RequestError, exceptions.rest.ResponseError):
            raise
        except Exception as e:
            logger.exception('Exception on put')
            raise exceptions.rest.RequestError('incorrect invocation to PUT') from e

    def delete(self) -> typing.Any:
        """
        Processes a DELETE request
        """
        logger.debug('method DELETE for %s, %s', self.__class__.__name__, self._args)
        if len(self._args) > 1:
            return self.process_detail()

        if len(self._args) != 1:
            raise exceptions.rest.RequestError('Delete need one and only one argument')

        self.ensure_has_access(
            self.model(), types.permissions.PermissionType.ALL, root=True
        )  # Must have write permissions to delete

        try:
            item = self.model.objects.get(uuid=self._args[0].lower())
            self.validate_delete(item)
            self.delete_item(item)
        except self.model.DoesNotExist:
            raise exceptions.rest.NotFound('Element do not exists') from None

        return consts.OK

    def delete_item(self, item: models.Model) -> None:
        """
        Basic, overridable method for deleting an item
        """
        item.delete()
