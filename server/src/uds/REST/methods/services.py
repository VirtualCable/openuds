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
import collections.abc

from django.db import IntegrityError
from django.utils.translation import gettext as _

from uds import models

from uds.core import exceptions, types
import uds.core.types.permissions
from uds.core.util import log, permissions, ensure, ui as ui_utils
from uds.core.util.model import process_uuid
from uds.core.environment import Environment
from uds.core.consts.images import DEFAULT_THUMB_BASE64
from uds.core import ui
from uds.core.types.states import State


from uds.REST.model import DetailHandler

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from django.db.models import Model

logger = logging.getLogger(__name__)


class ServiceItem(types.rest.ManagedObjectDictType):
    id: str
    name: str
    tags: list[str]
    comments: str
    deployed_services_count: int
    user_services_count: int
    max_services_count_type: str
    maintenance_mode: bool
    permission: int
    info: typing.NotRequired['ServiceInfo']


class ServiceInfo(types.rest.ItemDictType):
    icon: str
    needs_publication: bool
    max_deployed: int
    uses_cache: bool
    uses_cache_l2: bool
    cache_tooltip: str
    cache_tooltip_l2: str
    needs_osmanager: bool
    allowed_protocols: list[str]
    services_type_provided: str
    can_reset: bool
    can_list_assignables: bool


class ServicePoolResumeItem(types.rest.ItemDictType):
    id: str
    name: str
    thumb: str
    user_services_count: int
    state: str


class Services(DetailHandler[ServiceItem]):  # pylint: disable=too-many-public-methods
    """
    Detail handler for Services, whose parent is a Provider
    """

    custom_methods = ['servicepools']

    @staticmethod
    def service_info(item: models.Service) -> ServiceInfo:
        info = item.get_type()
        overrided_fields = info.overrided_pools_fields or {}

        return {
            'icon': info.icon64().replace('\n', ''),
            'needs_publication': info.publication_type is not None,
            'max_deployed': info.userservices_limit,
            'uses_cache': info.uses_cache and overrided_fields.get('uses_cache', True),
            'uses_cache_l2': info.uses_cache_l2,
            'cache_tooltip': _(info.cache_tooltip),
            'cache_tooltip_l2': _(info.cache_tooltip_l2),
            'needs_osmanager': info.needs_osmanager,
            'allowed_protocols': [str(i) for i in info.allowed_protocols],
            'services_type_provided': info.services_type_provided,
            'can_reset': info.can_reset,
            'can_list_assignables': info.can_assign(),
        }

    @staticmethod
    def service_to_dict(item: models.Service, perm: int, full: bool = False) -> ServiceItem:
        """
        Convert a service db item to a dict for a rest response
        :param item: Service item (db)
        :param full: If full is requested, add "extra" fields to complete information
        """
        ret_value: ServiceItem = {
            'id': item.uuid,
            'name': item.name,
            'tags': [tag.tag for tag in item.tags.all()],
            'comments': item.comments,
            'deployed_services_count': item.deployedServices.count(),
            'user_services_count': models.UserService.objects.filter(deployed_service__service=item)
            .exclude(state__in=State.INFO_STATES)
            .count(),
            'max_services_count_type': str(item.max_services_count_type),
            'maintenance_mode': item.provider.maintenance_mode,
            'permission': perm,
        }
        Services.fill_instance_type(item, ret_value)

        if full:
            ret_value['info'] = Services.service_info(item)

        return ret_value

    def get_items(self, parent: 'Model', item: typing.Optional[str]) -> types.rest.GetItemsResult[ServiceItem]:
        parent = ensure.is_instance(parent, models.Provider)
        # Check what kind of access do we have to parent provider
        perm = permissions.effective_permissions(self._user, parent)
        try:
            if item is None:
                return [Services.service_to_dict(k, perm) for k in parent.services.all()]
            k = parent.services.get(uuid=process_uuid(item))
            val = Services.service_to_dict(k, perm, full=True)
            # On detail, ne wee to fill the instance fields by hand
            self.fill_instance_fields(k, val)
            return val
        except Exception as e:
            logger.error('Error getting services for %s: %s', parent, e)
            raise self.invalid_item_response(repr(e)) from e

    def get_row_style(self, parent: 'Model') -> types.ui.RowStyleInfo:
        return types.ui.RowStyleInfo(prefix='row-maintenance-', field='maintenance_mode')

    def _delete_incomplete_service(self, service: models.Service) -> None:
        """
        Deletes a service if it is needed to (that is, if it is not None) and silently catch any exception of this operation
        :param service:  Service to delete (may be None, in which case it does nothing)
        """
        try:
            service.delete()
        except Exception:  # nosec: This is a delete, we don't care about exceptions
            pass

    def save_item(self, parent: 'Model', item: typing.Optional[str]) -> ServiceItem:
        parent = ensure.is_instance(parent, models.Provider)
        # Extract item db fields
        # We need this fields for all
        logger.debug('Saving service for %s / %s', parent, item)

        # Get the sevice type as first step, to obtain "overrided_fields" and other info
        service_type = parent.get_instance().get_service_by_type(self._params['data_type'])
        if not service_type:
            raise exceptions.rest.RequestError('Service type not found')

        fields = self.fields_from_params(
            ['name', 'comments', 'data_type', 'tags', 'max_services_count_type'],
            defaults=service_type.overrided_fields,
        )
        # Fix max_services_count_type to ServicesCountingType enum or ServicesCountingType.STANDARD if not found
        try:
            fields['max_services_count_type'] = types.services.ServicesCountingType.from_int(
                int(fields['max_services_count_type'])
            )
        except Exception:
            fields['max_services_count_type'] = types.services.ServicesCountingType.STANDARD
        tags = fields['tags']
        del fields['tags']
        service: typing.Optional[models.Service] = None

        try:
            if not item:  # Create new
                service = parent.services.create(**fields)
            else:
                service = parent.services.get(uuid=process_uuid(item))
                service.__dict__.update(fields)

            if not service:
                raise Exception('Cannot create service!')

            service.tags.set([models.Tag.objects.get_or_create(tag=val)[0] for val in tags])

            service_instance = service.get_instance(self._params)

            # Store token if this service provides one
            service.token = service_instance.get_token() or None  # If '', use "None" to

            # This may launch an validation exception (the get_instance(...) part)
            service.data = service_instance.serialize()

            service.save()
            return Services.service_to_dict(
                service, permissions.effective_permissions(self._user, service), full=True
            )

        except models.Service.DoesNotExist:
            raise self.invalid_item_response() from None
        except IntegrityError as e:  # Duplicate key probably
            if service and service.token and not item:
                service.delete()
                raise exceptions.rest.RequestError(
                    _('Service token seems to be in use by other service. Please, select a new one.')
                ) from e
            raise exceptions.rest.RequestError(_('Element already exists (duplicate key error)')) from e
        except exceptions.ui.ValidationError as e:
            if (
                not item and service
            ):  # Only remove partially saved element if creating new (if editing, ignore this)
                self._delete_incomplete_service(service)
            raise exceptions.rest.RequestError(_('Input error: {0}'.format(e))) from e
        except Exception as e:
            if not item and service:
                self._delete_incomplete_service(service)
            logger.exception('Saving Service')
            raise exceptions.rest.RequestError('incorrect invocation to PUT: {0}'.format(e)) from e

    def delete_item(self, parent: 'Model', item: str) -> None:
        parent = ensure.is_instance(parent, models.Provider)
        try:
            service = parent.services.get(uuid=process_uuid(item))
            if service.deployedServices.count() == 0:
                service.delete()
                return
        except Exception:
            logger.exception('Deleting service')
            raise self.invalid_item_response() from None

        raise exceptions.rest.RequestError('Item has associated deployed services')

    def get_title(self, parent: 'Model') -> str:
        parent = ensure.is_instance(parent, models.Provider)
        try:
            return _('Services of {}').format(parent.name)
        except Exception:
            return _('Current services')

    def get_fields(self, parent: 'Model') -> list[typing.Any]:
        return [
            {'name': {'title': _('Service name'), 'visible': True, 'type': 'iconType'}},
            {'comments': {'title': _('Comments')}},
            {'type_name': {'title': _('Type')}},
            {
                'deployed_services_count': {
                    'title': _('Services Pools'),
                    'type': 'numeric',
                }
            },
            {'user_services_count': {'title': _('User services'), 'type': 'numeric'}},
            {
                'max_services_count_type': {
                    'title': _('Max services count type'),
                    'type': 'dict',
                    'dict': {'0': _('Standard'), '1': _('Conservative')},
                },
            },
            {'tags': {'title': _('tags'), 'visible': False}},
        ]

    def get_types(
        self, parent: 'Model', for_type: typing.Optional[str]
    ) -> collections.abc.Iterable[types.rest.TypeInfoDict]:

        parent = ensure.is_instance(parent, models.Provider)
        logger.debug('get_types parameters: %s, %s', parent, for_type)
        offers: list[types.rest.TypeInfoDict] = []
        if for_type is None:
            offers = [
                {
                    'name': _(t.mod_name()),
                    'type': t.mod_type(),
                    'description': _(t.description()),
                    'icon': t.icon64().replace('\n', ''),
                }
                for t in parent.get_type().get_provided_services()
            ]
        else:
            for t in parent.get_type().get_provided_services():
                if for_type == t.mod_type():
                    offers = [
                        {
                            'name': _(t.mod_name()),
                            'type': t.mod_type(),
                            'description': _(t.description()),
                            'icon': t.icon64().replace('\n', ''),
                        }
                    ]
                    break
            if not offers:
                raise exceptions.rest.NotFound('type not found')

        return offers  # Default is that details do not have types

    def get_gui(self, parent: 'Model', for_type: str) -> list[types.ui.GuiElement]:
        parent = ensure.is_instance(parent, models.Provider)
        try:
            logger.debug('getGui parameters: %s, %s', parent, for_type)
            parent_instance = parent.get_instance()
            service_type = parent_instance.get_service_by_type(for_type)
            if not service_type:
                raise self.invalid_item_response(f'Gui for type "{for_type}" not found')
            with Environment.temporary_environment() as env:
                service = service_type(
                    env, parent_instance
                )  # Instantiate it so it has the opportunity to alter gui description based on parent
                overrided_fields = service.overrided_fields or {}
                return [
                    field_gui
                    for field_gui in self.compose_gui(
                        [
                            types.rest.stock.StockField.NAME,
                            types.rest.stock.StockField.COMMENTS,
                            types.rest.stock.StockField.TAGS,
                        ],
                        *service.gui_description(),
                        ui_utils.choice_field(
                            name='max_services_count_type',
                            choices=[
                                ui.gui.choice_item(
                                    str(types.services.ServicesCountingType.STANDARD.value),
                                    _('Standard'),
                                ),
                                ui.gui.choice_item(
                                    str(types.services.ServicesCountingType.CONSERVATIVE.value),
                                    _('Conservative'),
                                ),
                            ],
                            label=_('Service counting method'),
                            tooltip=_('Kind of service counting for calculating if MAX is reached'),
                            order=110,
                            tab=types.ui.Tab.ADVANCED,
                        ),
                    )
                    if field_gui['name'] not in overrided_fields
                ]

        except Exception as e:
            logger.exception('get_gui')
            raise exceptions.rest.ResponseError(str(e)) from e

    def get_logs(self, parent: 'Model', item: str) -> list[typing.Any]:
        parent = ensure.is_instance(parent, models.Provider)
        try:
            service = parent.services.get(uuid=process_uuid(item))
            logger.debug('Getting logs for %s', item)
            return log.get_logs(service)
        except Exception:
            raise self.invalid_item_response() from None

    def servicepools(self, parent: 'Model', item: str) -> list[ServicePoolResumeItem]:
        parent = ensure.is_instance(parent, models.Provider)
        service = parent.services.get(uuid=process_uuid(item))
        logger.debug('Got parameters for servicepools: %s, %s', parent, item)
        res: list[ServicePoolResumeItem] = []
        for i in service.deployedServices.all():
            try:
                self.ensure_has_access(
                    i, uds.core.types.permissions.PermissionType.READ
                )  # Ensures access before listing...
                res.append(
                    {
                        'id': i.uuid,
                        'name': i.name,
                        'thumb': i.image.thumb64 if i.image is not None else DEFAULT_THUMB_BASE64,
                        'user_services_count': i.userServices.exclude(
                            state__in=(State.REMOVED, State.ERROR)
                        ).count(),
                        'state': _('With errors') if i.is_restrained() else _('Ok'),
                    }
                )
            except exceptions.rest.AccessDenied:
                pass

        return res
