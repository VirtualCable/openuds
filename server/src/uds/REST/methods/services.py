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

from django.utils.translation import ugettext as _


from uds.models import Service, UserService

from uds.core.services import Service as coreService
from uds.core.util import log
from uds.core.Environment import Environment
from uds.REST.model import DetailHandler
from uds.REST import NotFound, ResponseError, RequestError
from django.db import IntegrityError

import logging

logger = logging.getLogger(__name__)


class Services(DetailHandler):

    @staticmethod
    def serviceToDict(item, full=False):
        retVal = {
            'id': item.uuid,
            'name': item.name,
            'comments': item.comments,
            'type': item.data_type,
            'type_name': _(item.getType().name()),
            'deployed_services_count': item.deployedServices.count(),
            'user_services_count': UserService.objects.filter(deployed_service__service=item).count(),
        }
        if full:
            info = item.getType()
            retVal['info'] = {
                'icon': info.icon().replace('\n', ''),
                'needs_publication': info.publicationType is not None,
                'max_deployed': info.maxDeployed,
                'uses_cache': info.usesCache,
                'uses_cache_l2': info.usesCache_L2,
                'cache_tooltip': _(info.cacheTooltip),
                'cache_tooltip_l2': _(info.cacheTooltip_L2),
                'needs_manager': info.needsManager,
                'must_assign_manually': info.mustAssignManually,
            }

        return retVal

    def getItems(self, parent, item):
        # Extract provider
        try:
            if item is None:
                return [Services.serviceToDict(k) for k in parent.services.all()]
            else:
                k = parent.services.get(uuid=item)
                val = Services.serviceToDict(k)
                return self.fillIntanceFields(k, val)
        except Exception:
            logger.exception('getItems')
            self.invalidItemException()

    def deleteIncompleteService(self, service):
        if service is not None:
            try:
                service.delete()
            except:
                pass

    def saveItem(self, parent, item):
        # Extract item db fields
        # We need this fields for all
        logger.debug('Saving service {0} / {1}'.format(parent, item))
        fields = self.readFieldsFromParams(['name', 'comments', 'data_type'])
        service = None
        try:
            if item is None:  # Create new
                service = parent.services.create(**fields)
            else:
                service = parent.services.get(uuid=item)
                service.__dict__.update(fields)

            service.data = service.getInstance(self._params).serialize()
            service.save()
        except Service.DoesNotExist:
            self.invalidItemException()
        except IntegrityError:  # Duplicate key probably
            raise RequestError(_('Element already exists (duplicate key error)'))
        except coreService.ValidationException as e:
            self.deleteIncompleteService(service)
            raise RequestError(_('Input error: {0}'.format(unicode(e))))
        except Exception as e:
            self.deleteIncompleteService(service)
            logger.exception('Saving Service')
            raise RequestError('incorrect invocation to PUT: {0}'.format(e))

        return self.getItems(parent, service.id)

    def deleteItem(self, parent, item):
        try:
            service = parent.services.get(uuid=item)

            if service.deployedServices.count() != 0:
                raise RequestError('Item has associated deployed services')

            service.delete()
        except:
            self.invalidItemException()

        return 'deleted'

    def getTitle(self, parent):
        try:
            return _('Services of {0}').format(parent.name)
        except:
            return _('Current services')

    def getFields(self, parent):
        return [
            {'name': {'title': _('Service name'), 'visible': True, 'type': 'iconType'}},
            {'comments': {'title': _('Comments')}},
            {'type_name': {'title': _('Type')}},
            {'deployed_services_count': {'title': _('Deployed services'), 'type': 'numeric', 'width': '7em'}},
            {'user_services_count': {'title': _('User services'), 'type': 'numeric', 'width': '7em'}},
        ]

    def getTypes(self, parent, forType):
        logger.debug('getTypes parameters: {0}, {1}'.format(parent, forType))
        if forType is None:
            offers = [{
                'name': _(t.name()),
                'type': t.type(),
                'description': _(t.description()),
                'icon': t.icon().replace('\n', '')} for t in parent.getType().getServicesTypes()]
        else:
            offers = None  # Do we really need to get one specific type?
            for t in parent.getType().getServicesTypes():
                if forType == t.type():
                    offers = t
                    break
            if offers is None:
                raise NotFound('type not found')

        return offers  # Default is that details do not have types

    def getGui(self, parent, forType):
        try:
            logger.debug('getGui parameters: {0}, {1}'.format(parent, forType))
            parentInstance = parent.getInstance()
            serviceType = parentInstance.getServiceByType(forType)
            service = serviceType(Environment.getTempEnv(), parentInstance)  # Instantiate it so it has the opportunity to alter gui description based on parent
            return  self.addDefaultFields(service.guiDescription(service), ['name', 'comments'])
        except Exception as e:
            logger.exception('getGui')
            raise ResponseError(unicode(e))

    def getLogs(self, parent, item):
        try:
            item = parent.services.get(uuid=item)
            logger.debug('Getting logs for {0}'.format(item))
            return log.getLogs(item)
        except:
            self.invalidItemException()
