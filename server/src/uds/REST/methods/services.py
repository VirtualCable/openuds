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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing
import collections.abc

from django.db import IntegrityError
from django.utils.translation import gettext as _

from uds import models

from uds.core import exceptions, types
import uds.core.types.permissions
from uds.core.util import log, permissions, ensure
from uds.core.util.model import processUuid
from uds.core.environment import Environment
from uds.core.consts.images import DEFAULT_THUMB_BASE64
from uds.core.ui import gui
from uds.core.util.state import State


from uds.REST.model import DetailHandler
from uds.REST import NotFound, ResponseError, RequestError, AccessDenied

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from django.db.models import Model

logger = logging.getLogger(__name__)


class Services(DetailHandler):  # pylint: disable=too-many-public-methods
    """
    Detail handler for Services, whose parent is a Provider
    """

    custom_methods = ['servicesPools']

    @staticmethod
    def serviceInfo(item: models.Service) -> dict[str, typing.Any]:
        info = item.get_type()

        return {
            'icon': info.icon64().replace('\n', ''),
            'needs_publication': info.publicationType is not None,
            'max_deployed': info.maxUserServices,
            'uses_cache': info.usesCache and info.cacheConstrains is None,
            'uses_cache_l2': info.usesCache_L2,
            'cache_tooltip': _(info.cacheTooltip),
            'cache_tooltip_l2': _(info.cacheTooltip_L2),
            'needs_manager': info.needsManager,
            'allowedProtocols': info.allowedProtocols,
            'servicesTypeProvided': [info.servicesTypeProvided],  # As a list for compatibility, to be removed TODO: Remove
            'must_assign_manually': info.mustAssignManually,
            'can_reset': info.canReset,
            'can_list_assignables': info.canAssign(),
        }

    @staticmethod
    def serviceToDict(
        item: models.Service, perm: int, full: bool = False
    ) -> dict[str, typing.Any]:
        """
        Convert a service db item to a dict for a rest response
        :param item: Service item (db)
        :param full: If full is requested, add "extra" fields to complete information
        """
        itemType = item.get_type()
        retVal = {
            'id': item.uuid,
            'name': item.name,
            'tags': [tag.tag for tag in item.tags.all()],
            'comments': item.comments,
            'type': item.data_type,
            'type_name': _(itemType.name()),
            'deployed_services_count': item.deployedServices.count(),
            'user_services_count': models.UserService.objects.filter(
                deployed_service__service=item
            )
            .exclude(state__in=State.INFO_STATES)
            .count(),
            'max_services_count_type': item.max_services_count_type,
            'maintenance_mode': item.provider.maintenance_mode,
            'permission': perm,
        }
        if full:
            retVal['info'] = Services.serviceInfo(item)

        return retVal

    def getItems(self, parent: 'Model', item: typing.Optional[str]):
        parent = ensure.is_instance(parent, models.Provider)
        # Check what kind of access do we have to parent provider
        perm = permissions.getEffectivePermission(self._user, parent)
        try:
            if item is None:
                return [Services.serviceToDict(k, perm) for k in parent.services.all()]
            k = parent.services.get(uuid=processUuid(item))
            val = Services.serviceToDict(k, perm, full=True)
            return self.fillIntanceFields(k, val)
        except Exception as e:
            logger.error('Error getting services for %s: %s', parent, e)
            raise self.invalidItemException() from e

    def getRowStyle(self, parent: 'Model') -> dict[str, typing.Any]:
        parent = ensure.is_instance(parent, models.Provider)
        return {'field': 'maintenance_mode', 'prefix': 'row-maintenance-'}

    def _deleteIncompleteService(
        self, service: models.Service
    ):  # pylint: disable=no-self-use
        """
        Deletes a service if it is needed to (that is, if it is not None) and silently catch any exception of this operation
        :param service:  Service to delete (may be None, in which case it does nothing)
        """
        if service:
            try:
                service.delete()
            except Exception:  # nosec: This is a delete, we don't care about exceptions
                pass

    def saveItem(self, parent: 'Model', item: typing.Optional[str]) -> None:
        parent = ensure.is_instance(parent, models.Provider)
        # Extract item db fields
        # We need this fields for all
        logger.debug('Saving service for %s / %s', parent, item)
        fields = self.readFieldsFromParams(
            ['name', 'comments', 'data_type', 'tags', 'max_services_count_type']
        )
        # Fix max_services_count_type to ServicesCountingType enum or ServicesCountingType.STANDARD if not found
        try:
            fields['max_services_count_type'] = types.services.ServicesCountingType.from_int(int(fields['max_services_count_type']))
        except Exception:
            fields['max_services_count_type'] = types.services.ServicesCountingType.STANDARD
        tags = fields['tags']
        del fields['tags']
        service: typing.Optional[models.Service] = None

        try:
            if not item:  # Create new
                service = parent.services.create(**fields)
            else:
                service = parent.services.get(uuid=processUuid(item))
                service.__dict__.update(fields)

            if service is None:
                raise Exception('Cannot create service!')

            service.tags.set(
                [models.Tag.objects.get_or_create(tag=val)[0] for val in tags]
            )

            serviceInstance = service.get_instance(self._params)

            # Store token if this service provides one
            service.token = serviceInstance.getToken() or None  # If '', use "None" to

            service.data = (
                serviceInstance.serialize()
            )  # This may launch an validation exception (the get_instance(...) part)

            service.save()
        except models.Service.DoesNotExist:
            raise self.invalidItemException() from None
        except IntegrityError as e:  # Duplicate key probably
            if service and service.token and not item:
                service.delete()
                raise RequestError(
                    _(
                        'Service token seems to be in use by other service. Please, select a new one.'
                    )
                ) from e
            raise RequestError(_('Element already exists (duplicate key error)')) from e
        except exceptions.validation.ValidationError as e:
            if (
                not item and service
            ):  # Only remove partially saved element if creating new (if editing, ignore this)
                self._deleteIncompleteService(service)
            raise RequestError(_('Input error: {0}'.format(e))) from e
        except Exception as e:
            if not item and service:
                self._deleteIncompleteService(service)
            logger.exception('Saving Service')
            raise RequestError('incorrect invocation to PUT: {0}'.format(e)) from e

    def deleteItem(self, parent: 'Model', item: str) -> None:
        parent = ensure.is_instance(parent, models.Provider)
        try:
            service = parent.services.get(uuid=processUuid(item))
            if service.deployedServices.count() == 0:
                service.delete()
                return
        except Exception:
            logger.exception('Deleting service')
            raise self.invalidItemException() from None

        raise RequestError('Item has associated deployed services')

    def getTitle(self, parent: 'Model') -> str:
        parent = ensure.is_instance(parent, models.Provider)
        try:
            return _('Services of {}').format(parent.name)
        except Exception:
            return _('Current services')

    def getFields(self, parent: 'Model') -> list[typing.Any]:
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
                    'dict': {'0': _('Standard'), '1': _('Conservative')}
                },
            },
            {'tags': {'title': _('tags'), 'visible': False}},
        ]

    def get_types(
        self, parent: 'Model', forType: typing.Optional[str]
    ) -> collections.abc.Iterable[dict[str, typing.Any]]:
        parent = ensure.is_instance(parent, models.Provider)
        logger.debug('get_types parameters: %s, %s', parent, forType)
        offers: list[dict[str, typing.Any]] = []
        if forType is None:
            offers = [
                {
                    'name': _(t.name()),
                    'type': t.get_type(),
                    'description': _(t.description()),
                    'icon': t.icon64().replace('\n', ''),
                }
                for t in parent.get_type().getProvidedServices()
            ]
        else:
            for t in parent.get_type().getProvidedServices():
                if forType == t.get_type():
                    offers = [
                        {
                            'name': _(t.name()),
                            'type': t.get_type(),
                            'description': _(t.description()),
                            'icon': t.icon64().replace('\n', ''),
                        }
                    ]
                    break
            if offers:
                raise NotFound('type not found')

        return offers  # Default is that details do not have types

    def getGui(self, parent: 'Model', forType: str) -> collections.abc.Iterable[typing.Any]:
        parent = ensure.is_instance(parent, models.Provider)
        try:
            logger.debug('getGui parameters: %s, %s', parent, forType)
            parentInstance = parent.get_instance()
            serviceType = parentInstance.getServiceByType(forType)
            if not serviceType:
                raise self.invalidItemException(f'Gui for {forType} not found')

            service = serviceType(
                Environment.getTempEnv(), parentInstance
            )  # Instantiate it so it has the opportunity to alter gui description based on parent
            localGui = self.addDefaultFields(
                service.guiDescription(), ['name', 'comments', 'tags']
            )
            self.addField(
                localGui,
                {
                    'name': 'max_services_count_type',
                    'choices': [
                        gui.choiceItem('0', _('Standard')),
                        gui.choiceItem('1', _('Conservative')),
                    ],
                    'label': _('Service counting method'),
                    'tooltip': _(
                        'Kind of service counting for calculating if MAX is reached'
                    ),
                    'type': types.ui.FieldType.CHOICE,
                    'readonly': False,
                    'order': 101,
                },
            )

            return localGui

        except Exception as e:
            logger.exception('getGui')
            raise ResponseError(str(e)) from e

    def getLogs(self, parent: 'Model', item: str) -> list[typing.Any]:
        parent = ensure.is_instance(parent, models.Provider)
        try:
            service = parent.services.get(uuid=processUuid(item))
            logger.debug('Getting logs for %s', item)
            return log.getLogs(service)
        except Exception:
            raise self.invalidItemException() from None

    def servicesPools(self, parent: 'Model', item: str) -> typing.Any:
        parent = ensure.is_instance(parent, models.Provider)
        service = parent.services.get(uuid=processUuid(item))
        logger.debug('Got parameters for servicepools: %s, %s', parent, item)
        res = []
        for i in service.deployedServices.all():
            try:
                self.ensureAccess(
                    i, uds.core.types.permissions.PermissionType.READ
                )  # Ensures access before listing...
                res.append(
                    {
                        'id': i.uuid,
                        'name': i.name,
                        'thumb': i.image.thumb64
                        if i.image is not None
                        else DEFAULT_THUMB_BASE64,
                        'user_services_count': i.userServices.exclude(
                            state__in=(State.REMOVED, State.ERROR)
                        ).count(),
                        'state': _('With errors') if i.isRestrained() else _('Ok'),
                    }
                )
            except AccessDenied:
                pass

        return res
