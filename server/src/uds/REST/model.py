# -*- coding: utf-8 -*-
#
# Copyright (c) 2014 Virtual Cable S.L.
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

from __future__ import unicode_literals

from uds.REST.handlers import NotFound, RequestError, ResponseError, AccessDenied, NotSupportedError
from django.utils.translation import ugettext as _
from django.db import IntegrityError

from uds.core.ui.UserInterface import gui as uiGui
from uds.REST.handlers import Handler, HandlerError
from uds.core.util import log
from uds.core.util import permissions
from uds.core.util.model import processUuid
from uds.models import Tag

import six
from six.moves import filter  # @UnresolvedImport
import fnmatch
import re
import types

import logging

logger = logging.getLogger(__name__)

__updated__ = '2018-12-19'

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
    pass


class BaseModelHandler(Handler):
    """
    Base Handler for Master & Detail Handlers
    """

    def addField(self, gui, field):  # pylint: disable=no-self-use
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

    def addDefaultFields(self, gui, flds):
        """
        Adds default fields (based in a list) to a "gui" description
        :param gui: Gui list where the "default" fielsds will be added
        :param flds: List of fields names requested to be added. Valid values are 'name', 'comments', 'priority' and 'small_name'
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

    def ensureAccess(self, obj, permission, root=False):
        perm = permissions.getEffectivePermission(self._user, obj, root)
        if perm < permission:
            self.accessDenied()
        return perm

    def typeInfo(self, type_):  # pylint: disable=no-self-use
        """
        Returns info about the type
        In fact, right now, it returns an empty dict, that will be extended by typeAsDict
        """
        return {}

    def typeAsDict(self, type_):
        """
        Returns a dictionary describing the type (the name, the icon, description, etc...)
        """
        res = self.typeInfo(type_)
        res.update({
            'name': _(type_.name()),
            'type': type_.type(),
            'description': _(type_.description()),
            'icon': type_.icon().replace('\n', '')
        })
        if hasattr(type_, 'group'):
            res['group'] = _(type_.group)  # Add group info is it is contained
        return res

    def processTableFields(self, title, fields, row_style, subtitle=None):  # pylint: disable=no-self-use
        """
        Returns a dict containing the table fields description
        """
        return {
            'title': title,
            'fields': fields,
            'row-style': row_style,
            'subtitle': '' if subtitle is None else subtitle
        }

    def readFieldsFromParams(self, fldList):  # pylint: disable=no-self-use
        """
        Reads the indicated fields from the parameters received, and if
        :param fldList: List of required fields
        :return: A dictionary containing all required fields
        """
        args = {}
        try:
            for key in fldList:
                args[key] = self._params[key]
                del self._params[key]
        except KeyError as e:
            raise RequestError('needed parameter not found in data {0}'.format(six.text_type(e)))

        return args

    def fillIntanceFields(self, item, res):  # pylint: disable=no-self-use
        """
        For Managed Objects (db element that contains a serialized object), fills a dictionary with the "field" parameters values.
        For non managed objects, it does nothing
        :param item: Item to extract fields
        :param res: Dictionary to "extend" with instance key-values pairs
        """
        if hasattr(item, 'getInstance'):
            i = item.getInstance()
            i.initGui()  # Defaults & stuff
            for key, value in six.iteritems(i.valuesDict()):
                if isinstance(value, six.string_types):
                    value = {"true": True, "false": False}.get(value, value)  # Translate "true" & "false" to True & False (booleans)
                logger.debug('{0} = {1}'.format(key, value))
                res[key] = value
        return res

    # Exceptions
    def invalidRequestException(self, message=None):
        """
        Raises an invalid request error with a default translated string
        :param message: Custom message to add to exception. If it is None, "Invalid Request" is used
        """
        message = _('Invalid Request') if message is None else message
        raise RequestError('{} {}: {}'.format(message, self.__class__, self._args))

    def invalidResponseException(self, message=None):
        message = 'Invalid response' if message is None else message
        raise ResponseError(message)

    def invalidMethodException(self):
        """
        Raises a NotFound exception with translated "Method not found" string to current locale
        """
        raise RequestError(_('Method not found in {}: {}'.format(self.__class__, self._args)))

    def invalidItemException(self, message=None):
        """
        Raises a NotFound exception, with location info
        """
        message = _('Item not found') if message is None else message
        raise NotFound(message)
        # raise NotFound('{} {}: {}'.format(message, self.__class__, self._args))

    def accessDenied(self, message=None):
        raise AccessDenied(message or _('Access denied'))

    def notSupported(self, message=None):
        raise NotSupportedError(message or _('Operation not supported'))

    # Success methods
    def success(self):
        """
        Utility method to be invoked for simple methods that returns nothing in fact
        """
        logger.debug('Returning success on {} {}'.format(self.__class__, self._args))
        return OK

    def test(self, type_):
        """
        Invokes a test for an item
        """
        logger.debug('Called base test for {0} --> {1}'.format(self.__class__.__name__, self._params))
        return self.invalidMethodException()


# Details do not have types at all
# so, right now, we only process details petitions for Handling & tables info
# noinspection PyMissingConstructor
class DetailHandler(BaseModelHandler):  # pylint: disable=abstract-class-not-used
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
    custom_methods = []

    def __init__(self, parentHandler, path, params, *args, **kwargs):  # pylint: disable=super-init-not-called
        """
        Detail Handlers in fact "disabled" handler most initialization, that is no needed because
        parent modelhandler has already done it (so we must access through parent handler)
        """
        self._parent = parentHandler
        self._path = path
        self._params = params
        self._args = args
        self._kwargs = kwargs
        self._user = kwargs.get('user', None)

    def __checkCustom(self, check, parent, arg=None):
        """
        checks curron methods
        :param check: Method to check
        :param parent: Parent Model Element
        :param arg: argument to pass to custom method
        """
        logger.debug('Checking custom method {0}'.format(check))
        if check in self.custom_methods:
            operation = getattr(self, check)

            if arg is None:
                return operation(parent)
            else:
                return operation(parent, arg)

        return None

    def get(self):  # pylint: disable=too-many-branches,too-many-return-statements
        """
        Processes GET method for a detail Handler
        """
        # Process args
        logger.debug("Detail args for GET: {0}".format(self._args))
        nArgs = len(self._args)

        parent = self._kwargs['parent']

        if nArgs == 0:
            return self.getItems(parent, None)

        # if has custom methods, look for if this request matches any of them
        r = self.__checkCustom(self._args[0], parent)
        if r is not None:
            return r

        if nArgs == 1:
            if self._args[0] == OVERVIEW:
                return self.getItems(parent, None)
            elif self._args[0] == GUI:
                gui = self.getGui(parent, None)
                return sorted(gui, key=lambda f: f['gui']['order'])
            elif self._args[0] == TYPES:
                return self.getTypes(parent, None)
            elif self._args[0] == TABLEINFO:
                return self.processTableFields(self.getTitle(parent), self.getFields(parent), self.getRowStyle(parent))

            # try to get id
            return self.getItems(parent, processUuid(self._args[0]))

        if nArgs == 2:
            if self._args[0] == GUI:
                gui = self.getGui(parent, self._args[1])
                return sorted(gui, key=lambda f: f['gui']['order'])
            elif self._args[0] == TYPES:
                return self.getTypes(parent, self._args[1])
            elif self._args[1] == LOG:
                return self.getLogs(parent, self._args[0])
            else:
                r = self.__checkCustom(self._args[1], parent, self._args[0])
                if r is not None:
                    return r

        return self.fallbackGet()

    def put(self):
        """
        Process the "PUT" operation, making the correspondent checks.
        Evaluates if it is a new element or a "modify" operation (based on if it has parameter),
        and invokes "saveItem" with parent & item (that can be None for a new Item)
        """
        logger.debug("Detail args for PUT: {0}, {1}".format(self._args, self._params))

        parent = self._kwargs['parent']

        # Create new item unless param received
        item = None
        if len(self._args) == 1:
            item = self._args[0]
        elif len(self._args) > 1:  # PUT expects 0 or 1 parameters. 0 == NEW, 1 = EDIT
            self.invalidRequestException()

        logger.debug('Invoking proper saving detail item {}'.format(item))
        return self.saveItem(parent, item)

    def post(self):
        """
        Process the "POST" operation
        Post can be used for, for example, testing.
        Right now is an invalid method for Detail elements
        """
        self.invalidRequestException('This method does not accepts POST')

    def delete(self):
        """
        Process the "DELETE" operation, making the correspondent checks.
        Extracts the item id and invokes deleteItem with parent item and item id (uuid)
        """
        logger.debug("Detail args for DELETE: {0}".format(self._args))

        parent = self._kwargs['parent']

        if len(self._args) != 1:
            self.invalidRequestException()

        return self.deleteItem(parent, self._args[0])

    def fallbackGet(self):
        """
        Invoked if default get can't process request.
        Here derived classes can process "non default" (and so, not understood) GET constructions
        """
        raise self.invalidRequestException('Fallback invoked')

    # Override this to provide functionality
    # Default (as sample) getItems
    def getItems(self, parent, item):
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
    def saveItem(self, parent, item):
        """
        Invoked for a valid "put" operation
        If this method is not overridden, the detail class will not have "Save/modify" operations.
        Parameters (probably object fields) must be retrieved from "_params" member variable
        :param parent: Parent of this detail (parent DB Object)
        :param item: Item id (uuid)
        :return: Normally "success" is expected, but can throw any "exception"
        """
        logger.debug('Default saveItem handler caller for {0}'.format(self._path))
        self.invalidRequestException()

    # Default delete
    def deleteItem(self, parent, item):
        """
        Invoked for a valid "delete" operation.
        If this method is not overriden, the detail class will not have "delete" operation.
        :param parent: Parent of this detail (parent DB Object)
        :param item: Item id (uuid)
        :return: Normally "success" is expected, but can throw any "exception"
        """
        self.invalidRequestException()

    # A detail handler must also return title & fields for tables
    def getTitle(self, parent):  # pylint: disable=no-self-use
        """
        A "generic" title for a view based on this detail.
        If not overridden, defaults to ''
        :param parent: Parent object
        :return: Expected to return an string that is the "title".
        """
        return ''

    def getFields(self, parent):  # pylint: disable=no-self-use
        """
        A "generic" list of fields for a view based on this detail.
        If not overridden, defaults to emty list
        :param parent: Parent object
        :return: Expected to return a list of fields
        """
        return []

    def getRowStyle(self, parent):  # pylint: disable=no-self-use
        """
        A "generic" row style based on row field content.
        If not overridden, defaults to {}
        :param parent: Parent object
        :return: Expected to return a dictionary that contains 'field' & 'prefix' fields
        """
        return {}

    def getGui(self, parent, forType):  # pylint: disable=no-self-use
        """
        Gets the gui that is needed in order to "edit/add" new items on this detail
        If not overriden, means that the detail has no edit/new Gui
        :param parent: Parent object
        :param forType: Type of object needing gui
        :return: a "gui" (list of gui fields)
        """
        raise RequestError('Gui not provided for this type of object')

    def getTypes(self, parent, forType):  # pylint: disable=no-self-use
        """
        The default is that detail element will not have any types (they are "homogeneous")
        but we provided this method, that can be overridden, in case one detail needs it
        :param parent: Parent object
        :param forType: Request argument in fact
        :return: list of strings that repressents the detail types
        """
        return []  # Default is that details do not have types

    def getLogs(self, parent, item):
        """
        If the detail has any log associated with it items, provide it overriding this method
        :param parent:
        :param item:
        :return: a list of log elements (normally got using "uds.core.util.log.getLogs" method)
        """
        self.invalidMethodException()


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
    # Which model does this manage
    model = None

    # By default, filter is empty
    fltr = None

    # This is an array of tuples of two items, where first is method and second inticates if method needs parent id
    # For example ('services', True) -- > .../id_parent/services
    #             ('services', False) --> ..../services
    custom_methods = []  # If this model respond to "custom" methods, we will declare them here
    # If this model has details, which ones
    detail = None  # Dictionary containing detail routing
    # Put needed fields
    save_fields = []
    # Put removable fields before updating
    remove_fields = []
    # Table info needed fields and title
    table_fields = []
    table_row_style = {}
    table_title = ''
    table_subtitle = ''

    # This methods must be override, depending on what is provided

    # Data related
    def item_as_dict(self, item):
        """
        Must be overriden by descendants.
        Expects the return of an item as a dictionary
        """
        return None

    def item_as_dict_overview(self, item):
        """
        Invoked when request is an "overview"
        default behavior is return item_as_dict
        """
        return self.item_as_dict(item)

    # types related
    def enum_types(self):  # override this
        """
        Must be overriden by desdencents if they support types
        Excpetcs the list of types that the handler supports
        """
        return []

    def getTypes(self, *args, **kwargs):
        for type_ in self.enum_types():
            yield self.typeAsDict(type_)

    def getType(self, type_):
        found = None
        for v in self.getTypes():
            if v['type'] == type_:
                found = v
                break

        if found is None:
            raise NotFound('type not found')

        logger.debug('Found type {0}'.format(found))
        return found

    # log related
    def getLogs(self, item):
        self.ensureAccess(item, permissions.PERMISSION_READ)
        logger.debug('Default getLogs invoked')
        return log.getLogs(item)

    # gui related
    def getGui(self, type_):
        self.invalidRequestException()

    # Delete related, checks if the item can be deleted
    # If it can't be so, raises an exception
    def checkDelete(self, item):
        pass

    # Save related, checks if the item can be saved
    # If it can't be saved, raises an exception
    def checkSave(self, item):
        pass

    # Invoked to possibily fix fields (or add new one, or check
    def beforeSave(self, fields):
        pass

    # Invoked right after saved an item (no matter if new or edition)
    def afterSave(self, item):
        pass

    # End overridable

    def extractFilter(self):
        # Extract filter from params if present
        self.fltr = None
        if 'filter' in self._params:
            self.fltr = self._params['filter']
            del self._params['filter']  # Remove parameter
            logger.debug('Found a filter expression ({})'.format(self.fltr))

    def doFilter(self, data):
        # Right now, filtering only supports a single filter, in a future
        # we may improve it
        if self.fltr is None:
            return data

        # Filtering a non iterable (list or tuple)
        if not isinstance(data, (list, tuple, types.GeneratorType)):
            return data

        logger.debug('data: {}, fltr: {}'.format(data, self.fltr))
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

            def fltr_function(item):
                try:
                    if fld not in item or r.match(item[fld]) is None:
                        return False
                except Exception:
                    return False
                return True

            res = list(filter(fltr_function, data))

            logger.debug('After filtering: {}'.format(res))
            return res
        except:
            logger.exception('Exception:')
            logger.info('Filtering expression {} is invalid!'.format(self.fltr))
            raise RequestError('Filtering expression {} is invalid'.format(self.fltr))

        return data

    # Helper to process detail
    # Details can be managed (writen) by any user that has MANAGEMENT permission over parent
    def processDetail(self):
        logger.debug('Processing detail {} for with params {}'.format(self._path, self._params))
        try:
            item = self.model.objects.filter(uuid=self._args[0])[0]
            # If we do not have access to parent to, at least, read...

            if self._operation in ('put', 'post', 'delete'):
                requiredPermission = permissions.PERMISSION_MANAGEMENT
            else:
                requiredPermission = permissions.PERMISSION_READ

            if permissions.checkPermissions(self._user, item, requiredPermission) is False:
                logger.debug('Permission for user {} does not comply with {}'.format(self._user, requiredPermission))
                self.accessDenied()

            detailCls = self.detail[self._args[1]]
            args = list(self._args[2:])
            path = self._path + '/'.join(args[:2])
            detail = detailCls(self, path, self._params, *args, parent=item, user=self._user)
            method = getattr(detail, self._operation)

            return method()
        except KeyError:
            self.invalidMethodException()
        except AttributeError:
            self.invalidMethodException()

        raise Exception('Invalid code executed on processDetail')

    def getItems(self, overview=True, *args, **kwargs):
        for item in self.model.objects.filter(*args, **kwargs):
            try:
                if permissions.checkPermissions(self._user, item, permissions.PERMISSION_READ) is False:
                    continue
                if overview:
                    yield self.item_as_dict_overview(item)
                else:
                    res = self.item_as_dict(item)
                    self.fillIntanceFields(item, res)
                    yield res
            except Exception:  # maybe an exception is thrown to skip an item
                # logger.exception('Exception getting item from {0}'.format(self.model))
                pass

    def get(self):
        """
        Wraps real get method so we can process filters if they exists
        """
        # Extract filter from params if present
        self.extractFilter()
        return self.doFilter(self.doGet())

    def doGet(self):
        logger.debug('method GET for {0}, {1}'.format(self.__class__.__name__, self._args))
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
                        logger.error('Invalid custom method exception {}/{}/{}: {}'.format(self.__class__.__name__, self._args, self._params, e))
                        self.invalidMethodException()

                    return operation(item)

            elif self._args[0] == cm[0]:
                operation = None
                try:
                    operation = getattr(self, self._args[0])
                except Exception:
                    self.invalidMethodException()

                return operation()

        if nArgs == 1:
            if self._args[0] == OVERVIEW:
                return list(self.getItems())
            elif self._args[0] == TYPES:
                return list(self.getTypes())
            elif self._args[0] == TABLEINFO:
                return self.processTableFields(self.table_title, self.table_fields, self.table_row_style, self.table_subtitle)
            elif self._args[0] == GUI:
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
                self.invalidItemException()

        # nArgs > 1
        # Request type info or gui, or detail
        if self._args[0] == OVERVIEW:
            if nArgs != 2:
                self.invalidRequestException()
        elif self._args[0] == TYPES:
            if nArgs != 2:
                self.invalidRequestException()
            return self.getType(self._args[1])
        elif self._args[0] == GUI:
            if nArgs != 2:
                self.invalidRequestException()
            gui = self.getGui(self._args[1])
            return sorted(gui, key=lambda f: f['gui']['order'])
        elif self._args[1] == LOG:
            if nArgs != 2:
                self.invalidRequestException()
            try:
                item = self.model.objects.get(uuid=self._args[0].lower())  # DB maybe case sensitive??, anyway, uuids are stored in lowercase
                return self.getLogs(item)
            except Exception:
                self.invalidItemException()

        # If has detail and is requesting detail
        if self.detail is not None:
            return self.processDetail()

        self.invalidRequestException()

    def post(self):
        """
        Processes a POST request
        """
        # right now
        logger.debug('method POST for {0}, {1}'.format(self.__class__.__name__, self._args))
        if len(self._args) == 2:
            if self._args[0] == 'test':
                return self.test(self._args[1])

        self.invalidMethodException()

    def put(self):
        """
        Processes a PUT request
        """
        logger.debug('method PUT for {0}, {1}'.format(self.__class__.__name__, self._args))
        self._params['_request'] = self._request

        deleteOnError = False

        if len(self._args) > 1:  # Detail?
            return self.processDetail()

        self.ensureAccess(self.model(), permissions.PERMISSION_ALL, root=True)  # Must have write permissions to create, modify, etc..

        try:
            # Extract fields
            args = self.readFieldsFromParams(self.save_fields)
            logger.debug('Args: {}'.format(args))
            self.beforeSave(args)
            # If tags is in save fields, treat it "specially"
            if 'tags' in self.save_fields:
                tags = args['tags']
                del args['tags']
            else:
                tags = None

            deleteOnError = False
            if len(self._args) == 0:  # create new
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
            if tags is not None:
                logger.debug('Updating tags: {}'.format(tags))
                item.tags.set([ Tag.objects.get_or_create(tag=val)[0] for val in tags if val != ''])

        except self.model.DoesNotExist:
            raise NotFound('Item not found')
        except IntegrityError:  # Duplicate key probably
            raise RequestError('Element already exists (duplicate key error)')
        except SaveException as e:
            raise RequestError(six.text_type(e))
        except (RequestError, ResponseError):
            raise
        except Exception:
            logger.exception('Exception on put')
            raise RequestError('incorrect invocation to PUT')

        if not deleteOnError:
            self.checkSave(item)  # Will raise an exception if item can't be saved (only for modify operations..)

        # Store associated object if needed
        try:
            data_type = self._params.get('data_type', self._params.get('type'))
            if data_type is not None:
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

    def delete(self):
        """
        Processes a DELETE request
        """
        logger.debug('method DELETE for {0}, {1}'.format(self.__class__.__name__, self._args))
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

    def deleteItem(self, item):
        """
        Basic, overridable method for deleting an item
        """
        item.delete()
