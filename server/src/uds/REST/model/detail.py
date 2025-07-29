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

import logging
import typing
import collections.abc

from django.db import models
from django.utils.translation import gettext as _

from uds.core import consts
from uds.core import types
from uds.core.util.model import process_uuid
from uds.REST.utils import rest_result

from .base import BaseModelHandler
from ..utils import camel_and_snake_case_from

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.models import User
    from .model import ModelHandler

logger = logging.getLogger(__name__)


# Details do not have types at all
# so, right now, we only process details petitions for Handling & tables info
# noinspection PyMissingConstructor
class DetailHandler(BaseModelHandler[types.rest.T_Item], typing.Generic[types.rest.T_Item]):
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
    _parent: typing.Optional[
        'ModelHandler[types.rest.T_Item]'
    ]  # Parent handler, that is the ModelHandler that contains this detail
    _path: str
    _params: typing.Any  # _params is deserialized object from request
    _args: list[str]
    _kwargs: dict[str, typing.Any]
    _user: 'User'

    def __init__(
        self,
        parent_handler: 'ModelHandler[types.rest.T_Item]',
        path: str,
        params: typing.Any,
        *args: str,
        user: 'User',
        **kwargs: typing.Any,
    ) -> None:
        """
        Detail Handlers in fact "disabled" handler most initialization, that is no needed because
        parent modelhandler has already done it (so we must access through parent handler)
        """
        # Parent init not invoked because their methos are not used on detail handlers (only on parent handlers..)
        self._parent = parent_handler
        self._request = parent_handler._request
        self._path = path
        self._params = params
        self._args = list(args)
        self._kwargs = kwargs
        self._user = user

    def _check_is_custom_method(self, check: str, parent: models.Model, arg: typing.Any = None) -> typing.Any:
        """
        checks curron methods
        :param check: Method to check
        :param parent: Parent Model Element
        :param arg: argument to pass to custom method
        """
        for to_check in self.custom_methods:
            camel_case_name, snake_case_name = camel_and_snake_case_from(to_check)
            if check in (camel_case_name, snake_case_name):
                operation = getattr(self, snake_case_name, None) or getattr(self, camel_case_name, None)
                if operation:
                    if not arg:
                        return operation(parent)
                    return operation(parent, arg)

        return consts.rest.NOT_FOUND

    # pylint: disable=too-many-branches,too-many-return-statements
    def get(self) -> typing.Any:
        """
        Processes GET method for a detail Handler
        """
        # Process args
        logger.debug('Detail args for GET: %s', self._args)
        num_args = len(self._args)

        parent: models.Model = self._kwargs['parent']

        if num_args == 0:
            return self.get_items(parent, None)

        # if has custom methods, look for if this request matches any of them
        r = self._check_is_custom_method(self._args[0], parent)
        if r is not consts.rest.NOT_FOUND:
            return r

        match self._args[0]:
            case consts.rest.OVERVIEW:
                if num_args == 1:
                    return self.get_items(parent, None)
                raise self.invalid_request_response()
            case consts.rest.TYPES:
                if num_args == 1:
                    types = self.get_types(parent, None)
                    logger.debug('Types: %s', types)
                    return [i.as_dict() for i in types]
                elif num_args == 2:
                    return [i.as_dict() for i in self.get_types(parent, self._args[1])]
                raise self.invalid_request_response()
            case consts.rest.TABLEINFO:
                if num_args == 1:
                    return self.table_info(
                        self.get_title(parent),
                        self.get_fields(parent),
                        self.get_row_style(parent),
                    ).as_dict()
                raise self.invalid_request_response()
            case consts.rest.GUI:
                if num_args in (1, 2):
                    if num_args == 1:
                        gui = self.get_processed_gui(parent, '')
                    else:
                        gui = self.get_processed_gui(parent, self._args[1])
                    return sorted(gui, key=lambda f: f['gui']['order'])
                raise self.invalid_request_response()
            case consts.rest.LOG:
                if num_args == 2:
                    return self.get_logs(parent, self._args[1])
                raise self.invalid_request_response()
            case _:
                # try to get id
                if num_args == 1:
                    return self.get_items(parent, process_uuid(self._args[0]))

                # Maybe a custom method?
                r = self._check_is_custom_method(self._args[1], parent, self._args[0])
                if r is not None:
                    return r

        # Not understood, fallback, maybe the derived class can understand it
        return self.fallback_get()

    def put(self) -> typing.Any:
        """
        Process the "PUT" operation, making the correspondent checks.
        Evaluates if it is a new element or a "modify" operation (based on if it has parameter),
        and invokes "save_item" with parent & item (that can be None for a new Item)
        """
        logger.debug('Detail args for PUT: %s, %s', self._args, self._params)

        parent: models.Model = self._kwargs['parent']

        # if has custom methods, look for if this request matches any of them
        if len(self._args) > 1:
            r = self._check_is_custom_method(self._args[1], parent)
            if r is not consts.rest.NOT_FOUND:
                return r

        # Create new item unless 1 param received (the id of the item to modify)
        item = None
        if len(self._args) == 1:
            item = self._args[0]
        elif len(self._args) > 1:  # PUT expects 0 or 1 parameters. 0 == NEW, 1 = EDIT
            raise self.invalid_request_response()

        logger.debug('Invoking proper saving detail item %s', item)
        return rest_result(self.save_item(parent, item))

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
    def get_items(
        self, parent: models.Model, item: typing.Optional[str]
    ) -> types.rest.ItemsResult[types.rest.T_Item]:
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
    def save_item(self, parent: models.Model, item: typing.Optional[str]) -> types.rest.T_Item:
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

    def get_gui(self, parent: models.Model, for_type: str) -> list[types.ui.GuiElement]:
        """
        Gets the gui that is needed in order to "edit/add" new items on this detail
        If not overriden, means that the detail has no edit/new Gui

        Args:
            parent (models.Model): Parent object
            for_type (str): Type of object needing gui

        Return:
            list[types.ui.GuiElement]: A list of gui fields
        """
        # raise RequestError('Gui not provided for this type of object')
        return []

    def get_processed_gui(self, parent: models.Model, for_type: str) -> list[types.ui.GuiElement]:
        return sorted(self.get_gui(parent, for_type), key=lambda f: f['gui']['order'])

    def get_types(
        self, parent: models.Model, for_type: typing.Optional[str]
    ) -> collections.abc.Iterable[types.rest.TypeInfo]:
        """
        The default is that detail element will not have any types (they are "homogeneous")
        but we provided this method, that can be overridden, in case one detail needs it

        Args:
            parent (models.Model): Parent object
            for_type (typing.Optional[str]): Request argument in fact

        Return:
            collections.abc.Iterable[types.rest.TypeInfoDict]: A list of dictionaries describing type/types
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
