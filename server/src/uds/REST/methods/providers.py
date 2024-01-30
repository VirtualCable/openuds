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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import collections.abc
import logging
import typing

from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

import uds.core.types.permissions
from uds.core import exceptions, services, types
from uds.core.environment import Environment
from uds.core.util import ensure, permissions
from uds.core.types.states import State
from uds.models import Provider, Service, UserService
from uds.REST.model import ModelHandler

from .services import Services as DetailServices
from .services_usage import ServicesUsage

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from django.db.models import Model


class Providers(ModelHandler):
    """
    Providers REST handler
    """

    model = Provider
    detail = {'services': DetailServices, 'usage': ServicesUsage}

    custom_methods = [('allservices', False), ('service', False), ('maintenance', True)]

    save_fields = ['name', 'comments', 'tags']

    table_title = typing.cast(str, _('Service providers'))

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
    table_row_style = types.ui.RowStyleInfo(prefix='row-maintenance-', field='maintenance_mode')

    def item_as_dict(self, item: 'Provider') -> dict[str, typing.Any]:
        type_ = item.get_type()

        # Icon can have a lot of data (1-2 Kbytes), but it's not expected to have a lot of services providers, and even so, this will work fine
        offers = [
            {
                'name': gettext(t.name()),
                'type': t.get_type(),
                'description': gettext(t.description()),
                'icon': t.icon64().replace('\n', ''),
            }
            for t in type_.get_provided_services()
        ]

        return {
            'id': item.uuid,
            'name': item.name,
            'tags': [tag.vtag for tag in item.tags.all()],
            'services_count': item.services.count(),
            'user_services_count': UserService.objects.filter(deployed_service__service__provider=item)
            .exclude(state__in=(State.REMOVED, State.ERROR))
            .count(),
            'maintenance_mode': item.maintenance_mode,
            'offers': offers,
            'type': type_.get_type(),
            'type_name': type_.name(),
            'comments': item.comments,
            'permission': permissions.effective_permissions(self._user, item),
        }

    def validate_delete(self, item: 'Model') -> None:
        item = ensure.is_instance(item, Provider)
        if item.services.count() > 0:
            raise exceptions.rest.RequestError(gettext('Can\'t delete providers with services'))

    # Types related
    def enum_types(self) -> collections.abc.Iterable[type[services.ServiceProvider]]:
        return services.factory().providers().values()

    # Gui related
    def get_gui(self, type_: str) -> list[typing.Any]:
        providerType = services.factory().lookup(type_)
        if providerType:
            with Environment.temporary_environment() as env:
                provider = providerType(env, None)
                return self.add_default_fields(provider.gui_description(), ['name', 'comments', 'tags'])
        raise exceptions.rest.NotFound('Type not found!')

    def allservices(self) -> typing.Generator[dict, None, None]:
        """
        Custom method that returns "all existing services", no mater who's his daddy :)
        """
        for s in Service.objects.all():
            try:
                perm = permissions.effective_permissions(self._user, s)
                if perm >= uds.core.types.permissions.PermissionType.READ:
                    yield DetailServices.service_to_dict(s, perm, True)
            except Exception:
                logger.exception('Passed service cause type is unknown')

    def service(self) -> dict:
        """
        Custom method that returns a service by its uuid, no matter who's his daddy
        """
        try:
            service = Service.objects.get(uuid=self._args[1])
            self.ensure_has_access(service.provider, uds.core.types.permissions.PermissionType.READ)
            perm = self.get_permissions(service.provider)
            return DetailServices.service_to_dict(service, perm, True)
        except Exception:
            # logger.exception('Exception')
            return {}

    def maintenance(self, item: 'Model') -> dict:
        """
        Custom method that swaps maintenance mode state for a provider
        :param item:
        """
        item = ensure.is_instance(item, Provider)
        self.ensure_has_access(item, uds.core.types.permissions.PermissionType.MANAGEMENT)
        item.maintenance_mode = not item.maintenance_mode
        item.save()
        return self.item_as_dict(item)

    def test(self, type_: str):
        from uds.core.environment import Environment

        logger.debug('Type: %s', type_)
        provider_type = services.factory().lookup(type_)

        if not provider_type:
            raise exceptions.rest.NotFound('Type not found!')

        with Environment.temporary_environment() as temp_environment:
            logger.debug('spType: %s', provider_type)

            dct = self._params.copy()
            dct['_request'] = self._request
            res = provider_type.test(temp_environment, dct)
            if res[0]:
                return 'ok'

            return res[1]
