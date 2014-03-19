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

'''
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''
from __future__ import unicode_literals

from handlers import NotFound, RequestError, ResponseError
from django.utils.translation import ugettext as _
from django.db import IntegrityError

from uds.core.ui.UserInterface import gui as uiGui
from uds.REST.handlers import Handler
from uds.core.util import log

import logging

logger = logging.getLogger(__name__)

# a few constants
OVERVIEW = 'overview'
TYPES = 'types'
TABLEINFO = 'tableinfo'
GUI = 'gui'
LOG = 'log'


# Exception to "rethrow" on save error
class SaveException(Exception):
    pass


# Base for Gui Related mixins
class BaseModelHandler(Handler):

    def addField(self, gui, field):
        gui.append({
            'name': field.get('name', ''),
            'value': '',
            'gui': {
                'required': field.get('required', False),
                'defvalue': field.get('value', ''),
                'value': field.get('value', ''),
                'label': field.get('label', ''),
                'length': field.get('length', 128),
                'multiline': field.get('multiline', 0),
                'tooltip': field.get('tooltip', ''),
                'rdonly': field.get('rdonly', False),
                'type': field.get('type', uiGui.InputField.TEXT_TYPE),
                'order': field.get('order', 0),
                'values': field.get('values', [])
            }
        })
        return gui

    def addDefaultFields(self, gui, flds):
        if 'name' in flds:
            self.addField(gui, {
                'name': 'name',
                'required': True,
                'label': _('Name'),
                'tooltip': _('Name of this element'),
                'order': 0 - 100,
            })
        if 'comments' in flds:
            self.addField(gui, {
                 'name': 'comments',
                 'label': _('Comments'),
                 'tooltip': _('Comments for this element'),
                 'length': 256,
                 'order': 0 - 99,
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
                 'order': 0 - 98,
            })
        if 'small_name' in flds:
            self.addField(gui, {
                 'name': 'small_name',
                 'type': 'text',
                 'label': _('Short name'),
                 'tooltip': _('Short name of this element'),
                 'required': True,
                 'length': 128,
                 'order': 0 - 97,
            })

        return gui

    def typeInfo(self, type_):
        return {}

    def type_as_dict(self, type_):
        res = self.typeInfo(type_)
        res.update({
            'name': _(type_.name()),
            'type': type_.type(),
            'description': _(type_.description()),
            'icon': type_.icon().replace('\n', '')
        })
        return res

    def processTableFields(self, title, fields, row_style):
        return {
            'title': unicode(title),
            'fields': fields,
            'row-style': row_style
        }

    def readFieldsFromParams(self, fldList):
        args = {}
        try:
            for key in fldList:
                args[key] = self._params[key]
                del self._params[key]
        except KeyError as e:
            raise RequestError('needed parameter not found in data {0}'.format(unicode(e)))

        return args

    def fillIntanceFields(self, item, res):
        if hasattr(item, 'getInstance'):
            for key, value in item.getInstance().valuesDict().iteritems():
                if type(value) in (unicode, str):
                    value = {"true": True, "false": False}.get(value, value)  # Translate "true" & "false" to True & False (booleans)
                logger.debug('{0} = {1}'.format(key, value))
                res[key] = value
        return res

    # Exceptions
    def invalidRequestException(self):
        raise RequestError(_('Invalid Request'))

    def invalidMethodException(self):
        raise NotFound(_('Method not found'))

    def invalidItemException(self, msg=None):
        msg = msg or _('Item not found')
        raise NotFound(msg)

    # Success methods
    def success(self):
        return 'done'

    def test(self, type_):
        logger.debug('Called base test for {0} --> {1}'.format(self.__class__.__name__, self._params))
        return self.invalidMethodException()


# Details do not have types at all
# so, right now, we only process details petitions for Handling & tables info
class DetailHandler(BaseModelHandler):
    custom_methods = []
    '''
    Detail handler (for relations such as provider-->services, authenticators-->users,groups, deployed services-->cache,assigned, groups, transports
    Urls recognized for GET are:
    [path] --> get Items (all hopefully, this call is delegated to getItems)
    [path]/overview
    [path]/ID
    [path]/gui
    [path]/gui/TYPE
    [path]/types
    [path]/types/TYPE
    [path]/tableinfo
    For PUT:
    [path] --> create NEW item
    [path]/ID --> Modify existing item
    For DELETE:
    [path]/ID

    Also accepts GET methods for "custom" methods
    '''

    def __init__(self, parentHandler, path, params, *args, **kwargs):
        self._parent = parentHandler
        self._path = path
        self._params = params
        self._args = args
        self._kwargs = kwargs

    def __checkCustom(self, check, parent, arg=None):
        logger.debug('Checking custom method {0}'.format(check))
        for cm in self.custom_methods:
            if check == cm:
                try:
                    operation = getattr(self, cm)
                except:
                    self.invalidMethodException()

                if arg is None:
                    return operation(parent)
                else:
                    return operation(parent, arg)
        return None

    def get(self):
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
            return self.getItems(parent, self._args[0])

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
        '''
        Put is delegated to specific implementation
        '''
        logger.debug("Detail args for PUT: {0}, {1}".format(self._args, self._params))

        parent = self._kwargs['parent']

        if len(self._args) == 0:
            # Create new
            item = None
        elif len(self._args) == 1:
            item = self._args[0]
        else:
            self.invalidRequestException()

        return self.saveItem(parent, item)

    def post(self):
        '''
        Post will be used for, for example, testing
        '''
        raise NotFound('TODO: do it :-)')

    def delete(self):
        '''
        Put is delegated to specific implementation
        '''
        logger.debug("Detail args for DELETE: {0}".format(self._args))

        parent = self._kwargs['parent']

        if len(self._args) != 1:
            self.invalidRequestException()

        return self.deleteItem(parent, self._args[0])

    # Invoked if default get can't process request
    def fallbackGet(self):
        raise self.invalidRequestException()

    # Override this to provide functionality
    # Default (as sample) getItems
    def getItems(self, parent, item):
        if item is None:  # Returns ALL detail items
            return []
        return {}  # Returns one item

    # Default save
    def saveItem(self, parent, item):
        logger.debug('Default saveItem handler caller for {0}'.format(self._path))
        self.invalidRequestException()

    # Default delete
    def deleteItem(self, parent, item):
        self.invalidRequestException()

    # A detail handler must also return title & fields for tables
    def getTitle(self, parent):
        return ''

    def getFields(self, parent):
        return []

    def getRowStyle(self, parent):
        return {}

    def getGui(self, parent, forType):
        raise RequestError('Gui not provided for this type of object')

    def getTypes(self, parent, forType):
        return []  # Default is that details do not have types

    def getLogs(self, parent, item):
        self.invalidMethodException()


class ModelHandler(BaseModelHandler):
    '''
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
    '''
    # Authentication related
    authenticated = True
    needs_staff = True
    # Which model does this manage
    model = None
    custom_methods = []  # If this model respond to "custom" methods, we will declare them here
                        # This is an array of tuples of two items, where first is method and second inticates if method needs parent id
                        # For example ('services', True) -- > .../id_parent/services
                        #             ('services', False) --> ..../services
    # If this model has details, which ones
    detail = None  # Dictionary containing detail routing
    # Put needed fields
    save_fields = []
    # Table info needed fields and title
    table_fields = []
    table_row_style = {}
    table_title = ''

    # This methods must be override, depending on what is provided

    # Data related
    def item_as_dict(self, item):
        pass

    # types related
    def enum_types(self):  # override this
        return []

    def getTypes(self, *args, **kwargs):
        for type_ in self.enum_types():
            yield self.type_as_dict(type_)

    def getType(self, type_):
        found = None
        for v in self.getTypes():
            if v['type'] == type_:
                found = v
                break

        if found is None:
            raise NotFound('type not found')

        logger.debug('Found type {0}'.format(v))
        return found

    # log related
    def getLogs(self, item):
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

    # Helper to process detail
    def processDetail(self):
        logger.debug('Processing detail {0}'.format(self._path))
        try:
            item = self.model.objects.filter(pk=self._args[0])[0]
            detailCls = self.detail[self._args[1]]
            args = list(self._args[2:])
            path = self._path + '/'.join(args[:2])
            detail = detailCls(self, path, self._params, *args, parent=item)
            method = getattr(detail, self._operation)
        except KeyError:
            self.invalidMethodException()
        except AttributeError:
            self.invalidMethodException()

        return method()

    def getItems(self, *args, **kwargs):
        for item in self.model.objects.filter(*args, **kwargs):
            try:
                yield self.item_as_dict(item)
            except:
                logger.exception('Exception getting item from {0}'.format(self.model))

    def get(self):
        logger.debug('method GET for {0}, {1}'.format(self.__class__.__name__, self._args))
        nArgs = len(self._args)
        if nArgs == 0:
            result = []
            for val in self.model.objects.all():
                res = self.item_as_dict(val)
                self.fillIntanceFields(val, res)
                result.append(res)
            return result

        # if has custom methods, look for if this request matches any of them
        for cm in self.custom_methods:
            if nArgs > 1 and cm[1] is True:  # Method needs parent (existing item)
                if self._args[1] == cm[0]:
                    try:
                        operation = getattr(self, self._args[1])
                        item = self.model.objects.get(pk=self._args[0])
                    except:
                        self.invalidMethodException()

                    return operation(item)
            elif self._args[0] == cm[0]:
                try:
                    operation = getattr(self, self._args[0])
                except:
                    self.invalidMethodException()

                return operation()

        if nArgs == 1:
            if self._args[0] == OVERVIEW:
                return list(self.getItems())
            elif self._args[0] == TYPES:
                return list(self.getTypes())
            elif self._args[0] == TABLEINFO:
                return self.processTableFields(self.table_title, self.table_fields, self.table_row_style)
            elif self._args[0] == GUI:
                return self.getGui(None)

            # get item ID
            try:
                val = self.model.objects.get(pk=self._args[0])
                res = self.item_as_dict(val)
                self.fillIntanceFields(val, res)
                return res
            except:
                self.invalidItemException()

        # nArgs > 1
        # Request type info or gui, or detail
        if self._args[0] == TYPES:
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
                item = self.model.objects.get(pk=self._args[0])
            except:
                self.invalidItemException()
            return self.getLogs(item)

        # If has detail and is requesting detail
        if self.detail is not None:
            return self.processDetail()

        self.invalidRequestException()

    def post(self):
        # right now
        logger.debug('method POST for {0}, {1}'.format(self.__class__.__name__, self._args))
        if len(self._args) == 2:
            if self._args[0] == 'test':
                return self.test(self._args[1])

        self.invalidMethodException()

    def put(self):
        logger.debug('method PUT for {0}, {1}'.format(self.__class__.__name__, self._args))

        if len(self._args) > 1:  # Detail?
            return self.processDetail()
        try:
            # Extract fields
            args = self.readFieldsFromParams(self.save_fields)
            self.beforeSave(args)
            deleteOnError = False
            if len(self._args) == 0:  # create new
                item = self.model.objects.create(**args)
                deleteOnError = True
            else:  # Must have 1 arg
                # We have to take care with this case, update will efectively update records on db
                item = self.model.objects.get(pk=self._args[0])
                item.__dict__.update(args)  # Update fields from args
        except self.model.DoesNotExist:
            raise NotFound('Item not found')
        except IntegrityError:  # Duplicate key probably
            raise RequestError('Element already exists (duplicate key error)')
        except SaveException as e:
            raise RequestError(unicode(e))
        except (RequestError, ResponseError):
            raise
        except Exception:
            logger.exception('Exception on put')
            raise RequestError('incorrect invocation to PUT')

        if not deleteOnError:
            self.checkSave(item)  # Will raise an exception if item can't be saved (only for modify operations..)

        # Store associated object if needed
        try:
            if 'data_type' in self._params:  # Needs to store instance
                item.data_type = self._params['data_type']
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
        logger.debug('method DELETE for {0}, {1}'.format(self.__class__.__name__, self._args))
        if len(self._args) > 1:
            return self.processDetail()

        if len(self._args) != 1:
            raise RequestError('Delete need one and only one argument')
        try:
            item = self.model.objects.get(pk=self._args[0])
            self.checkDelete(item)
            self.deleteItem(item)
        except self.model.DoesNotExist:
            raise NotFound('Element do not exists')

        return 'deleted'

    def deleteItem(self, item):
            item.delete()
