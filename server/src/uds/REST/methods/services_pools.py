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
from uds.models import ServicePool, OSManager, Service, Image, ServicePoolGroup, Account, User
from uds.models.calendar_action import (
    CALENDAR_ACTION_INITIAL,
    CALENDAR_ACTION_MAX,
    CALENDAR_ACTION_CACHE_L1,
    CALENDAR_ACTION_CACHE_L2,
    CALENDAR_ACTION_PUBLISH,
    CALENDAR_ACTION_ADD_TRANSPORT,
    CALENDAR_ACTION_DEL_TRANSPORT,
    CALENDAR_ACTION_ADD_GROUP,
    CALENDAR_ACTION_DEL_GROUP
)

from uds.core.managers import userServiceManager
from uds.core.ui.images import DEFAULT_THUMB_BASE64
from uds.core.util.state import State
from uds.core.util.model import processUuid
from uds.core.util import log
from uds.core.ui import gui
from uds.core.util import permissions

from uds.REST.model import ModelHandler
from uds.REST import RequestError, ResponseError

from .user_services import AssignedService, CachedService, Groups, Transports, Publications, Changelog
from .op_calendars import AccessCalendars, ActionsCalendars
from .services import Services


logger = logging.getLogger(__name__)


class ServicesPools(ModelHandler):
    """
    Handles Services Pools REST requests
    """
    model = ServicePool
    detail = {
        'services': AssignedService,
        'cache': CachedService,
        'groups': Groups,
        'transports': Transports,
        'publications': Publications,
        'changelog': Changelog,
        'access': AccessCalendars,
        'actions': ActionsCalendars
    }

    save_fields = ['name', 'short_name', 'comments', 'tags', 'service_id',
                   'osmanager_id', 'image_id', 'pool_group_id', 'initial_srvs',
                   'cache_l1_srvs', 'cache_l2_srvs', 'max_srvs', 'show_transports', 'visible',
                   'allow_users_remove', 'allow_users_reset', 'ignores_unused', 'account_id']

    remove_fields = ['osmanager_id', 'service_id']

    table_title = _('Service Pools')
    table_fields = [
        {'name': {'title': _('Name')}},
        {'state': {'title': _('Status'), 'type': 'dict', 'dict': State.dictionary()}},
        {'user_services_count': {'title': _('User services'), 'type': 'number'}},
        {'user_services_in_preparation': {'title': _('In Preparation')}},
        {'usage': {'title': _('Usage')}},
        {'visible': {'title': _('Visible'), 'type': 'callback'}},
        {'show_transports': {'title': _('Shows transports'), 'type': 'callback'}},
        {'pool_group_name': {'title': _('Pool group')}},
        {'parent': {'title': _('Parent service')}},
        {'tags': {'title': _('tags'), 'visible': False}},
    ]
    # Field from where to get "class" and prefix for that class, so this will generate "row-state-A, row-state-X, ....
    table_row_style = {'field': 'state', 'prefix': 'row-state-'}

    custom_methods = [
        ('setFallbackAccess', True),
        ('getFallbackAccess', True),
        ('actionsList', True),
        ('listAssignables', True),
        ('createFromAssignable', True),
    ]

    def item_as_dict(self, item: ServicePool) -> typing.Dict[str, typing.Any]:
        summary = 'summarize' in self._params
        # if item does not have an associated service, hide it (the case, for example, for a removed service)
        # Access from dict will raise an exception, and item will be skipped
        poolGroupId: typing.Optional[str] = None
        poolGroupName: str = _('Default')
        poolGroupThumb: str = DEFAULT_THUMB_BASE64
        if item.servicesPoolGroup:
            poolGroupId = item.servicesPoolGroup.uuid
            poolGroupName = item.servicesPoolGroup.name
            if item.servicesPoolGroup.image:
                poolGroupThumb = item.servicesPoolGroup.image.thumb64

        state = item.state
        if item.isInMaintenance():
            state = State.MAINTENANCE
        elif userServiceManager().canInitiateServiceFromDeployedService(item) is False:
            state = State.SLOWED_DOWN

        val = {
            'id': item.uuid,
            'name': item.name,
            'short_name': item.short_name,
            'tags': [tag.tag for tag in item.tags.all()],
            'parent': item.service.name,
            'parent_type': item.service.data_type,
            'comments': item.comments,
            'state': state,
            'thumb': item.image.thumb64 if item.image is not None else DEFAULT_THUMB_BASE64,
            'account': item.account.name if item.account is not None else '',
            'account_id': item.account.uuid if item.account is not None else None,
            'service_id': item.service.uuid,
            'provider_id': item.service.provider.uuid,
            'image_id': item.image.uuid if item.image is not None else None,
            'initial_srvs': item.initial_srvs,
            'cache_l1_srvs': item.cache_l1_srvs,
            'cache_l2_srvs': item.cache_l2_srvs,
            'max_srvs': item.max_srvs,
            'show_transports': item.show_transports,
            'visible': item.visible,
            'allow_users_remove': item.allow_users_remove,
            'allow_users_reset': item.allow_users_reset,
            'ignores_unused': item.ignores_unused,
            'fallbackAccess': item.fallbackAccess,
            'meta_member': [{'id': i.uuid, 'name': i.name} for i in item.meta.all()],
        }

        # Extended info
        if not summary:
            state = item.state
            if item.isInMaintenance():
                state = State.MAINTENANCE
            elif userServiceManager().canInitiateServiceFromDeployedService(item) is False:
                state = State.SLOWED_DOWN

            poolGroupId = None
            poolGroupName = _('Default')
            poolGroupThumb = DEFAULT_THUMB_BASE64
            if item.servicesPoolGroup is not None:
                poolGroupId = item.servicesPoolGroup.uuid
                poolGroupName = item.servicesPoolGroup.name
                if item.servicesPoolGroup.image is not None:
                    poolGroupThumb = item.servicesPoolGroup.image.thumb64

            val['state'] = state
            val['thumb'] = item.image.thumb64 if item.image is not None else DEFAULT_THUMB_BASE64
            val['user_services_count'] = item.userServices.exclude(state__in=State.INFO_STATES).count()
            val['user_services_in_preparation'] = item.userServices.filter(state=State.PREPARING).count()
            val['tags'] = [tag.tag for tag in item.tags.all()]
            val['restrained'] = item.isRestrained()
            val['permission'] = permissions.getEffectivePermission(self._user, item)
            val['info'] = Services.serviceInfo(item.service)
            val['pool_group_id'] = poolGroupId
            val['pool_group_name'] = poolGroupName
            val['pool_group_thumb'] = poolGroupThumb
            val['usage'] = item.usage()

        if item.osmanager:
            val['osmanager_id'] = item.osmanager.uuid

        return val

    # Gui related
    def getGui(self, type_: str) -> typing.List[typing.Any]:
        # if OSManager.objects.count() < 1:  # No os managers, can't create db
        #    raise ResponseError(ugettext('Create at least one OS Manager before creating a new service pool'))
        if Service.objects.count() < 1:
            raise ResponseError(ugettext('Create at least a service before creating a new service pool'))

        g = self.addDefaultFields([], ['name', 'short_name', 'comments', 'tags'])

        for f in [{
                'name': 'service_id',
                'values': [gui.choiceItem('', '')] + gui.sortedChoices([gui.choiceItem(v.uuid, v.provider.name + '\\' + v.name) for v in Service.objects.all()]),
                'label': ugettext('Base service'),
                'tooltip': ugettext('Service used as base of this service pool'),
                'type': gui.InputField.CHOICE_TYPE,
                'rdonly': True,
                'order': 100,  # Ensueres is At end
            }, {
                'name': 'osmanager_id',
                'values': [gui.choiceItem(-1, '')] + gui.sortedChoices([gui.choiceItem(v.uuid, v.name) for v in OSManager.objects.all()]),
                'label': ugettext('OS Manager'),
                'tooltip': ugettext('OS Manager used as base of this service pool'),
                'type': gui.InputField.CHOICE_TYPE,
                'rdonly': True,
                'order': 101,
            }, {
                'name': 'allow_users_remove',
                'value': False,
                'label': ugettext('Allow removal by users'),
                'tooltip': ugettext('If active, the user will be allowed to remove the service "manually". Be careful with this, because the user will have the "power" to delete it\'s own service'),
                'type': gui.InputField.CHECKBOX_TYPE,
                'order': 111,
                'tab': ugettext('Advanced'),
            }, {
                'name': 'allow_users_reset',
                'value': False,
                'label': ugettext('Allow reset by users'),
                'tooltip': ugettext('If active, the user will be allowed to reset the service'),
                'type': gui.InputField.CHECKBOX_TYPE,
                'order': 112,
                'tab': ugettext('Advanced'),
            }, {
                'name': 'ignores_unused',
                'value': False,
                'label': ugettext('Ignores unused'),
                'tooltip': ugettext('If the option is enabled, UDS will not attempt to detect and remove the user services assigned but not in use.'),
                'type': gui.InputField.CHECKBOX_TYPE,
                'order': 113,
                'tab': ugettext('Advanced'),
            }, {
                'name': 'image_id',
                'values': [gui.choiceImage(-1, '--------', DEFAULT_THUMB_BASE64)] + gui.sortedChoices([gui.choiceImage(v.uuid, v.name, v.thumb64) for v in Image.objects.all()]),
                'label': ugettext('Associated Image'),
                'tooltip': ugettext('Image assocciated with this service'),
                'type': gui.InputField.IMAGECHOICE_TYPE,
                'order': 120,
                'tab': ugettext('Display'),
            }, {
                'name': 'pool_group_id',
                'values': [gui.choiceImage(-1, _('Default'), DEFAULT_THUMB_BASE64)] + gui.sortedChoices([gui.choiceImage(v.uuid, v.name, v.thumb64) for v in ServicePoolGroup.objects.all()]),
                'label': ugettext('Pool group'),
                'tooltip': ugettext('Pool group for this pool (for pool classify on display)'),
                'type': gui.InputField.IMAGECHOICE_TYPE,
                'order': 121,
                'tab': ugettext('Display'),
            }, {
                'name': 'visible',
                'value': True,
                'label': ugettext('Visible'),
                'tooltip': ugettext('If active, transport will be visible for users'),
                'type': gui.InputField.CHECKBOX_TYPE,
                'order': 107,
                'tab': ugettext('Display'),
            }, {
                'name': 'initial_srvs',
                'value': '0',
                'minValue': '0',
                'label': ugettext('Initial available services'),
                'tooltip': ugettext('Services created initially for this service pool'),
                'type': gui.InputField.NUMERIC_TYPE,
                'order': 130,
                'tab': ugettext('Availability'),
            }, {
                'name': 'cache_l1_srvs',
                'value': '0',
                'minValue': '0',
                'label': ugettext('Services to keep in cache'),
                'tooltip': ugettext('Services kept in cache for improved user service assignation'),
                'type': gui.InputField.NUMERIC_TYPE,
                'order': 131,
                'tab': ugettext('Availability'),
            }, {
                'name': 'cache_l2_srvs',
                'value': '0',
                'minValue': '0',
                'label': ugettext('Services to keep in L2 cache'),
                'tooltip': ugettext('Services kept in cache of level2 for improved service generation'),
                'type': gui.InputField.NUMERIC_TYPE,
                'order': 132,
                'tab': ugettext('Availability'),
            }, {
                'name': 'max_srvs',
                'value': '0',
                'minValue': '1',
                'label': ugettext('Maximum number of services to provide'),
                'tooltip': ugettext('Maximum number of service (assigned and L1 cache) that can be created for this service'),
                'type': gui.InputField.NUMERIC_TYPE,
                'order': 133,
                'tab': ugettext('Availability'),
            }, {
                'name': 'show_transports',
                'value': True,
                'label': ugettext('Show transports'),
                'tooltip': ugettext('If active, alternative transports for user will be shown'),
                'type': gui.InputField.CHECKBOX_TYPE,
                'tab': ugettext('Advanced'),
                'order': 130,
            }, {
                'name': 'account_id',
                'values': [gui.choiceItem(-1, '')] + gui.sortedChoices([gui.choiceItem(v.uuid, v.name) for v in Account.objects.all()]),
                'label': ugettext('Accounting'),
                'tooltip': ugettext('Account associated to this service pool'),
                'type': gui.InputField.CHOICE_TYPE,
                'tab': ugettext('Advanced'),
                'order': 131,
            }]:
            self.addField(g, f)

        return g

    def beforeSave(self, fields: typing.Dict[str, typing.Any]) -> None: # pylint: disable=too-many-branches,too-many-statements
        # logger.debug(self._params)
        try:
            try:
                service = Service.objects.get(uuid=processUuid(fields['service_id']))
                fields['service_id'] = service.id
            except:
                raise RequestError(ugettext('Base service does not exist anymore'))

            try:
                serviceType = service.getType()

                if serviceType.publicationType is None:
                    self._params['publish_on_save'] = False

                if serviceType.canReset is False:
                    self._params['allow_users_reset'] = False

                if serviceType.needsManager is True:
                    osmanager = OSManager.objects.get(uuid=processUuid(fields['osmanager_id']))
                    fields['osmanager_id'] = osmanager.id
                else:
                    del fields['osmanager_id']

                if serviceType.cacheConstrains is not None:
                    for k, v in serviceType.cacheConstrains.items():
                        fields[k] = v

                if serviceType.maxDeployed != -1:
                    fields['max_srvs'] = min((int(fields['max_srvs']), serviceType.maxDeployed))
                    fields['initial_srvs'] = min(int(fields['initial_srvs']), serviceType.maxDeployed)
                    fields['cache_l1_srvs'] = min(int(fields['cache_l1_srvs']), serviceType.maxDeployed)

                if serviceType.usesCache is False:
                    for k in ('initial_srvs', 'cache_l1_srvs', 'cache_l2_srvs', 'max_srvs'):
                        fields[k] = 0

            except Exception:
                raise RequestError(ugettext('This service requires an OS Manager'))

            # If max < initial or cache_1 or cache_l2
            fields['max_srvs'] = max((int(fields['initial_srvs']), int(fields['cache_l1_srvs']), int(fields['max_srvs'])))

            # *** ACCOUNT ***
            accountId = fields['account_id']
            fields['account_id'] = None
            logger.debug('Account id: %s', accountId)

            if accountId != '-1':
                try:
                    fields['account_id'] = Account.objects.get(uuid=processUuid(accountId)).id
                except Exception:
                    logger.exception('Getting account ID')

            # **** IMAGE ***
            imgId = fields['image_id']
            fields['image_id'] = None
            logger.debug('Image id: %s', imgId)
            try:
                if imgId != '-1':
                    image = Image.objects.get(uuid=processUuid(imgId))
                    fields['image_id'] = image.id
            except Exception:
                logger.exception('At image recovering')

            # Servicepool Group
            spgrpId = fields['pool_group_id']
            del fields['pool_group_id']
            fields['servicesPoolGroup_id'] = None
            logger.debug('pool_group_id: %s', spgrpId)
            try:
                if spgrpId != '-1':
                    spgrp = ServicePoolGroup.objects.get(uuid=processUuid(spgrpId))
                    fields['servicesPoolGroup_id'] = spgrp.id
            except Exception:
                logger.exception('At service pool group recovering')

        except (RequestError, ResponseError):
            raise
        except Exception as e:
            raise RequestError(str(e))

    def afterSave(self, item: ServicePool) -> None:
        if self._params.get('publish_on_save', False) is True:
            try:
                item.publish()
            except Exception:
                pass

    def deleteItem(self, item: ServicePool) -> None:
        try:
            logger.debug('Deleting %s', item)
            item.remove()  # This will mark it for deletion, but in fact will not delete it directly
        except Exception:
            # Eat it and logit
            logger.exception('deleting service pool')

    # Logs
    def getLogs(self, item: ServicePool) -> typing.List[typing.Dict]:
        try:
            return log.getLogs(item)
        except Exception:
            return []

    # Set fallback status
    def setFallbackAccess(self, item: ServicePool):
        self.ensureAccess(item, permissions.PERMISSION_MANAGEMENT)

        fallback = self._params.get('fallbackAccess')
        if fallback != '':
            logger.debug('Setting fallback of %s to %s', item.name, fallback)
            item.fallbackAccess = fallback
            item.save()
        return item.fallbackAccess

    def getFallbackAccess(self, item: ServicePool):
        return item.fallbackAccess

    #  Returns the action list based on current element, for calendar
    def actionsList(self, item: ServicePool) -> typing.Any:
        validActions: typing.Tuple[typing.Dict, ...] = ()
        itemInfo = item.service.getType()
        if itemInfo.usesCache is True:
            validActions += (CALENDAR_ACTION_INITIAL, CALENDAR_ACTION_CACHE_L1, CALENDAR_ACTION_MAX)
            if itemInfo.usesCache_L2 is True:
                validActions += (CALENDAR_ACTION_CACHE_L2,)

        if itemInfo.publicationType is not None:
            validActions += (CALENDAR_ACTION_PUBLISH,)

        # Transport & groups actions
        validActions += (CALENDAR_ACTION_ADD_TRANSPORT, CALENDAR_ACTION_DEL_TRANSPORT, CALENDAR_ACTION_ADD_GROUP, CALENDAR_ACTION_DEL_GROUP)
        return validActions

    def listAssignables(self, item: ServicePool) -> typing.Any:
        service = item.service.getInstance()
        return [gui.choiceItem(i[0], i[1]) for i in service.listAssignables()]

    def createFromAssignable(self, item: ServicePool) ->typing.Any:
        if 'user_id' not in self._params or 'assignable_id' not in self._params:
            return self.invalidRequestException('Invalid parameters')

        logger.debug('Creating from assignable: %s', self._params)
        userServiceManager().createFromAssignable(item, User.objects.get(uuid=processUuid(self._params['user_id'])), self._params['assignable_id'])

        return True
