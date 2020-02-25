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

from django.utils.translation import ugettext, ugettext_lazy as _

from uds.models import Provider, Service, UserService
from uds.core import services
from uds.core.util.state import State
from uds.core.util import permissions

from uds.REST import NotFound, RequestError
from uds.REST.model import ModelHandler

from .services import Services as DetailServices
from .services_usage import ServicesUsage

logger = logging.getLogger(__name__)


class Providers(ModelHandler):
    """
    Providers REST handler
    """
    model = Provider
    detail = {
        'services': DetailServices,
        'usage': ServicesUsage
    }

    custom_methods = [('allservices', False), ('service', False), ('maintenance', True)]

    save_fields = ['name', 'comments', 'tags']

    table_title = _('Service providers')

    # Table info fields
    table_fields = [
        {'name': {'title': _('Name'), 'type': 'iconType'}},
        {'type_name': {'title': _('Type')}},
        {'comments': {'title': _('Comments')}},
        {'maintenance_state': {'title': _('Status')}},
        {'services_count': {'title': _('Services'), 'type': 'numeric'}},
        {'user_services_count': {'title': _('User Services'), 'type': 'numeric'}},  # , 'width': '132px'
        {'tags': {'title': _('tags'), 'visible': False}},
    ]
    # Field from where to get "class" and prefix for that class, so this will generate "row-state-A, row-state-X, ....
    table_row_style = {'field': 'maintenance_mode', 'prefix': 'row-maintenance-'}

    def item_as_dict(self, item: Provider) -> typing.Dict[str, typing.Any]:
        type_ = item.getType()

        # Icon can have a lot of data (1-2 Kbytes), but it's not expected to have a lot of services providers, and even so, this will work fine
        offers = [{
            'name': ugettext(t.name()),
            'type': t.type(),
            'description': ugettext(t.description()),
            'icon': t.icon64().replace('\n', '')
        } for t in type_.getServicesTypes()]

        return {
            'id': item.uuid,
            'name': item.name,
            'tags': [tag.vtag for tag in item.tags.all()],
            'services_count': item.services.count(),
            'user_services_count': UserService.objects.filter(deployed_service__service__provider=item).exclude(state__in=(State.REMOVED, State.ERROR)).count(),
            'maintenance_mode': item.maintenance_mode,
            'offers': offers,
            'type': type_.type(),
            'type_name': type_.name(),
            'comments': item.comments,
            'permission': permissions.getEffectivePermission(self._user, item)
        }

    def checkDelete(self, item: Provider) -> None:
        if item.services.count() > 0:
            raise RequestError(ugettext('Can\'t delete providers with services'))

    # Types related
    def enum_types(self) -> typing.Iterable[typing.Type[services.ServiceProvider]]:
        return services.factory().providers().values()

    # Gui related
    def getGui(self, type_: str) -> typing.List[typing.Any]:
        clsType = services.factory().lookup(type_)
        if clsType:
            return self.addDefaultFields(clsType.guiDescription(), ['name', 'comments', 'tags'])
        raise NotFound('Type not found!')

    def allservices(self) -> typing.Generator[typing.Dict, None, None]:
        """
        Custom method that returns "all existing services", no mater who's his daddy :)
        """
        for s in Service.objects.all():
            try:
                perm = permissions.getEffectivePermission(self._user, s)
                if perm >= permissions.PERMISSION_READ:
                    yield DetailServices.serviceToDict(s, perm, True)
            except Exception:
                logger.exception('Passed service cause type is unknown')

    def service(self) -> typing.Dict:
        """
        Custom method that returns a service by its uuid, no matter who's his daddy
        """
        try:
            service = Service.objects.get(uuid=self._args[1])
            perm = self.ensureAccess(service.provider, permissions.PERMISSION_READ)  # Ensures that we can read this item
            return DetailServices.serviceToDict(service, perm, True)
        except Exception:
            # logger.exception('Exception')
            return {}

    def maintenance(self, item: Provider):
        """
        Custom method that swaps maintenance mode state for a provider
        :param item:
        """
        self.ensureAccess(item, permissions.PERMISSION_MANAGEMENT)
        item.maintenance_mode = not item.maintenance_mode
        item.save()
        return self.item_as_dict(item)

    def test(self, type_: str):
        from uds.core.environment import Environment

        logger.debug('Type: %s', type_)
        spType = services.factory().lookup(type_)

        if not spType:
            raise NotFound('Type not found!')

        self.ensureAccess(spType, permissions.PERMISSION_MANAGEMENT, root=True)

        logger.debug('spType: %s', spType)

        dct = self._params.copy()
        dct['_request'] = self._request
        res = spType.test(Environment.getTempEnv(), dct)
        if res[0]:
            return 'ok'

        return res[1]
