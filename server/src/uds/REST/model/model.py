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

from django.db import IntegrityError, models
from django.utils.translation import gettext as _

from uds.core import consts
from uds.core import exceptions
from uds.core import types
from uds.core.module import Module
from uds.core.util import log, permissions
from uds.models import ManagedObjectModel, Tag, TaggingMixin

from .base import BaseModelHandler
from ..utils import camel_and_snake_case_from

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from .detail import DetailHandler

logger = logging.getLogger(__name__)


class ModelHandler(BaseModelHandler[types.rest.T_Item], typing.Generic[types.rest.T_Item]):
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
    ROLE = consts.UserRole.STAFF

    # Which model does this manage, must be a django model ofc
    MODEL: 'typing.ClassVar[type[models.Model]]'
    # If the model is filtered (for overviews)
    FILTER: 'typing.ClassVar[typing.Optional[collections.abc.Mapping[str, typing.Any]]]' = None
    # Same, but for exclude
    EXCLUDE: 'typing.ClassVar[typing.Optional[collections.abc.Mapping[str, typing.Any]]]' = None

    # This is an array of tuples of two items, where first is method and second inticates if method needs parent id (normal behavior is it needs it)
    # For example ('services', True) -- > .../id_parent/services
    #             ('services', False) --> ..../services
    CUSTOM_METHODS: typing.ClassVar[list[types.rest.ModelCustomMethod]] = (
        []
    )  # If this model respond to "custom" methods, we will declare them here
    # If this model has details, which ones
    DETAIL: typing.ClassVar[typing.Optional[dict[str, type['DetailHandler[typing.Any]']]]] = (
        None  # Dictionary containing detail routing
    )
    # Fields that are going to be saved directly
    # * If a field is in the form "field:default" and field is not present in the request, default will be used
    # * If the "default" is the string "None", then the default will be None
    # * If the "default" is _ (underscore), then the field will be ignored (not saved) if not present in the request
    # Note that these fields has to be present in the model, and they can be "edited" in the pre_save method
    FIELDS_TO_SAVE: typing.ClassVar[list[str]] = []
    # Put removable fields before updating
    EXCLUDED_FIELDS: typing.ClassVar[list[str]] = []
    # Table info needed fields and title
    
    TABLE: typing.ClassVar[types.rest.Table] = types.rest.Table.null()
    
    # This methods must be override, depending on what is provided

    # Data related
    def get_item(self, item: models.Model) -> types.rest.T_Item:
        """
        Must be overriden by descendants.
        Expects the return of an item as a dictionary
        """
        raise NotImplementedError()

    def get_item_summary(self, item: models.Model) -> types.rest.T_Item:
        """
        Invoked when request is an "overview"
        default behavior is return item_as_dict
        """
        return self.get_item(item)

    # types related
    def enum_types(self) -> collections.abc.Iterable[type['Module']]:  # override this
        """
        Must be overriden by desdencents if they support types
        Excpetcs the list of types that the handler supports
        """
        return []

    def get_types(
        self, *args: typing.Any, **kwargs: typing.Any
    ) -> typing.Generator[types.rest.TypeInfo, None, None]:
        for type_ in self.enum_types():
            yield self.as_typeinfo(type_)

    def get_type(self, type_: str) -> types.rest.TypeInfo:
        for v in self.get_types():
            if v.type == type_:
                return v

        raise exceptions.rest.NotFound('type not found')

    # log related
    def get_logs(self, item: models.Model) -> list[dict[typing.Any, typing.Any]]:
        self.check_access(item, types.permissions.PermissionType.READ)
        try:
            return log.get_logs(item)
        except Exception as e:
            logger.warning('Exception getting logs for %s: %s', item, e)
            return []

    # gui related
    def get_gui(self, for_type: str) -> list[types.ui.GuiElement]:
        return []
        # raise self.invalidRequestException()

    def get_processed_gui(self, for_type: str) -> list[types.ui.GuiElement]:
        return sorted(self.get_gui(for_type), key=lambda f: f['gui']['order'])

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

    # Helper to process detail
    # Details can be managed (writen) by any user that has MANAGEMENT permission over parent
    def process_detail(self) -> typing.Any:
        logger.debug('Processing detail %s for with params %s', self._path, self._params)
        try:
            item: models.Model = self.MODEL.objects.get(uuid__iexact=self._args[0])
            # If we do not have access to parent to, at least, read...

            if self._operation in ('put', 'post', 'delete'):
                required_permission = types.permissions.PermissionType.MANAGEMENT
            else:
                required_permission = types.permissions.PermissionType.READ

            if permissions.has_access(self._user, item, required_permission) is False:
                logger.debug(
                    'Permission for user %s does not comply with %s',
                    self._user,
                    required_permission,
                )
                raise self.access_denied_response()

            if not self.DETAIL:
                raise self.invalid_request_response()

            # pylint: disable=unsubscriptable-object
            handler_type = self.DETAIL[self._args[1]]
            args = list(self._args[2:])
            path = self._path + '/' + '/'.join(args[:2])
            detail_handler = handler_type(self, path, self._params, *args, parent=item, user=self._user)
            method = getattr(detail_handler, self._operation)

            return method()
        except self.MODEL.DoesNotExist:
            raise self.invalid_item_response()
        except (KeyError, AttributeError) as e:
            raise self.invalid_method_response() from e
        except exceptions.rest.HandlerError:
            raise
        except Exception as e:
            logger.error('Exception processing detail: %s', e)
            raise self.invalid_request_response() from e

    def get_items(
        self, *args: typing.Any, **kwargs: typing.Any
    ) -> typing.Generator[types.rest.T_Item, None, None]:
        if 'overview' in kwargs:
            overview: bool = kwargs['overview']
            del kwargs['overview']
        else:
            overview = True

        if 'prefetch' in kwargs:
            prefetch: list[str] = kwargs['prefetch']
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
            query = self.MODEL.objects.filter(*args, **kwargs).prefetch_related(*prefetch)

        if self.FILTER is not None:
            query = query.filter(**self.FILTER)

        if self.EXCLUDE is not None:
            query = query.exclude(**self.EXCLUDE)

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
                    yield self.get_item_summary(item)
                else:
                    yield self.get_item(item)
            except Exception as e:  # maybe an exception is thrown to skip an item
                logger.debug('Got exception processing item from model: %s', e)
                # logger.exception('Exception getting item from {0}'.format(self.model))

    def get(self) -> typing.Any:
        """
        Wraps real get method so we can process filters if they exists
        """
        return self.process_get()

    #  pylint: disable=too-many-return-statements
    def process_get(self) -> typing.Any:
        logger.debug('method GET for %s, %s', self.__class__.__name__, self._args)
        number_of_args = len(self._args)

        if number_of_args == 0:
            return list(self.get_items(overview=False))

        # if has custom methods, look for if this request matches any of them
        for cm in self.CUSTOM_METHODS:
            # Convert to snake case
            camel_case_name, snake_case_name = camel_and_snake_case_from(cm.name)
            if number_of_args > 1 and cm.needs_parent:  # Method needs parent (existing item)
                if self._args[1] in (camel_case_name, snake_case_name):
                    item = None
                    # Check if operation method exists
                    operation = getattr(self, snake_case_name, None) or getattr(self, camel_case_name, None)
                    try:
                        if not operation:
                            raise Exception()  # Operation not found
                        item = self.MODEL.objects.get(uuid__iexact=self._args[0])
                    except self.MODEL.DoesNotExist:
                        raise self.invalid_item_response()
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

            elif self._args[0] in (snake_case_name, snake_case_name):
                operation = getattr(self, snake_case_name) or getattr(self, snake_case_name)
                if not operation:
                    raise self.invalid_method_response()

                return operation()

        match self._args:
            case [consts.rest.OVERVIEW]:
                return [i.as_dict() for i in self.get_items()]
            case [consts.rest.OVERVIEW, *_fails]:
                raise self.invalid_request_response()
            case [consts.rest.TABLEINFO]:
                return self.TABLE.as_dict()
            case [consts.rest.TABLEINFO, *_fails]:
                raise self.invalid_request_response()
            case [consts.rest.TYPES]:
                return [i.as_dict() for i in self.get_types()]
            case [consts.rest.TYPES, for_type]:
                return self.get_type(for_type).as_dict()
            case [consts.rest.TYPES, for_type, *_fails]:
                raise self.invalid_request_response()
            case [consts.rest.GUI]:
                return self.get_processed_gui('')
            case [consts.rest.GUI, for_type]:
                return self.get_processed_gui(for_type)
            case [consts.rest.GUI, for_type, *_fails]:
                raise self.invalid_request_response()
            case _:  # Maybe an item or a detail
                if number_of_args == 1:
                    try:
                        item = self.MODEL.objects.get(uuid__iexact=self._args[0].lower())
                        self.check_access(item, types.permissions.PermissionType.READ)
                        return self.get_item(item).as_dict()
                    except Exception as e:
                        logger.exception('Got Exception looking for item')
                        raise self.invalid_item_response() from e
                elif number_of_args == 2:
                    if self._args[1] == consts.rest.LOG:
                        try:
                            item = self.MODEL.objects.get(uuid__iexact=self._args[0].lower())
                            return self.get_logs(item)
                        except Exception as e:
                            raise self.invalid_item_response() from e

                if self.DETAIL is not None:
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

        delete_on_error = False

        if len(self._args) > 1:  # Detail?
            return self.process_detail()

        # Here, self.model() indicates an "django model object with default params"
        self.check_access(
            self.MODEL(), types.permissions.PermissionType.ALL, root=True
        )  # Must have write permissions to create, modify, etc..

        try:
            # Extract fields
            args = self.fields_from_params(self.FIELDS_TO_SAVE)
            logger.debug('Args: %s', args)
            self.pre_save(args)
            # If tags is in save fields, treat it "specially"
            if 'tags' in self.FIELDS_TO_SAVE:
                tags = args['tags']
                del args['tags']
            else:
                tags = None

            delete_on_error = False
            item: models.Model
            if not self._args:  # create new?
                item = self.MODEL.objects.create(**args)
                delete_on_error = True
            else:  # Must have 1 arg
                # We have to take care with this case, update will efectively update records on db
                item = self.MODEL.objects.get(uuid__iexact=self._args[0].lower())
                for v in self.EXCLUDED_FIELDS:
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

            if not delete_on_error:
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

                res = self.get_item(item)
            except Exception:
                logger.exception('Exception on put')
                if delete_on_error:
                    item.delete()
                raise

            self.post_save(item)

            return res.as_dict()

        except self.MODEL.DoesNotExist:
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

        self.check_access(
            self.MODEL(), types.permissions.PermissionType.ALL, root=True
        )  # Must have write permissions to delete

        try:
            item = self.MODEL.objects.get(uuid__iexact=self._args[0].lower())
            self.validate_delete(item)
            self.delete_item(item)
        except self.MODEL.DoesNotExist:
            raise exceptions.rest.NotFound('Element do not exists') from None

        return consts.OK

    def delete_item(self, item: models.Model) -> None:
        """
        Basic, overridable method for deleting an item
        """
        item.delete()
