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
import dataclasses
import logging
import typing
import collections.abc

from django.db import IntegrityError
from django.utils.translation import gettext as _
from django.db.models import Model

from uds import models

from uds.core import exceptions, types, module, services
import uds.core.types.permissions
from uds.core.types.rest import TableInfo
from uds.core.util import log, permissions, ensure, ui as ui_utils
from uds.core.util.model import process_uuid
from uds.core.environment import Environment
from uds.core.consts.images import DEFAULT_THUMB_BASE64
from uds.core import ui
from uds.core.types.states import State


from uds.REST.model import DetailHandler


logger = logging.getLogger(__name__)


@dataclasses.dataclass
class ServiceItem(types.rest.ManagedObjectItem['models.Service']):
    id: str
    name: str
    tags: list[str]
    comments: str
    deployed_services_count: int
    user_services_count: int
    max_services_count_type: str
    maintenance_mode: bool
    permission: int
    info: 'ServiceInfo|types.rest.NotRequired' = types.rest.NotRequired.field()


@dataclasses.dataclass
class ServiceInfo(types.rest.BaseRestItem):
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


@dataclasses.dataclass
class ServicePoolResumeItem(types.rest.BaseRestItem):
    id: str
    name: str
    thumb: str
    user_services_count: int
    state: str


class Services(DetailHandler[ServiceItem]):  # pylint: disable=too-many-public-methods
    """
    Detail handler for Services, whose parent is a Provider
    """

    CUSTOM_METHODS = ['servicepools']

    @staticmethod
    def service_info(item: models.Service) -> ServiceInfo:
        info = item.get_type()
        overrided_fields = info.overrided_pools_fields or {}

        return ServiceInfo(
            icon=info.icon64().replace('\n', ''),
            needs_publication=info.publication_type is not None,
            max_deployed=info.userservices_limit,
            uses_cache=info.uses_cache and overrided_fields.get('uses_cache', True),
            uses_cache_l2=info.uses_cache_l2,
            cache_tooltip=_(info.cache_tooltip),
            cache_tooltip_l2=_(info.cache_tooltip_l2),
            needs_osmanager=info.needs_osmanager,
            allowed_protocols=[str(i) for i in info.allowed_protocols],
            services_type_provided=info.services_type_provided,
            can_reset=info.can_reset,
            can_list_assignables=info.can_assign(),
        )

    @staticmethod
    def service_item(item: models.Service, perm: int, full: bool = False) -> ServiceItem:
        """
        Convert a service db item to a dict for a rest response
        :param item: Service item (db)
        :param full: If full is requested, add "extra" fields to complete information
        """
        ret_value = ServiceItem(
            id=item.uuid,
            name=item.name,
            tags=[tag.tag for tag in item.tags.all()],
            comments=item.comments,
            deployed_services_count=item.deployedServices.count(),
            user_services_count=models.UserService.objects.filter(deployed_service__service=item)
            .exclude(state__in=State.INFO_STATES)
            .count(),
            max_services_count_type=str(item.max_services_count_type),
            maintenance_mode=item.provider.maintenance_mode,
            permission=perm,
            item=item,
        )

        if full:
            ret_value.info = Services.service_info(item)

        return ret_value

    def get_items(self, parent: 'Model', item: typing.Optional[str]) -> types.rest.ItemsResult[ServiceItem]:
        parent = ensure.is_instance(parent, models.Provider)
        # Check what kind of access do we have to parent provider
        perm = permissions.effective_permissions(self._user, parent)
        try:
            if item is None:
                return [Services.service_item(k, perm) for k in self.filter_queryset(parent.services.all())]
            k = parent.services.get(uuid=process_uuid(item))
            val = Services.service_item(k, perm, full=True)
            # On detail, ne wee to fill the instance fields by hand
            return val
        except models.Service.DoesNotExist:
            raise exceptions.rest.NotFound(_('Service not found')) from None
        except Exception as e:
            logger.error('Error getting services for %s: %s', parent, e)
            raise exceptions.rest.ResponseError(_('Error getting services')) from None

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
            return Services.service_item(
                service, permissions.effective_permissions(self._user, service), full=True
            )

        except models.Service.DoesNotExist:
            raise exceptions.rest.NotFound('Service not found') from None
        except IntegrityError as e:  # Duplicate key probably
            if service and service.token and not item:
                service.delete()
                raise exceptions.rest.RequestError(
                    'Service token seems to be in use by other service. Please, select a new one.'
                ) from e
            raise exceptions.rest.RequestError('Element already exists (duplicate key error)') from e
        except exceptions.ui.ValidationError as e:
            if (
                not item and service
            ):  # Only remove partially saved element if creating new (if editing, ignore this)
                self._delete_incomplete_service(service)
            raise exceptions.rest.ValidationError('Input error: {0}'.format(e)) from e
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
        except models.Service.DoesNotExist:
            raise exceptions.rest.NotFound(_('Service not found')) from None
        except Exception as e:
            logger.error('Error deleting service %s from %s: %s', item, parent, e)
            raise exceptions.rest.ResponseError(_('Error deleting service')) from None

        raise exceptions.rest.RequestError('Item has associated deployed services')

    def get_table(self, parent: 'Model') -> TableInfo:
        parent = ensure.is_instance(parent, models.Provider)
        return (
            ui_utils.TableBuilder(_('Services of {0}').format(parent.name))
            .icon(name='name', title=_('Name'))
            .text_column(name='type_name', title=_('Type'))
            .text_column(name='comments', title=_('Comments'))
            .numeric_column(name='deployed_services_count', title=_('Services Pools'), width='12em')
            .numeric_column(name='user_services_count', title=_('User Services'), width='12em')
            .dict_column(
                name='max_services_count_type',
                title=_('Counting method'),
                dct={
                    types.services.ServicesCountingType.STANDARD: _('Standard'),
                    types.services.ServicesCountingType.CONSERVATIVE: _('Conservative'),
                },
            )
            .text_column(name='tags', title=_('Tags'), visible=False)
            .row_style(prefix='row-maintenance-', field='maintenance_mode')
            .build()
        )

    def enum_types(self, parent: 'Model', for_type: typing.Optional[str]) -> list[types.rest.TypeInfo]:
        parent = ensure.is_instance(parent, models.Provider)
        logger.debug('get_types parameters: %s, %s', parent, for_type)
        offers: list[types.rest.TypeInfo] = []
        if for_type is None:
            offers = [type(self).as_typeinfo(t) for t in parent.get_type().get_provided_services()]
        else:
            for t in parent.get_type().get_provided_services():
                if for_type == t.mod_type():
                    offers = [type(self).as_typeinfo(t)]
                    break
            if not offers:
                raise exceptions.rest.NotFound('type not found')

        return offers

    @classmethod
    def possible_types(cls: type[typing.Self]) -> collections.abc.Iterable[type[module.Module]]:
        """
        If the detail has any possible types, provide them overriding this method
        :param cls:
        """
        for parent_type in services.factory().providers().values():
            for service in parent_type.get_provided_services():
                yield service

    def get_gui(self, parent: 'Model', for_type: str) -> list[types.ui.GuiElement]:
        parent = ensure.is_instance(parent, models.Provider)
        try:
            logger.debug('getGui parameters: %s, %s', parent, for_type)
            parent_instance = parent.get_instance()
            service_type = parent_instance.get_service_by_type(for_type)
            if not service_type:
                raise exceptions.rest.RequestError(f'Gui for type "{for_type}" not found')
            with Environment.temporary_environment() as env:
                service = service_type(
                    env, parent_instance
                )  # Instantiate it so it has the opportunity to alter gui description based on parent
                overrided_fields = service.overrided_fields or {}

                gui = (
                    ui_utils.GuiBuilder()
                    .add_stock_field(types.rest.stock.StockField.TAGS)
                    .add_stock_field(types.rest.stock.StockField.NAME)
                    .add_stock_field(types.rest.stock.StockField.COMMENTS)
                    .add_choice(
                        name='max_services_count_type',
                        choices=[
                            ui.gui.choice_item(
                                str(types.services.ServicesCountingType.STANDARD.value), _('Standard')
                            ),
                            ui.gui.choice_item(
                                str(types.services.ServicesCountingType.CONSERVATIVE.value), _('Conservative')
                            ),
                        ],
                        label=_('Service counting method'),
                        tooltip=_('Kind of service counting for calculating if MAX is reached'),
                        tab=types.ui.Tab.ADVANCED,
                    )
                    .add_fields(service.gui_description())
                )

                return [field_gui for field_gui in gui.build() if field_gui.name not in overrided_fields]

        except Exception as e:
            logger.exception('get_gui')
            raise exceptions.rest.ResponseError(str(e)) from e

    def get_logs(self, parent: 'Model', item: str) -> list[typing.Any]:
        parent = ensure.is_instance(parent, models.Provider)
        try:
            service = parent.services.get(uuid=process_uuid(item))
            logger.debug('Getting logs for %s', item)
            return log.get_logs(service)
        except models.Service.DoesNotExist:
            raise exceptions.rest.NotFound(_('Service not found')) from None
        except Exception as e:
            logger.error('Error getting logs for %s: %s', item, e)
            raise exceptions.rest.ResponseError(_('Error getting logs')) from None

    def servicepools(self, parent: 'Model', item: str) -> list[ServicePoolResumeItem]:
        parent = ensure.is_instance(parent, models.Provider)
        service = parent.services.get(uuid=process_uuid(item))
        logger.debug('Got parameters for servicepools: %s, %s', parent, item)
        res: list[ServicePoolResumeItem] = []
        for i in service.deployedServices.all():
            try:
                self.check_access(
                    i, uds.core.types.permissions.PermissionType.READ
                )  # Ensures access before listing...
                res.append(
                    ServicePoolResumeItem(
                        id=i.uuid,
                        name=i.name,
                        thumb=i.image.thumb64 if i.image is not None else DEFAULT_THUMB_BASE64,
                        user_services_count=i.userServices.exclude(
                            state__in=(State.REMOVED, State.ERROR)
                        ).count(),
                        state=_('With errors') if i.is_restrained() else _('Ok'),
                    )
                )
            except exceptions.rest.AccessDenied:
                pass

        return res
