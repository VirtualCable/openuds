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
import datetime
import logging
import typing
import collections.abc

from django.db.models import Count, Q
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from uds.core import consts, types
from uds.core.managers.user_service import UserServiceManager
from uds.core.ui import gui
from uds.core.consts.images import DEFAULT_THUMB_BASE64
from uds.core.util import log, permissions, ensure
from uds.core.util.config import GlobalConfig
from uds.core.util.model import sql_datetime, processUuid
from uds.core.util.state import State
from uds.models import (Account, Image, OSManager, Service, ServicePool,
                        ServicePoolGroup, User)
from uds.models.calendar_action import (
    CALENDAR_ACTION_ADD_GROUP, CALENDAR_ACTION_ADD_TRANSPORT,
    CALENDAR_ACTION_CACHE_L1, CALENDAR_ACTION_CACHE_L2,
    CALENDAR_ACTION_DEL_ALL_GROUPS, CALENDAR_ACTION_DEL_ALL_TRANSPORTS,
    CALENDAR_ACTION_DEL_GROUP, CALENDAR_ACTION_DEL_TRANSPORT,
    CALENDAR_ACTION_IGNORE_UNUSED, CALENDAR_ACTION_INITIAL,
    CALENDAR_ACTION_MAX, CALENDAR_ACTION_PUBLISH,
    CALENDAR_ACTION_REMOVE_STUCK_USERSERVICES,
    CALENDAR_ACTION_REMOVE_USERSERVICES)
from uds.REST import RequestError, ResponseError
from uds.REST.model import ModelHandler

from .op_calendars import AccessCalendars, ActionsCalendars
from .services import Services
from .user_services import (AssignedService, CachedService, Changelog, Groups,
                            Publications, Transports)

if typing.TYPE_CHECKING:
    from django.db.models import Model

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
        'actions': ActionsCalendars,
    }

    save_fields = [
        'name',
        'short_name',
        'comments',
        'tags',
        'service_id',
        'osmanager_id',
        'image_id',
        'pool_group_id',
        'initial_srvs',
        'cache_l1_srvs',
        'cache_l2_srvs',
        'max_srvs',
        'show_transports',
        'visible',
        'allow_users_remove',
        'allow_users_reset',
        'ignores_unused',
        'account_id',
        'calendar_message',
    ]

    remove_fields = ['osmanager_id', 'service_id']

    table_title = typing.cast(str, _('Service Pools'))
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

    def getItems(self, *args, **kwargs) -> typing.Generator[typing.Any, None, None]:
        # Optimized query, due that there is a lot of info needed for theee
        d = sql_datetime() - datetime.timedelta(seconds=GlobalConfig.RESTRAINT_TIME.getInt())
        return super().getItems(
            overview=kwargs.get('overview', True),
            query=(
                ServicePool.objects.prefetch_related(
                    'service',
                    'service__provider',
                    'servicesPoolGroup',
                    'servicesPoolGroup__image',
                    'osmanager',
                    'image',
                    'tags',
                    'memberOfMeta__meta_pool',
                    'account',
                )
                .annotate(
                    valid_count=Count(
                        'userServices',
                        filter=~Q(userServices__state__in=State.INFO_STATES),
                    )
                )
                .annotate(preparing_count=Count('userServices', filter=Q(userServices__state=State.PREPARING)))
                .annotate(
                    error_count=Count(
                        'userServices',
                        filter=Q(
                            userServices__state=State.ERROR,
                            userServices__state_date__gt=d,
                        ),
                    )
                )
                .annotate(
                    usage_count=Count(
                        'userServices',
                        filter=Q(
                            userServices__state__in=State.VALID_STATES,
                            userServices__cache_level=0,
                        ),
                    )
                )
            ),
        )
        # return super().getItems(overview=kwargs.get('overview', True), prefetch=['service', 'service__provider', 'servicesPoolGroup', 'image', 'tags'])
        # return super(ServicesPools, self).getItems(*args, **kwargs)

    def item_as_dict(self, item: 'Model') -> dict[str, typing.Any]:
        item = ensure.is_instance(item, ServicePool)
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
        if item.is_in_maintenance():
            state = State.MAINTENANCE
        # This needs a lot of queries, and really does not apport anything important to the report
        # elif UserServiceManager().canInitiateServiceFromDeployedService(item) is False:
        #     state = State.SLOWED_DOWN
        val = {
            'id': item.uuid,
            'name': item.name,
            'short_name': item.short_name,
            'tags': [tag.tag for tag in item.tags.all()],
            'parent': item.service.name,  # type: ignore
            'parent_type': item.service.data_type,  # type: ignore
            'comments': item.comments,
            'state': state,
            'thumb': item.image.thumb64 if item.image is not None else DEFAULT_THUMB_BASE64,
            'account': item.account.name if item.account is not None else '',
            'account_id': item.account.uuid if item.account is not None else None,
            'service_id': item.service.uuid,  # type: ignore
            'provider_id': item.service.provider.uuid,  # type: ignore
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
            'meta_member': [
                {'id': i.meta_pool.uuid, 'name': i.meta_pool.name} for i in item.memberOfMeta.all()
            ],
            'calendar_message': item.calendar_message,
        }

        # Extended info
        if not summary:
            if hasattr(item, 'valid_count'):
                valid_count = item.valid_count  # type: ignore
                preparing_count = item.preparing_count  # type: ignore
                restrained = item.error_count >= GlobalConfig.RESTRAINT_COUNT.getInt()  # type: ignore
                usage_count = item.usage_count  # type: ignore
            else:
                valid_count = item.userServices.exclude(state__in=State.INFO_STATES).count()
                preparing_count = item.userServices.filter(state=State.PREPARING).count()
                restrained = item.is_restrained()
                usage_count = -1

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
            val['user_services_count'] = valid_count
            val['user_services_in_preparation'] = preparing_count
            val['tags'] = [tag.tag for tag in item.tags.all()]
            val['restrained'] = restrained
            val['permission'] = permissions.effective_permissions(self._user, item)
            val['info'] = Services.serviceInfo(item.service)  # type: ignore
            val['pool_group_id'] = poolGroupId
            val['pool_group_name'] = poolGroupName
            val['pool_group_thumb'] = poolGroupThumb
            val['usage'] = str(item.usage(usage_count).percent) + '%'

        if item.osmanager:
            val['osmanager_id'] = item.osmanager.uuid

        return val

    # Gui related
    def getGui(self, type_: str) -> list[typing.Any]:
        # if OSManager.objects.count() < 1:  # No os managers, can't create db
        #    raise ResponseError(gettext('Create at least one OS Manager before creating a new service pool'))
        if Service.objects.count() < 1:
            raise ResponseError(gettext('Create at least a service before creating a new service pool'))

        g = self.addDefaultFields([], ['name', 'comments', 'tags'])

        for f in [
            {
                'name': 'short_name',
                'type': 'text',
                'label': _('Short name'),
                'tooltip': _('Short name for user service visualization'),
                'required': False,
                'length': 64,
                'order': 0 - 95,
            },
            {
                'name': 'service_id',
                'choices': [gui.choiceItem('', '')]
                + gui.sortedChoices(
                    [
                        gui.choiceItem(v.uuid, v.provider.name + '\\' + v.name)  # type: ignore
                        for v in Service.objects.all()
                    ]
                ),
                'label': gettext('Base service'),
                'tooltip': gettext('Service used as base of this service pool'),
                'type': types.ui.FieldType.CHOICE,
                'readonly': True,
                'order': 100,  # Ensures is At end
            },
            {
                'name': 'osmanager_id',
                'choices': [gui.choiceItem(-1, '')]
                + gui.sortedChoices(
                    [gui.choiceItem(v.uuid, v.name) for v in OSManager.objects.all()]  # type: ignore
                ),
                'label': gettext('OS Manager'),
                'tooltip': gettext('OS Manager used as base of this service pool'),
                'type': types.ui.FieldType.CHOICE,
                'readonly': True,
                'order': 101,
            },
            {
                'name': 'allow_users_remove',
                'value': False,
                'label': gettext('Allow removal by users'),
                'tooltip': gettext(
                    'If active, the user will be allowed to remove the service "manually". Be careful with this, because the user will have the "power" to delete it\'s own service'
                ),
                'type': types.ui.FieldType.CHECKBOX,
                'order': 111,
                'tab': gettext('Advanced'),
            },
            {
                'name': 'allow_users_reset',
                'value': False,
                'label': gettext('Allow reset by users'),
                'tooltip': gettext('If active, the user will be allowed to reset the service'),
                'type': types.ui.FieldType.CHECKBOX,
                'order': 112,
                'tab': gettext('Advanced'),
            },
            {
                'name': 'ignores_unused',
                'value': False,
                'label': gettext('Ignores unused'),
                'tooltip': gettext(
                    'If the option is enabled, UDS will not attempt to detect and remove the user services assigned but not in use.'
                ),
                'type': types.ui.FieldType.CHECKBOX,
                'order': 113,
                'tab': gettext('Advanced'),
            },
            {
                'name': 'visible',
                'value': True,
                'label': gettext('Visible'),
                'tooltip': gettext('If active, transport will be visible for users'),
                'type': types.ui.FieldType.CHECKBOX,
                'order': 107,
                'tab': gettext('Display'),
            },
            {
                'name': 'image_id',
                'choices': [gui.choiceImage(-1, '--------', DEFAULT_THUMB_BASE64)]
                + gui.sortedChoices(
                    [gui.choiceImage(v.uuid, v.name, v.thumb64) for v in Image.objects.all()]  # type: ignore
                ),
                'label': gettext('Associated Image'),
                'tooltip': gettext('Image assocciated with this service'),
                'type': types.ui.FieldType.IMAGECHOICE,
                'order': 120,
                'tab': gettext('Display'),
            },
            {
                'name': 'pool_group_id',
                'choices': [gui.choiceImage(-1, _('Default'), DEFAULT_THUMB_BASE64)]
                + gui.sortedChoices(
                    [
                        gui.choiceImage(v.uuid, v.name, v.thumb64)  # type: ignore
                        for v in ServicePoolGroup.objects.all()
                    ]
                ),
                'label': gettext('Pool group'),
                'tooltip': gettext('Pool group for this pool (for pool classify on display)'),
                'type': types.ui.FieldType.IMAGECHOICE,
                'order': 121,
                'tab': gettext('Display'),
            },
            {
                'name': 'calendar_message',
                'value': '',
                'label': gettext('Calendar access denied text'),
                'tooltip': gettext(
                    'Custom message to be shown to users if access is limited by calendar rules.'
                ),
                'type': types.ui.FieldType.TEXT,
                'order': 122,
                'tab': gettext('Display'),
            },
            {
                'name': 'initial_srvs',
                'value': '0',
                'minValue': '0',
                'label': gettext('Initial available services'),
                'tooltip': gettext('Services created initially for this service pool'),
                'type': types.ui.FieldType.NUMERIC,
                'order': 130,
                'tab': gettext('Availability'),
            },
            {
                'name': 'cache_l1_srvs',
                'value': '0',
                'minValue': '0',
                'label': gettext('Services to keep in cache'),
                'tooltip': gettext('Services kept in cache for improved user service assignation'),
                'type': types.ui.FieldType.NUMERIC,
                'order': 131,
                'tab': gettext('Availability'),
            },
            {
                'name': 'cache_l2_srvs',
                'value': '0',
                'minValue': '0',
                'label': gettext('Services to keep in L2 cache'),
                'tooltip': gettext('Services kept in cache of level2 for improved service generation'),
                'type': types.ui.FieldType.NUMERIC,
                'order': 132,
                'tab': gettext('Availability'),
            },
            {
                'name': 'max_srvs',
                'value': '0',
                'minValue': '0',
                'label': gettext('Maximum number of services to provide'),
                'tooltip': gettext(
                    'Maximum number of service (assigned and L1 cache) that can be created for this service'
                ),
                'type': types.ui.FieldType.NUMERIC,
                'order': 133,
                'tab': gettext('Availability'),
            },
            {
                'name': 'show_transports',
                'value': True,
                'label': gettext('Show transports'),
                'tooltip': gettext('If active, alternative transports for user will be shown'),
                'type': types.ui.FieldType.CHECKBOX,
                'tab': gettext('Advanced'),
                'order': 130,
            },
            {
                'name': 'account_id',
                'choices': [gui.choiceItem(-1, '')]
                + gui.sortedChoices(
                    [gui.choiceItem(v.uuid, v.name) for v in Account.objects.all()]  # type: ignore
                ),
                'label': gettext('Accounting'),
                'tooltip': gettext('Account associated to this service pool'),
                'type': types.ui.FieldType.CHOICE,
                'tab': gettext('Advanced'),
                'order': 131,
            },
        ]:
            self.addField(g, f)

        return g

    # pylint: disable=too-many-statements
    def beforeSave(self, fields: dict[str, typing.Any]) -> None:
        # logger.debug(self._params)
        def macro_fld_len(x) -> int:
            w = x
            for i in ('{use}', '{total}', '{usec}', '{left}'):
                w = w.replace(i, 'xx')
            return len(w)
                
        if macro_fld_len(fields['name']) > 128:
            raise RequestError(gettext('Name too long'))
        
        if macro_fld_len(fields['short_name']) > 32:
            raise RequestError(gettext('Short name too long'))

        try:
            try:
                service = Service.objects.get(uuid=processUuid(fields['service_id']))
                fields['service_id'] = service.id
            except Exception:
                raise RequestError(gettext('Base service does not exist anymore')) from None

            try:
                serviceType = service.get_type()

                if serviceType.publication_type is None:
                    self._params['publish_on_save'] = False

                if serviceType.can_reset is False:
                    self._params['allow_users_reset'] = False

                if serviceType.needs_manager is True:
                    osmanager = OSManager.objects.get(uuid=processUuid(fields['osmanager_id']))
                    fields['osmanager_id'] = osmanager.id
                else:
                    del fields['osmanager_id']

                # If service has "overrided fields", overwrite received ones now
                if serviceType.overrided_fields:
                    for k, v in serviceType.overrided_fields.items():
                        fields[k] = v

                if serviceType.uses_cache_l2 is False:
                    fields['cache_l2_srvs'] = 0

                if serviceType.uses_cache is False:
                    for k in (
                        'initial_srvs',
                        'cache_l1_srvs',
                        'cache_l2_srvs',
                        'max_srvs',
                    ):
                        fields[k] = 0
                else:  # uses cache, adjust values
                    fields['max_srvs'] = int(fields['max_srvs']) or 1  # ensure max_srvs is at least 1
                    fields['initial_srvs'] = int(fields['initial_srvs'])
                    fields['cache_l1_srvs'] = int(fields['cache_l1_srvs'])

                    # if serviceType.max_user_services != consts.UNLIMITED:
                    #    fields['max_srvs'] = min((fields['max_srvs'], serviceType.max_user_services))
                    #    fields['initial_srvs'] = min(fields['initial_srvs'], serviceType.max_user_services)
                    #    fields['cache_l1_srvs'] = min(fields['cache_l1_srvs'], serviceType.max_user_services)
            except Exception as e:
                raise RequestError(gettext('This service requires an OS Manager')) from e

            # If max < initial or cache_1 or cache_l2
            fields['max_srvs'] = max(
                (
                    int(fields['initial_srvs']),
                    int(fields['cache_l1_srvs']),
                    int(fields['max_srvs']),
                )
            )

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
            raise RequestError(str(e)) from e

    def afterSave(self, item: 'Model') -> None:
        item = ensure.is_instance(item, ServicePool)
        if self._params.get('publish_on_save', False) is True:
            try:
                item.publish()
            except Exception as e:
                logger.error('Could not publish service pool %s: %s', item.name, e)

    def deleteItem(self, item: 'Model') -> None:
        item = ensure.is_instance(item, ServicePool)
        try:
            logger.debug('Deleting %s', item)
            item.remove()  # This will mark it for deletion, but in fact will not delete it directly
        except Exception:
            # Eat it and logit
            logger.exception('deleting service pool')

    # Logs
    def getLogs(self, item: 'Model') -> list[dict]:
        item = ensure.is_instance(item, ServicePool)
        try:
            return log.get_logs(item)
        except Exception:
            return []

    # Set fallback status
    def setFallbackAccess(self, item: 'Model'):
        item = ensure.is_instance(item, ServicePool)
        self.ensureAccess(item, types.permissions.PermissionType.MANAGEMENT)

        fallback = self._params.get('fallbackAccess')
        if fallback:
            logger.debug('Setting fallback of %s to %s', item.name, fallback)
            item.fallbackAccess = fallback
            item.save()
        return item.fallbackAccess

    def getFallbackAccess(self, item: 'Model'):
        item = ensure.is_instance(item, ServicePool)
        return item.fallbackAccess

    #  Returns the action list based on current element, for calendar
    def actionsList(self, item: 'Model') -> typing.Any:
        item = ensure.is_instance(item, ServicePool)
        validActions: tuple[dict, ...] = ()
        itemInfo = item.service.get_type()  # type: ignore
        if itemInfo.uses_cache is True:
            validActions += (
                CALENDAR_ACTION_INITIAL,
                CALENDAR_ACTION_CACHE_L1,
                CALENDAR_ACTION_MAX,
            )
            if itemInfo.uses_cache_l2 is True:
                validActions += (CALENDAR_ACTION_CACHE_L2,)

        if itemInfo.publication_type is not None:
            validActions += (CALENDAR_ACTION_PUBLISH,)

        # Transport & groups actions
        validActions += (
            CALENDAR_ACTION_ADD_TRANSPORT,
            CALENDAR_ACTION_DEL_TRANSPORT,
            CALENDAR_ACTION_DEL_ALL_TRANSPORTS,
            CALENDAR_ACTION_ADD_GROUP,
            CALENDAR_ACTION_DEL_GROUP,
            CALENDAR_ACTION_DEL_ALL_GROUPS,
        )

        # Advanced actions
        validActions += (
            CALENDAR_ACTION_IGNORE_UNUSED,
            CALENDAR_ACTION_REMOVE_USERSERVICES,
            CALENDAR_ACTION_REMOVE_STUCK_USERSERVICES,
        )
        return validActions

    def listAssignables(self, item: 'Model') -> typing.Any:
        item = ensure.is_instance(item, ServicePool)
        service = item.service.get_instance()  # type: ignore
        return [gui.choiceItem(i[0], i[1]) for i in service.enumerate_assignables()]

    def createFromAssignable(self, item: 'Model') -> typing.Any:
        item = ensure.is_instance(item, ServicePool)
        if 'user_id' not in self._params or 'assignable_id' not in self._params:
            return self.invalidRequestException('Invalid parameters')

        logger.debug('Creating from assignable: %s', self._params)
        UserServiceManager().create_from_assignable(
            item,
            User.objects.get(uuid=processUuid(self._params['user_id'])),
            self._params['assignable_id'],
        )

        return True
