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
import datetime
import logging
import typing

from django.db.models import Count, Q
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from uds.core import types, exceptions, consts
from uds.core.managers.userservice import UserServiceManager
from uds.core.ui import gui
from uds.core.consts.images import DEFAULT_THUMB_BASE64
from uds.core.util import log, permissions, ensure
from uds.core.util.config import GlobalConfig
from uds.core.util.model import sql_now, process_uuid
from uds.core.types.states import State
from uds.models import Account, Image, OSManager, Service, ServicePool, ServicePoolGroup, User
from uds.REST.model import ModelHandler

from .op_calendars import AccessCalendars, ActionsCalendars
from .services import Services
from .user_services import AssignedService, CachedService, Changelog, Groups, Publications, Transports

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
        'servers': CachedService,  # Alias for cache, but will change in a future release
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
        'custom_message',
        'display_custom_message',
        'state:_',  # Optional field, defaults to Nothing (to apply default or existing value)
    ]

    remove_fields = ['osmanager_id', 'service_id']

    table_title = _('Service Pools')
    table_fields = [
        {'name': {'title': _('Name')}},
        {'state': {'title': _('Status'), 'type': 'dict', 'dict': State.literals_dict()}},
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
    table_row_style = types.ui.RowStyleInfo(prefix='row-state-', field='state')

    custom_methods = [
        ('set_fallback_access', True),
        ('get_fallback_access', True),
        ('actions_list', True),
        ('list_assignables', True),
        ('create_from_assignable', True),
        ('add_log', True),
    ]

    def get_items(
        self, *args: typing.Any, **kwargs: typing.Any
    ) -> typing.Generator[types.rest.ItemDictType, None, None]:
        # Optimized query, due that there is a lot of info needed for theee
        d = sql_now() - datetime.timedelta(seconds=GlobalConfig.RESTRAINT_TIME.as_int())
        return super().get_items(
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
        # return super().get_items(overview=kwargs.get('overview', True), prefetch=['service', 'service__provider', 'servicesPoolGroup', 'image', 'tags'])
        # return super(ServicesPools, self).get_items(*args, **kwargs)

    def item_as_dict(self, item: 'Model') -> dict[str, typing.Any]:
        item = ensure.is_instance(item, ServicePool)
        summary = 'summarize' in self._params
        # if item does not have an associated service, hide it (the case, for example, for a removed service)
        # Access from dict will raise an exception, and item will be skipped

        poolgroup_id: typing.Optional[str] = None
        poolgroup_name: str = _('Default')
        poolgroup_thumb: str = DEFAULT_THUMB_BASE64
        if item.servicesPoolGroup:
            poolgroup_id = item.servicesPoolGroup.uuid
            poolgroup_name = item.servicesPoolGroup.name
            if item.servicesPoolGroup.image:
                poolgroup_thumb = item.servicesPoolGroup.image.thumb64

        state = item.state
        if item.is_in_maintenance():
            state = State.MAINTENANCE
        # This needs a lot of queries, and really does not apport anything important to the report
        # elif UserServiceManager.manager().canInitiateServiceFromDeployedService(item) is False:
        #     state = State.SLOWED_DOWN
        val: dict[str, typing.Any] = {
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
            'meta_member': [
                {'id': i.meta_pool.uuid, 'name': i.meta_pool.name} for i in item.memberOfMeta.all()
            ],
            'calendar_message': item.calendar_message,
            'custom_message': item.custom_message,
            'display_custom_message': item.display_custom_message,
        }

        # Extended info
        if not summary:
            if hasattr(item, 'valid_count'):
                valid_count = getattr(item, 'valid_count')
                preparing_count = getattr(item, 'preparing_count')
                restrained = getattr(item, 'error_count') >= GlobalConfig.RESTRAINT_COUNT.as_int()
                usage_count = getattr(item, 'usage_count')
            else:
                valid_count = item.userServices.exclude(state__in=State.INFO_STATES).count()
                preparing_count = item.userServices.filter(state=State.PREPARING).count()
                restrained = item.is_restrained()
                usage_count = -1

            poolgroup_id = None
            poolgroup_name = _('Default')
            poolgroup_thumb = DEFAULT_THUMB_BASE64
            if item.servicesPoolGroup is not None:
                poolgroup_id = item.servicesPoolGroup.uuid
                poolgroup_name = item.servicesPoolGroup.name
                if item.servicesPoolGroup.image is not None:
                    poolgroup_thumb = item.servicesPoolGroup.image.thumb64

            val['user_services_count'] = valid_count
            val['user_services_in_preparation'] = preparing_count
            val['restrained'] = restrained
            val['permission'] = permissions.effective_permissions(self._user, item)
            val['info'] = Services.service_info(item.service)
            val['pool_group_id'] = poolgroup_id
            val['pool_group_name'] = poolgroup_name
            val['pool_group_thumb'] = poolgroup_thumb
            val['usage'] = str(item.usage(usage_count).percent) + '%'

        if item.osmanager:
            val['osmanager_id'] = item.osmanager.uuid

        return val

    # Gui related
    def get_gui(self, type_: str) -> list[typing.Any]:
        # if OSManager.objects.count() < 1:  # No os managers, can't create db
        #    raise exceptions.rest.ResponseError(gettext('Create at least one OS Manager before creating a new service pool'))
        if Service.objects.count() < 1:
            raise exceptions.rest.ResponseError(
                gettext('Create at least a service before creating a new service pool')
            )

        g = self.add_default_fields([], ['name', 'comments', 'tags'])

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
                'choices': [gui.choice_item('', '')]
                + gui.sorted_choices(
                    [gui.choice_item(v.uuid, v.provider.name + '\\' + v.name) for v in Service.objects.all()]
                ),
                'label': gettext('Base service'),
                'tooltip': gettext('Service used as base of this service pool'),
                'type': types.ui.FieldType.CHOICE,
                'readonly': True,
                'order': 100,  # Ensures is At end
            },
            {
                'name': 'osmanager_id',
                'choices': [gui.choice_item(-1, '')]
                + gui.sorted_choices([gui.choice_item(v.uuid, v.name) for v in OSManager.objects.all()]),
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
                'choices': [gui.choice_image(-1, '--------', DEFAULT_THUMB_BASE64)]
                + gui.sorted_choices(
                    [gui.choice_image(v.uuid, v.name, v.thumb64) for v in Image.objects.all()]
                ),
                'label': gettext('Associated Image'),
                'tooltip': gettext('Image assocciated with this service'),
                'type': types.ui.FieldType.IMAGECHOICE,
                'order': 120,
                'tab': gettext('Display'),
            },
            {
                'name': 'pool_group_id',
                'choices': [gui.choice_image(-1, _('Default'), DEFAULT_THUMB_BASE64)]
                + gui.sorted_choices(
                    [gui.choice_image(v.uuid, v.name, v.thumb64) for v in ServicePoolGroup.objects.all()]
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
                'name': 'custom_message',
                'value': '',
                'label': gettext('Custom launch message text'),
                'tooltip': gettext(
                    'Custom message to be shown to users, if active, when trying to start a service from this pool.'
                ),
                'type': types.ui.FieldType.TEXT,
                'order': 123,
                'tab': gettext('Display'),
            },
            {
                'name': 'display_custom_message',
                'value': False,
                'label': gettext('Enable custom launch message'),
                'tooltip': gettext('If active, the custom launch message will be shown to users'),
                'type': types.ui.FieldType.CHECKBOX,
                'order': 124,
                'tab': gettext('Display'),
            },
            {
                'name': 'initial_srvs',
                'value': '0',
                'min_value': '0',
                'label': gettext('Initial available services'),
                'tooltip': gettext('Services created initially for this service pool'),
                'type': types.ui.FieldType.NUMERIC,
                'order': 130,
                'tab': gettext('Availability'),
            },
            {
                'name': 'cache_l1_srvs',
                'value': '0',
                'min_value': '0',
                'label': gettext('Services to keep in cache'),
                'tooltip': gettext('Services kept in cache for improved user service assignation'),
                'type': types.ui.FieldType.NUMERIC,
                'order': 131,
                'tab': gettext('Availability'),
            },
            {
                'name': 'cache_l2_srvs',
                'value': '0',
                'min_value': '0',
                'label': gettext('Services to keep in L2 cache'),
                'tooltip': gettext('Services kept in cache of level2 for improved service generation'),
                'type': types.ui.FieldType.NUMERIC,
                'order': 132,
                'tab': gettext('Availability'),
            },
            {
                'name': 'max_srvs',
                'value': '0',
                'min_value': '0',
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
                'choices': [gui.choice_item(-1, '')]
                + gui.sorted_choices([gui.choice_item(v.uuid, v.name) for v in Account.objects.all()]),
                'label': gettext('Accounting'),
                'tooltip': gettext('Account associated to this service pool'),
                'type': types.ui.FieldType.CHOICE,
                'tab': gettext('Advanced'),
                'order': 131,
            },
        ]:
            self.add_field(g, f)

        return g

    # pylint: disable=too-many-statements
    def pre_save(self, fields: dict[str, typing.Any]) -> None:
        # logger.debug(self._params)

        if types.pools.UsageInfoVars.processed_macros_len(fields['name']) > 128:
            raise exceptions.rest.RequestError(gettext('Name too long'))

        if types.pools.UsageInfoVars.processed_macros_len(fields['short_name']) > 32:
            raise exceptions.rest.RequestError(gettext('Short name too long'))

        try:
            try:
                service = Service.objects.get(uuid=process_uuid(fields['service_id']))
                fields['service_id'] = service.id
            except Exception:
                raise exceptions.rest.RequestError(gettext('Base service does not exist anymore')) from None

            try:
                service_type = service.get_type()

                if service_type.publication_type is None:
                    self._params['publish_on_save'] = False

                if service_type.can_reset is False:
                    self._params['allow_users_reset'] = False

                if service_type.needs_osmanager is True:
                    try:
                        osmanager = OSManager.objects.get(uuid=process_uuid(fields['osmanager_id']))
                        fields['osmanager_id'] = osmanager.id
                    except Exception:
                        if fields.get('state') != State.LOCKED:
                            raise exceptions.rest.RequestError(gettext('This service requires an OS Manager')) from None
                        del fields['osmanager_id']
                else:
                    del fields['osmanager_id']

                # If service has "overrided fields", overwrite received ones now
                if service_type.overrided_pools_fields:
                    for k, v in service_type.overrided_pools_fields.items():
                        fields[k] = v

                if service_type.uses_cache_l2 is False:
                    fields['cache_l2_srvs'] = 0

                if service_type.uses_cache is False:
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

                    # if service_type.userservices_limit != consts.UNLIMITED:
                    #    fields['max_srvs'] = min((fields['max_srvs'], service_type.userservices_limit))
                    #    fields['initial_srvs'] = min(fields['initial_srvs'], service_type.userservices_limit)
                    #    fields['cache_l1_srvs'] = min(fields['cache_l1_srvs'], service_type.userservices_limit)
            except Exception as e:
                raise exceptions.rest.RequestError(gettext('This parameters provided are not valid')) from e

            # If max < initial or cache_1 or cache_l2
            fields['max_srvs'] = max(
                (
                    int(fields['initial_srvs']),
                    int(fields['cache_l1_srvs']),
                    int(fields['max_srvs']),
                )
            )

            # *** ACCOUNT ***
            account_id = fields['account_id']
            fields['account_id'] = None

            if account_id and account_id != '-1':
                logger.debug('Account id: %s', account_id)
                try:
                    fields['account_id'] = Account.objects.get(uuid=process_uuid(account_id)).id
                except Exception:
                    logger.warning('Getting account ID: %s %s', account_id)

            # **** IMAGE ***
            image_id = fields['image_id']
            fields['image_id'] = None
            if image_id and image_id != '-1':
                logger.debug('Image id: %s', image_id)
                try:
                    image = Image.objects.get(uuid=process_uuid(image_id))
                    fields['image_id'] = image.id
                except Exception:
                    logger.warning('At image recovering: %s', image_id)

            # Servicepool Group
            pool_group_id = fields['pool_group_id']
            del fields['pool_group_id']
            fields['servicesPoolGroup_id'] = None
            if pool_group_id and pool_group_id != '-1':
                logger.debug('pool_group_id: %s', pool_group_id)
                try:
                    spgrp = ServicePoolGroup.objects.get(uuid=process_uuid(pool_group_id))
                    fields['servicesPoolGroup_id'] = spgrp.id
                except Exception:
                    logger.warning('At service pool group recovering: %s', pool_group_id)

        except (exceptions.rest.RequestError, exceptions.rest.ResponseError):
            raise
        except Exception as e:
            raise exceptions.rest.RequestError(str(e)) from e

    def post_save(self, item: 'Model') -> None:
        item = ensure.is_instance(item, ServicePool)
        if self._params.get('publish_on_save', False) is True:
            try:
                item.publish()
            except Exception as e:
                logger.error('Could not publish service pool %s: %s', item.name, e)

    def delete_item(self, item: 'Model') -> None:
        item = ensure.is_instance(item, ServicePool)
        try:
            logger.debug('Deleting %s', item)
            item.remove()  # This will mark it for deletion, but in fact will not delete it directly
        except Exception:
            # Eat it and logit
            logger.exception('deleting service pool')

    # Logs
    def get_logs(self, item: 'Model') -> typing.Any:
        item = ensure.is_instance(item, ServicePool)
        try:
            return log.get_logs(item)
        except Exception:
            return []

    # Set fallback status
    def set_fallback_access(self, item: 'Model') -> typing.Any:
        item = ensure.is_instance(item, ServicePool)
        self.ensure_has_access(item, types.permissions.PermissionType.MANAGEMENT)

        fallback = self._params.get('fallbackAccess', self.params.get('fallback', None))
        if fallback:
            logger.debug('Setting fallback of %s to %s', item.name, fallback)
            item.fallbackAccess = fallback
            item.save()
        return item.fallbackAccess

    def get_fallback_access(self, item: 'Model') -> typing.Any:
        item = ensure.is_instance(item, ServicePool)
        return item.fallbackAccess

    #  Returns the action list based on current element, for calendar
    def actions_list(self, item: 'Model') -> list[types.calendar.CalendarAction]:
        item = ensure.is_instance(item, ServicePool)

        # If item is locked, only allow publish
        if item.state == types.states.State.LOCKED:
            # Only allow publish
            return [
                consts.calendar.CALENDAR_ACTION_PUBLISH,
            ]

        valid_actions: list[types.calendar.CalendarAction] = []
        item_info = item.service.get_type()
        if item_info.uses_cache is True:
            valid_actions += [
                consts.calendar.CALENDAR_ACTION_INITIAL,
                consts.calendar.CALENDAR_ACTION_CACHE_L1,
                consts.calendar.CALENDAR_ACTION_MAX,
            ]
            if item_info.uses_cache_l2 is True:
                valid_actions += [
                    consts.calendar.CALENDAR_ACTION_CACHE_L2,
                ]

        if item_info.publication_type is not None:
            valid_actions += [
                consts.calendar.CALENDAR_ACTION_PUBLISH,
            ]

        # Transport & groups actions
        valid_actions += [
            consts.calendar.CALENDAR_ACTION_ADD_TRANSPORT,
            consts.calendar.CALENDAR_ACTION_DEL_TRANSPORT,
            consts.calendar.CALENDAR_ACTION_DEL_ALL_TRANSPORTS,
            consts.calendar.CALENDAR_ACTION_ADD_GROUP,
            consts.calendar.CALENDAR_ACTION_DEL_GROUP,
            consts.calendar.CALENDAR_ACTION_DEL_ALL_GROUPS,
        ]

        # Advanced actions
        valid_actions += [
            consts.calendar.CALENDAR_ACTION_IGNORE_UNUSED,
            consts.calendar.CALENDAR_ACTION_REMOVE_USERSERVICES,
            consts.calendar.CALENDAR_ACTION_REMOVE_STUCK_USERSERVICES,
            consts.calendar.CALENDAR_ACTION_DISPLAY_CUSTOM_MESSAGE,
        ]
        return valid_actions

    def list_assignables(self, item: 'Model') -> typing.Any:
        item = ensure.is_instance(item, ServicePool)
        service = item.service.get_instance()
        return list(service.enumerate_assignables())

    def create_from_assignable(self, item: 'Model') -> typing.Any:
        item = ensure.is_instance(item, ServicePool)
        if 'user_id' not in self._params or 'assignable_id' not in self._params:
            return self.invalid_request_response('Invalid parameters')

        logger.debug('Creating from assignable: %s', self._params)
        UserServiceManager.manager().create_from_assignable(
            item,
            User.objects.get(uuid__iexact=process_uuid(self._params['user_id'])),
            self._params['assignable_id'],
        )

        return True

    def add_log(self, item: 'Model') -> typing.Any:
        item = ensure.is_instance(item, ServicePool)
        if 'message' not in self._params:
            return self.invalid_request_response('Invalid parameters')
        if 'level' not in self._params:
            return self.invalid_request_response('Invalid parameters')
        
        log.log(
            item,
            level=types.log.LogLevel.from_str(self._params['level']),
            message=self._params['message'],
            source=types.log.LogSource.REST,
            log_name=self._params.get('log_name', None),
        )
        