# -*- coding: utf-8 -*-
#
# Copyright (c) 2014-2019 Virtual Cable S.L.
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

"""
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
# pylint: disable=too-many-public-methods

import fnmatch
import re
import types
import typing

import logging

from django.utils.translation import ugettext as _
from django.db import IntegrityError, models

from uds.core.ui import gui as uiGui
from uds.core.util import log
from uds.core.util import permissions
from uds.core.util.model import processUuid
from uds.models import Tag

from .handlers import (
    Handler,
    HandlerError,
    NotFound,
    RequestError,
    ResponseError,
    AccessDenied,
    NotSupportedError
)

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.models.managed_object_model import ManagedObjectModel
    from uds.models import User
    from uds.core import Module

logger = logging.getLogger(__name__)

# a few constants
OVERVIEW = 'overview'
TYPES = 'types'
TABLEINFO = 'tableinfo'
GUI = 'gui'
LOG = 'log'

OK = 'ok'  # Constant to be returned when result is just "operation complete successfully"

# Exception to "rethrow" on save error
class SaveException(HandlerError):
    """
    Exception thrown if couldn't save
    """

class BaseModelHandler(Handler):
    """
    Base Handler for Master & Detail Handlers
    """

    def addField(self, gui: typing.List[typing.Any], field: typing.Dict[str, typing.Any]) -> typing.List[typing.Any]:
        """
        Add a field to a "gui" description.
        This method checks that every required field element is in there.
        If not, defaults are assigned
        :param gui: List of "gui" items where the field will be added
        :param field: Field to be added (dictionary)
        """
        v = {
            'name': field.get('name', ''),
            'value': '',
            'gui': {
                'required': field.get('required', False),
                'defvalue': field.get('value', ''),
                'value': field.get('value', ''),
                'minValue': field.get('minValue', '987654321'),
                'label': field.get('label', ''),
                'length': field.get('length', 128),
                'multiline': field.get('multiline', 0),
                'tooltip': field.get('tooltip', ''),
                'rdonly': field.get('rdonly', False),
                'type': field.get('type', uiGui.InputField.TEXT_TYPE),
                'order': field.get('order', 0),
                'values': field.get('values', [])
            }
        }
        if 'tab' in field:
            v['gui']['tab'] = field['tab']
        gui.append(v)
        return gui

    def addDefaultFields(self, gui: typing.List[typing.Any], flds: typing.List[str]) -> typing.List[typing.Any]:
        """
        Adds default fields (based in a list) to a "gui" description
        :param gui: Gui list where the "default" fielsds will be added
        :param flds: List of fields names requested to be added. Valid values are 'name', 'comments',
                    'priority' and 'small_name', 'short_name', 'tags'
        """
        if 'tags' in flds:
            self.addField(gui, {
                'name': 'tags',
                'label': _('Tags'),
                'type': 'taglist',
                'tooltip': _('Tags for this element'),
                'order': 0 - 105,
            })
        if 'name' in flds:
            self.addField(gui, {
                'name': 'name',
                'required': True,
                'label': _('Name'),
                'length': 128,
                'tooltip': _('Name of this element'),
                'order': 0 - 100,
            })
        if 'short_name' in flds:
            self.addField(gui, {
                'name': 'short_name',
                'type': 'text',
                'label': _('Short name'),
                'tooltip': _('Short name for user service visualization'),
                'required': False,
                'length': 16,
                'order': 0 - 95,
            })
        if 'comments' in flds:
            self.addField(gui, {
                'name': 'comments',
                'label': _('Comments'),
                'tooltip': _('Comments for this element'),
                'length': 256,
                'order': 0 - 90,
            })
        if 'priority' in flds:
            self.addField(gui, {
                'name': 'priority',
                'type': 'numeric',
                'label': _('Priority'),
                'tooltip': _('Selects the priority of this element (lower number means higher priority)'),
                'required': True,
                'value': 1,
                'length': 4,
                'order': 0 - 85,
            })
        if 'small_name' in flds:
            self.addField(gui, {
                'name': 'small_name',
                'type': 'text',
                'label': _('Label'),
                'tooltip': _('Label for this element'),
                'required': True,
                'length': 128,
                'order': 0 - 80,
            })

        return gui

    def ensureAccess(self, obj: models.Model, permission: int, root: bool = False) -> int:
        perm = permissions.getEffectivePermission(self._user, obj, root)
        if perm < permission:
            raise self.accessDenied()
        return perm

    def typeInfo(self, type_: typing.Type['Module']) -> typing.Dict[str, typing.Any]:
        """
        Returns info about the type
        In fact, right now, it returns an empty dict, that will be extended by typeAsDict
        """
        return {}

    def typeAsDict(self, type_: typing.Type['Module']) -> typing.Dict[str, typing.Any]:
        """
        Returns a dictionary describing the type (the name, the icon, description, etc...)
        """
        res = self.typeInfo(type_)
        res.update({
            'name': _(type_.name()),
            'type': type_.type(),
            'description': _(type_.description()),
            'icon': type_.icon64().replace('\n', '')
        })
        if hasattr(type_, 'group'):
            res['group'] = _(type_.group)  # Add group info is it is contained
        return res

    def processTableFields(
            self,
            title: str,
            fields: typing.List[typing.Any],
            row_style: typing.Dict[str, typing.Any],
            subtitle: typing.Optional[str] = None
        ) -> typing.Dict[str, typing.Any]:
        """
        Returns a dict containing the table fields description
        """
        return {
            'title': title,
            'fields': fields,
            'row-style': row_style,
            'subtitle': subtitle or ''
        }

    def readFieldsFromParams(self, fldList: typing.List[str]) -> typing.Dict[str, typing.Any]:
        """
        Reads the indicated fields from the parameters received, and if
        :param fldList: List of required fields
        :return: A dictionary containing all required fields
        """
        args: typing.Dict[str, str] = {}
        try:
            for key in fldList:
                args[key] = self._params[key]
                del self._params[key]
        except KeyError as e:
            raise RequestError('needed parameter not found in data {0}'.format(e))

        return args

    def fillIntanceFields(self, item: 'ManagedObjectModel', res: typing.Dict[str, typing.Any]) -> typing.Dict[str, typing.Any]:
        """
        For Managed Objects (db element that contains a serialized object), fills a dictionary with the "field" parameters values.
        For non managed objects, it does nothing
        :param item: Item to extract fields
        :param res: Dictionary to "extend" with instance key-values pairs
        """
        if hasattr(item, 'getInstance'):
            i = item.getInstance()
            i.initGui()  # Defaults & stuff
            value: typing.Any
            for key, value in i.valuesDict().items():
                if isinstance(value, str):
                    value = {"true": True, "false": False}.get(value, value)  # Translate "true" & "false" to True & False (booleans)
                logger.debug('%s = %s', key, value)
                res[key] = value
        return res

    # Exceptions
    def invalidRequestException(self, message: typing.Optional[str] = None) -> HandlerError:
        """
        Raises an invalid request error with a default translated string
        :param message: Custom message to add to exception. If it is None, "Invalid Request" is used
        """
        message = message or _('Invalid Request')
        return RequestError('{} {}: {}'.format(message, self.__class__, self._args))

    def invalidResponseException(self, message: typing.Optional[str] = None) -> HandlerError:
        message = 'Invalid response' if message is None else message
        return ResponseError(message)

    def invalidMethodException(self) -> HandlerError:
        """
        Raises a NotFound exception with translated "Method not found" string to current locale
        """
        return RequestError(_('Method not found in {}: {}').format(self.__class__, self._args))

    def invalidItemException(self, message: typing.Optional[str] = None) -> HandlerError:
        """
        Raises a NotFound exception, with location info
        """
        message = message or _('Item not found')
        return NotFound(message)
        # raise NotFound('{} {}: {}'.format(message, self.__class__, self._args))

    def accessDenied(self, message: typing.Optional[str] = None) -> HandlerError:
        return AccessDenied(message or _('Access denied'))

    def notSupported(self, message: typing.Optional[str] = None) -> HandlerError:
        return NotSupportedError(message or _('Operation not supported'))

    # Success methods
    def success(self) -> str:
        """
        Utility method to be invoked for simple methods that returns nothing in fact
        """
        logger.debug('Returning success on %s %s', self.__class__, self._args)
        return OK

    def test(self, type_: str):
        """
        Invokes a test for an item
        """
        logger.debug('Called base test for %s --> %s', self.__class__.__name__, self._params)
        raise self.invalidMethodException()


# Details do not have types at all
# so, right now, we only process details petitions for Handling & tables info
# noinspection PyMissingConstructor
class DetailHandler(BaseModelHandler):
    """
    Detail handler (for relations such as provider-->services, authenticators-->users,groups, deployed services-->cache,assigned, groups, transports
    Urls recognized for GET are:
    [path] --> get Items (all items, this call is delegated to getItems)
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
    custom_methods: typing.ClassVar[typing.List[str]] = []
    _parent: typing.Optional['ModelHandler']
    _path: str
    _params: typing.Any  # _params is deserialized object from request
    _args: typing.Tuple[str, ...]
    _kwargs: typing.Dict[str, typing.Any]
    _user: 'User'

    def __init__(
            self,
            parentHandler: 'ModelHandler',
            path: str,
            params: typing.Any,
            *args: str,
            **kwargs: typing.Any
        ):  # pylint: disable=super-init-not-called
        """
        Detail Handlers in fact "disabled" handler most initialization, that is no needed because
        parent modelhandler has already done it (so we must access through parent handler)
        """
        # Parent init not invoked because their methos are not used on detail handlers (only on parent handlers..)
        self._parent = parentHandler
        self._path = path
        self._params = params
        self._args = args
        self._kwargs = kwargs
        self._user = kwargs.get('user', None)

    def __checkCustom(self, check: str, parent: models.Model, arg: typing.Any = None) -> typing.Any:
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

    def get(self) -> typing.Any:  # pylint: disable=too-many-branches,too-many-return-statements
        """
        Processes GET method for a detail Handler
        """
        # Process args
        logger.debug('Detail args for GET: %s', self._args)
        nArgs = len(self._args)

        parent: models.Model = self._kwargs['parent']

        if nArgs == 0:
            return self.getItems(parent, None)

        # if has custom methods, look for if this request matches any of them
        r = self.__checkCustom(self._args[0], parent)
        if r is not None:
            return r

        if nArgs == 1:
            if self._args[0] == OVERVIEW:
                return self.getItems(parent, None)
            # if self._args[0] == GUI:
            #     gui = self.getGui(parent, None)
            #     return sorted(gui, key=lambda f: f['gui']['order'])
            if self._args[0] == TYPES:
                types_ = self.getTypes(parent, None)
                logger.debug('Types: %s', types_)
                return types_
            if self._args[0] == TABLEINFO:
                return self.processTableFields(self.getTitle(parent), self.getFields(parent), self.getRowStyle(parent))

            # try to get id
            return self.getItems(parent, processUuid(self._args[0]))

        if nArgs == 2:
            if self._args[0] == GUI:
                gui = self.getGui(parent, self._args[1])
                return sorted(gui, key=lambda f: f['gui']['order'])
            if self._args[0] == TYPES:
                types_ = self.getTypes(parent, self._args[1])
                logger.debug('Types: %s', types_)
                return types_
            if self._args[1] == LOG:
                return self.getLogs(parent, self._args[0])

            r = self.__checkCustom(self._args[1], parent, self._args[0])
            if r is not None:
                return r

        return self.fallbackGet()

    def put(self) -> typing.Any:
        """
        Process the "PUT" operation, making the correspondent checks.
        Evaluates if it is a new element or a "modify" operation (based on if it has parameter),
        and invokes "saveItem" with parent & item (that can be None for a new Item)
        """
        logger.debug('Detail args for PUT: %s, %s', self._args, self._params)

        parent: models.Model = self._kwargs['parent']

        # Create new item unless 1 param received (the id of the item to modify)
        item = None
        if len(self._args) == 1:
            item = self._args[0]
        elif len(self._args) > 1:  # PUT expects 0 or 1 parameters. 0 == NEW, 1 = EDIT
            raise self.invalidRequestException()

        logger.debug('Invoking proper saving detail item %s', item)
        return self.saveItem(parent, item)

    def post(self) -> typing.Any:
        """
        Process the "POST" operation
        Post can be used for, for example, testing.
        Right now is an invalid method for Detail elements
        """
        raise self.invalidRequestException('This method does not accepts POST')

    def delete(self) -> typing.Any:
        """
        Process the "DELETE" operation, making the correspondent checks.
        Extracts the item id and invokes deleteItem with parent item and item id (uuid)
        """
        logger.debug('Detail args for DELETE: %s', self._args)

        parent = self._kwargs['parent']

        if len(self._args) != 1:
            raise self.invalidRequestException()

        self.deleteItem(parent, self._args[0])

        return OK

    def fallbackGet(self) -> typing.Any:
        """
        Invoked if default get can't process request.
        Here derived classes can process "non default" (and so, not understood) GET constructions
        """
        raise self.invalidRequestException('Fallback invoked')

    # Override this to provide functionality
    # Default (as sample) getItems
    def getItems(self, parent: models.Model, item: typing.Optional[str]):
        """
        This MUST be overridden by derived classes
        Excepts to return a list of dictionaries or a single dictionary, depending on "item" param
        If "item" param is None, ALL items are expected to be returned as a list of dictionaries
        If "Item" param has an id (normally an uuid), one item is expected to be returned as dictionary
        """
        # if item is None:  # Returns ALL detail items
        #     return []
        # return {}  # Returns one item
        raise NotImplementedError('Must provide an getItems method for {} class'.format(self.__class__))

    # Default save
    def saveItem(self, parent: models.Model, item: typing.Optional[str]) -> None:
        """
        Invoked for a valid "put" operation
        If this method is not overridden, the detail class will not have "Save/modify" operations.
        Parameters (probably object fields) must be retrieved from "_params" member variable
        :param parent: Parent of this detail (parent DB Object)
        :param item: Item id (uuid)
        :return: Normally "success" is expected, but can throw any "exception"
        """
        logger.debug('Default saveItem handler caller for %s', self._path)
        raise self.invalidRequestException()

    # Default delete
    def deleteItem(self, parent: models.Model, item: str) -> None:
        """
        Invoked for a valid "delete" operation.
        If this method is not overriden, the detail class will not have "delete" operation.
        :param parent: Parent of this detail (parent DB Object)
        :param item: Item id (uuid)
        :return: Normally "success" is expected, but can throw any "exception"
        """
        raise self.invalidRequestException()

    # A detail handler must also return title & fields for tables
    def getTitle(self, parent: models.Model) -> str:  # pylint: disable=no-self-use
        """
        A "generic" title for a view based on this detail.
        If not overridden, defaults to ''
        :param parent: Parent object
        :return: Expected to return an string that is the "title".
        """
        return ''

    def getFields(self, parent: models.Model) -> typing.List[typing.Any]:
        """
        A "generic" list of fields for a view based on this detail.
        If not overridden, defaults to emty list
        :param parent: Parent object
        :return: Expected to return a list of fields
        """
        return []

    def getRowStyle(self, parent: models.Model) -> typing.Dict[str, typing.Any]:
        """
        A "generic" row style based on row field content.
        If not overridden, defaults to {}
        :param parent: Parent object
        :return: Expected to return a dictionary that contains 'field' & 'prefix' fields
        """
        return {}

    def getGui(self, parent: models.Model, forType: str) -> typing.Iterable[typing.Any]:
        """
        Gets the gui that is needed in order to "edit/add" new items on this detail
        If not overriden, means that the detail has no edit/new Gui
        :param parent: Parent object
        :param forType: Type of object needing gui
        :return: a "gui" (list of gui fields)
        """
        # raise RequestError('Gui not provided for this type of object')
        return []

    def getTypes(self, parent: models.Model, forType: typing.Optional[str]) -> typing.Iterable[typing.Dict[str, typing.Any]]:
        """
        The default is that detail element will not have any types (they are "homogeneous")
        but we provided this method, that can be overridden, in case one detail needs it
        :param parent: Parent object
        :param forType: Request argument in fact
        :return: list of dictionaries describing type/types
        """
        return []  # Default is that details do not have types

    def getLogs(self, parent: models.Model, item: str):
        """
        If the detail has any log associated with it items, provide it overriding this method
        :param parent:
        :param item:
        :return: a list of log elements (normally got using "uds.core.util.log.getLogs" method)
        """
        raise self.invalidMethodException()


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
    model: typing.ClassVar[models.Model]

    # By default, filter is empty
    fltr: typing.Optional[str] = None

    # This is an array of tuples of two items, where first is method and second inticates if method needs parent id (normal behavior is it needs it)
    # For example ('services', True) -- > .../id_parent/services
    #             ('services', False) --> ..../services
    custom_methods: typing.ClassVar[typing.List[typing.Tuple[str, bool]]] = []  # If this model respond to "custom" methods, we will declare them here
    # If this model has details, which ones
    detail: typing.ClassVar[typing.Optional[typing.Dict[str, typing.Type[DetailHandler]]]] = None  # Dictionary containing detail routing
    # Put needed fields
    save_fields: typing.ClassVar[typing.List[str]] = []
    # Put removable fields before updating
    remove_fields: typing.ClassVar[typing.List[str]] = []
    # Table info needed fields and title
    table_fields: typing.ClassVar[typing.List[typing.Any]] = []
    table_row_style: typing.ClassVar[typing.Dict] = {}
    table_title: typing.ClassVar[str] = ''
    table_subtitle: typing.ClassVar[str] = ''

    # This methods must be override, depending on what is provided

    # Data related
    def item_as_dict(self, item: models.Model) -> typing.Dict[str, typing.Any]:
        """
        Must be overriden by descendants.
        Expects the return of an item as a dictionary
        """
        return {}

    def item_as_dict_overview(self, item: models.Model) -> typing.Dict[str, typing.Any]:
        """
        Invoked when request is an "overview"
        default behavior is return item_as_dict
        """
        return self.item_as_dict(item)

    # types related
    def enum_types(self) -> typing.Iterable[typing.Type['Module']]:  # override this
        """
        Must be overriden by desdencents if they support types
        Excpetcs the list of types that the handler supports
        """
        return []

    def getTypes(self, *args, **kwargs):
        for type_ in self.enum_types():
            yield self.typeAsDict(type_)

    def getType(self, type_: str) -> typing.Dict[str, typing.Any]:
        found = None
        for v in self.getTypes():
            if v['type'] == type_:
                found = v
                break

        if found is None:
            raise NotFound('type not found')

        logger.debug('Found type %s', found)
        return found

    # log related
    def getLogs(self, item: models.Model) -> typing.List[typing.Dict]:
        self.ensureAccess(item, permissions.PERMISSION_READ)
        try:
            return log.getLogs(item)
        except Exception as e:
            logger.warning('Exception getting logs for %s: %s', item, e)
            return []

    # gui related
    def getGui(self, type_: str) -> typing.List[typing.Any]:
        return []
        # raise self.invalidRequestException()

    # Delete related, checks if the item can be deleted
    # If it can't be so, raises an exception
    def checkDelete(self, item: models.Model) -> None:
        pass

    # Save related, checks if the item can be saved
    # If it can't be saved, raises an exception
    def checkSave(self, item: models.Model) -> None:
        pass

    # Invoked to possibily fix fields (or add new one, or check
    def beforeSave(self, fields: typing.Dict[str, typing.Any]) -> None:
        pass

    # Invoked right after saved an item (no matter if new or edition)
    def afterSave(self, item: models.Model) -> None:
        pass

    # End overridable

    def extractFilter(self) -> None:
        # Extract filter from params if present
        self.fltr = None
        if 'filter' in self._params:
            self.fltr = self._params['filter']
            del self._params['filter']  # Remove parameter
            logger.debug('Found a filter expression (%s)', self.fltr)

    def doFilter(self, data: typing.List[typing.Dict[str, typing.Any]]) -> typing.List[typing.Dict[str, typing.Any]]:
        # Right now, filtering only supports a single filter, in a future
        # we may improve it
        if self.fltr is None:
            return data

        # Filtering a non iterable (list or tuple)
        if not isinstance(data, (list, tuple, types.GeneratorType)):
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

            def fltr_function(item: typing.Dict[str, typing.Any]):
                try:
                    if fld not in item or r.match(item[fld]) is None:
                        return False
                except Exception:
                    return False
                return True

            res = list(filter(fltr_function, data))

            logger.debug('After filtering: %s', res)
            return res
        except:
            logger.exception('Exception:')
            logger.info('Filtering expression %s is invalid!', self.fltr)
            raise RequestError('Filtering expression {} is invalid'.format(self.fltr))

    # Helper to process detail
    # Details can be managed (writen) by any user that has MANAGEMENT permission over parent
    def processDetail(self):
        logger.debug('Processing detail %s for with params %s', self._path, self._params)
        try:
            item: models.Model = self.model.objects.filter(uuid=self._args[0])[0]
            # If we do not have access to parent to, at least, read...

            if self._operation in ('put', 'post', 'delete'):
                requiredPermission = permissions.PERMISSION_MANAGEMENT
            else:
                requiredPermission = permissions.PERMISSION_READ

            if permissions.checkPermissions(self._user, item, requiredPermission) is False:
                logger.debug('Permission for user %s does not comply with %s', self._user, requiredPermission)
                raise self.accessDenied()

            detailCls = self.detail[self._args[1]]  # pylint: disable=unsubscriptable-object
            args = list(self._args[2:])
            path = self._path + '/'.join(args[:2])
            detail = detailCls(self, path, self._params, *args, parent=item, user=self._user)
            method = getattr(detail, self._operation)

            return method()
        except KeyError:
            raise self.invalidMethodException()
        except AttributeError:
            raise self.invalidMethodException()

        raise Exception('Invalid code executed on processDetail')

    def getItems(self, *args, **kwargs) -> typing.Generator[typing.Dict[str, typing.Any], None, None]:
        for item in self.model.objects.filter(*args, **kwargs):
            try:
                if permissions.checkPermissions(typing.cast('User', self._user), item, permissions.PERMISSION_READ) is False:
                    continue
                if kwargs.get('overview', True):
                    yield self.item_as_dict_overview(item)
                else:
                    res = self.item_as_dict(item)
                    self.fillIntanceFields(item, res)
                    yield res
            except Exception:  # maybe an exception is thrown to skip an item
                # logger.exception('Exception getting item from {0}'.format(self.model))
                pass

    def get(self) -> typing.Any:
        """
        Wraps real get method so we can process filters if they exists
        """
        # Extract filter from params if present
        self.extractFilter()
        return self.doFilter(self.doGet())

    def doGet(self):  # pylint: disable=too-many-statements,too-many-branches,too-many-return-statements
        logger.debug('method GET for %s, %s', self.__class__.__name__, self._args)
        nArgs = len(self._args)

        if nArgs == 0:
            return list(self.getItems(overview=False))

        # if has custom methods, look for if this request matches any of them
        for cm in self.custom_methods:
            if nArgs > 1 and cm[1] is True:  # Method needs parent (existing item)
                if self._args[1] == cm[0]:
                    item = operation = None
                    try:
                        operation = getattr(self, self._args[1])
                        item = self.model.objects.get(uuid=self._args[0].lower())
                    except Exception as e:
                        logger.error('Invalid custom method exception %s/%s/%s: %s', self.__class__.__name__, self._args, self._params, e)
                        raise self.invalidMethodException()

                    return operation(item)

            elif self._args[0] == cm[0]:
                operation = None
                try:
                    operation = getattr(self, self._args[0])
                except Exception:
                    raise self.invalidMethodException()

                return operation()

        if nArgs == 1:
            if self._args[0] == OVERVIEW:
                return list(self.getItems())
            if self._args[0] == TYPES:
                return list(self.getTypes())
            if self._args[0] == TABLEINFO:
                return self.processTableFields(self.table_title, self.table_fields, self.table_row_style, self.table_subtitle)
            if self._args[0] == GUI:
                return self.getGui(None)

            # get item ID
            try:
                val = self.model.objects.get(uuid=self._args[0].lower())

                self.ensureAccess(val, permissions.PERMISSION_READ)

                res = self.item_as_dict(val)
                self.fillIntanceFields(val, res)
                return res
            except Exception:
                logger.exception('Got Exception looking for item')
                raise self.invalidItemException()

        # nArgs > 1
        # Request type info or gui, or detail
        if self._args[0] == OVERVIEW:
            if nArgs != 2:
                raise self.invalidRequestException()
        elif self._args[0] == TYPES:
            if nArgs != 2:
                raise self.invalidRequestException()
            return self.getType(self._args[1])
        elif self._args[0] == GUI:
            if nArgs != 2:
                raise self.invalidRequestException()
            gui = self.getGui(self._args[1])
            return sorted(gui, key=lambda f: f['gui']['order'])
        elif self._args[1] == LOG:
            if nArgs != 2:
                raise self.invalidRequestException()
            try:
                item = self.model.objects.get(uuid=self._args[0].lower())  # DB maybe case sensitive??, anyway, uuids are stored in lowercase
                return self.getLogs(item)
            except Exception:
                raise self.invalidItemException()

        # If has detail and is requesting detail
        if self.detail is not None:
            return self.processDetail()

        raise self.invalidRequestException()  # Will not return


    def post(self):
        """
        Processes a POST request
        """
        # right now
        logger.debug('method POST for %s, %s', self.__class__.__name__, self._args)
        if len(self._args) == 2:
            if self._args[0] == 'test':
                return self.test(self._args[1])

        raise self.invalidMethodException()  # Will not return

    def put(self):  # pylint: disable=too-many-branches, too-many-statements
        """
        Processes a PUT request
        """
        logger.debug('method PUT for %s, %s', self.__class__.__name__, self._args)
        self._params['_request'] = self._request

        deleteOnError = False

        if len(self._args) > 1:  # Detail?
            return self.processDetail()

        self.ensureAccess(self.model(), permissions.PERMISSION_ALL, root=True)  # Must have write permissions to create, modify, etc..

        try:
            # Extract fields
            args = self.readFieldsFromParams(self.save_fields)
            logger.debug('Args: %s', args)
            self.beforeSave(args)
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
                item.__dict__.update(args)  # Update fields from args

            # Now if tags, update them
            if tags:
                logger.debug('Updating tags: %s', tags)
                item.tags.set([Tag.objects.get_or_create(tag=val)[0] for val in tags if val != ''])

        except self.model.DoesNotExist:
            raise NotFound('Item not found')
        except IntegrityError:  # Duplicate key probably
            raise RequestError('Element already exists (duplicate key error)')
        except SaveException as e:
            raise RequestError(str(e))
        except (RequestError, ResponseError):
            raise
        except Exception:
            logger.exception('Exception on put')
            raise RequestError('incorrect invocation to PUT')

        if not deleteOnError:
            self.checkSave(item)  # Will raise an exception if item can't be saved (only for modify operations..)

        # Store associated object if requested (data_type)
        try:
            data_type: typing.Optional[str] = self._params.get('data_type', self._params.get('type'))
            if data_type:
                item.data_type = data_type
                item.data = item.getInstance(self._params).serialize()

            item.save()

            res = self.item_as_dict(item)
            self.fillIntanceFields(item, res)
        except:
            if deleteOnError:
                item.delete()
            raise

        self.afterSave(item)

        return res

    def delete(self) -> str:
        """
        Processes a DELETE request
        """
        logger.debug('method DELETE for %s, %s', self.__class__.__name__, self._args)
        if len(self._args) > 1:
            return self.processDetail()

        if len(self._args) != 1:
            raise RequestError('Delete need one and only one argument')

        self.ensureAccess(self.model(), permissions.PERMISSION_ALL, root=True)  # Must have write permissions to delete

        try:
            item = self.model.objects.get(uuid=self._args[0].lower())
            self.checkDelete(item)
            self.deleteItem(item)
        except self.model.DoesNotExist:
            raise NotFound('Element do not exists')

        return OK

    def deleteItem(self, item: models.Model) -> None:
        """
        Basic, overridable method for deleting an item
        """
        item.delete()
