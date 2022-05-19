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
import logging
import typing

from django.db import IntegrityError
from django.utils.translation import gettext as _

from uds import models

from uds.core import services
from uds.core.util import log
from uds.core.util import permissions
from uds.core.util.model import processUuid
from uds.core.util.config import GlobalConfig
from uds.core.environment import Environment
from uds.core.ui.images import DEFAULT_THUMB_BASE64
from uds.core.ui import gui
from uds.core.util.state import State

from uds.REST.model import DetailHandler
from uds.REST import NotFound, ResponseError, RequestError, AccessDenied

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.models import Provider

logger = logging.getLogger(__name__)


class Services(DetailHandler):  # pylint: disable=too-many-public-methods
    """
    Detail handler for Services, whose parent is a Provider
    """

    custom_methods = ['servicesPools']

    @staticmethod
    def serviceInfo(item: models.Service) -> typing.Dict[str, typing.Any]:
        info = item.getType()

        return {
            'icon': info.icon64().replace('\n', ''),
            'needs_publication': info.publicationType is not None,
            'max_deployed': info.maxDeployed,
            'uses_cache': info.usesCache and info.cacheConstrains is None,
            'uses_cache_l2': info.usesCache_L2,
            'cache_tooltip': _(info.cacheTooltip),
            'cache_tooltip_l2': _(info.cacheTooltip_L2),
            'needs_manager': info.needsManager,
            'allowedProtocols': info.allowedProtocols,
            'servicesTypeProvided': info.servicesTypeProvided,
            'must_assign_manually': info.mustAssignManually,
            'can_reset': info.canReset,
            'can_list_assignables': info.canAssign(),
        }

    @staticmethod
    def serviceToDict(
        item: models.Service, perm: int, full: bool = False
    ) -> typing.Dict[str, typing.Any]:
        """
        Convert a service db item to a dict for a rest response
        :param item: Service item (db)
        :param full: If full is requested, add "extra" fields to complete information
        """
        itemType = item.getType()
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

    def getItems(self, parent: 'Provider', item: typing.Optional[str]):
        # Check what kind of access do we have to parent provider
        perm = permissions.getEffectivePermission(self._user, parent)
        try:
            if item is None:
                return [Services.serviceToDict(k, perm) for k in parent.services.all()]
            k = parent.services.get(uuid=processUuid(item))
            val = Services.serviceToDict(k, perm, full=True)
            return self.fillIntanceFields(k, val)
        except Exception:
            logger.exception('itemId %s', item)
            raise self.invalidItemException()

    def getRowStyle(self, parent: 'Provider') -> typing.Dict[str, typing.Any]:
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
            except Exception:
                pass

    def saveItem(self, parent: 'Provider', item: typing.Optional[str]) -> None:
        # Extract item db fields
        # We need this fields for all
        logger.debug('Saving service for %s / %s', parent, item)
        fields = self.readFieldsFromParams(
            ['name', 'comments', 'data_type', 'tags', 'max_services_count_type']
        )
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

            serviceInstance = service.getInstance(self._params)

            # Store token if this service provides one
            service.token = serviceInstance.getToken() or None  # If '', use "None" to

            service.data = (
                serviceInstance.serialize()
            )  # This may launch an validation exception (the getInstance(...) part)

            service.save()
        except models.Service.DoesNotExist:
            raise self.invalidItemException()
        except IntegrityError:  # Duplicate key probably
            if service and service.token and not item:
                service.delete()
                raise RequestError(
                    _(
                        'Service token seems to be in use by other service. Please, select a new one.'
                    )
                )
            raise RequestError(_('Element already exists (duplicate key error)'))
        except services.Service.ValidationException as e:
            if (
                not item and service
            ):  # Only remove partially saved element if creating new (if editing, ignore this)
                self._deleteIncompleteService(service)
            raise RequestError(_('Input error: {0}'.format(e)))
        except Exception as e:
            if not item and service:
                self._deleteIncompleteService(service)
            logger.exception('Saving Service')
            raise RequestError('incorrect invocation to PUT: {0}'.format(e))

    def deleteItem(self, parent: 'Provider', item: str) -> None:
        try:
            service = parent.services.get(uuid=processUuid(item))
            if service.deployedServices.count() == 0:
                service.delete()
                return
        except Exception:
            logger.exception('Deleting service')
            raise self.invalidItemException()

        raise RequestError('Item has associated deployed services')

    def getTitle(self, parent: 'Provider') -> str:
        try:
            return _('Services of {}').format(parent.name)
        except Exception:
            return _('Current services')

    def getFields(self, parent: 'Provider') -> typing.List[typing.Any]:
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

    def getTypes(
        self, parent: 'Provider', forType: typing.Optional[str]
    ) -> typing.Iterable[typing.Dict[str, typing.Any]]:
        logger.debug('getTypes parameters: %s, %s', parent, forType)
        offers: typing.List[typing.Dict[str, typing.Any]] = []
        if forType is None:
            offers = [
                {
                    'name': _(t.name()),
                    'type': t.type(),
                    'description': _(t.description()),
                    'icon': t.icon64().replace('\n', ''),
                }
                for t in parent.getType().getServicesTypes()
            ]
        else:
            for t in parent.getType().getServicesTypes():
                if forType == t.type():
                    offers = [
                        {
                            'name': _(t.name()),
                            'type': t.type(),
                            'description': _(t.description()),
                            'icon': t.icon64().replace('\n', ''),
                        }
                    ]
                    break
            if offers:
                raise NotFound('type not found')

        return offers  # Default is that details do not have types

    def getGui(self, parent: 'Provider', forType: str) -> typing.Iterable[typing.Any]:
        try:
            logger.debug('getGui parameters: %s, %s', parent, forType)
            parentInstance = parent.getInstance()
            serviceType = parentInstance.getServiceByType(forType)
            if not serviceType:
                raise self.invalidItemException('Gui for {} not found'.format(forType))

            service = serviceType(
                Environment.getTempEnv(), parentInstance
            )  # Instantiate it so it has the opportunity to alter gui description based on parent
            localGui = self.addDefaultFields(
                service.guiDescription(service), ['name', 'comments', 'tags']
            )
            self.addField(
                localGui,
                {
                    'name': 'max_services_count_type',
                    'values': [
                        gui.choiceItem('0', _('Standard')),
                        gui.choiceItem('1', _('Conservative')),
                    ],
                    'label': _('Service counting method'),
                    'tooltip': _(
                        'Kind of service counting for calculating if MAX is reached'
                    ),
                    'type': gui.InputField.CHOICE_TYPE,
                    'rdonly': False,
                    'order': 101,
                },
            )

            return localGui

        except Exception as e:
            logger.exception('getGui')
            raise ResponseError(str(e))

    def getLogs(self, parent: 'Provider', item: str) -> typing.List[typing.Any]:
        try:
            service = parent.services.get(uuid=processUuid(item))
            logger.debug('Getting logs for %s', item)
            return log.getLogs(service)
        except Exception:
            raise self.invalidItemException()

    def servicesPools(self, parent: 'Provider', item: str) -> typing.Any:
        service = parent.services.get(uuid=processUuid(item))
        logger.debug('Got parameters for servicepools: %s, %s', parent, item)
        res = []
        for i in service.deployedServices.all():
            try:
                self.ensureAccess(
                    i, permissions.PERMISSION_READ
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
