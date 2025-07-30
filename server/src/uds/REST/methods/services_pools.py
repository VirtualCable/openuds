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
from uds.core import ui
from uds.core.consts.images import DEFAULT_THUMB_BASE64
from uds.core.util import log, permissions, ensure, ui as ui_utils
from uds.core.util.config import GlobalConfig
from uds.core.util.model import sql_now, process_uuid
from uds.core.types.states import State
from uds.models import Account, Image, OSManager, Service, ServicePool, ServicePoolGroup, User
from uds.REST.model import ModelHandler

from .op_calendars import AccessCalendars, ActionsCalendars
from .services import Services, ServiceInfo
from .user_services import AssignedUserService, CachedService, Changelog, Groups, Publications, Transports

if typing.TYPE_CHECKING:
    from django.db.models import Model

logger = logging.getLogger(__name__)


class ServicePoolItem(types.rest.BaseRestItem):
    id: str
    name: str
    short_name: str
    tags: typing.List[str]
    parent: str
    parent_type: str
    comments: str
    state: str
    thumb: str
    account: str
    account_id: str | None
    service_id: str
    provider_id: str
    image_id: str | None
    initial_srvs: int
    cache_l1_srvs: int
    cache_l2_srvs: int
    max_srvs: int
    show_transports: bool
    visible: bool
    allow_users_remove: bool
    allow_users_reset: bool
    ignores_unused: bool
    fallbackAccess: str
    meta_member: list[dict[str, str]]
    calendar_message: str
    custom_message: str
    display_custom_message: bool
    osmanager_id: str | None

    user_services_count: typing.NotRequired[int]
    user_services_in_preparation: typing.NotRequired[int]
    user_services_in_preparation: typing.NotRequired[int]
    restrained: typing.NotRequired[bool]
    permission: typing.NotRequired[int]
    info: typing.NotRequired[ServiceInfo]
    pool_group_id: typing.NotRequired[str | None]
    pool_group_name: typing.NotRequired[str]
    pool_group_thumb: typing.NotRequired[str]
    usage: typing.NotRequired[str]


class ServicesPools(ModelHandler[ServicePoolItem]):
    """
    Handles Services Pools REST requests
    """

    MODEL = ServicePool
    DETAIL = {
        'services': AssignedUserService,
        'cache': CachedService,
        'servers': CachedService,  # Alias for cache, but will change in a future release
        'groups': Groups,
        'transports': Transports,
        'publications': Publications,
        'changelog': Changelog,
        'access': AccessCalendars,
        'actions': ActionsCalendars,
    }

    FIELDS_TO_SAVE = [
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

    EXCLUDED_FIELDS = ['osmanager_id', 'service_id']

    TABLE = (
        ui_utils.TableBuilder(_('Service Pools'))
        .text_column(name='name', title=_('Name'))
        .dict_column(name='state', title=_('Status'), dct=State.literals_dict())
        .numeric_column(name='user_services_count', title=_('User services'))
        .numeric_column(name='user_services_in_preparation', title=_('In Preparation'))
        .text_column(name='usage', title=_('Usage'))
        .boolean(name='visible', title=_('Visible'))
        .boolean(name='show_transports', title=_('Shows transports'))
        .text_column(name='pool_group_name', title=_('Pool group'))
        .text_column(name='parent', title=_('Parent service'))
        .text_column(name='tags', title=_('tags'), visible=False)
        .row_style(prefix='row-state-', field='state')
        .build()
    )

    CUSTOM_METHODS = [
        types.rest.ModelCustomMethod('set_fallback_access', True),
        types.rest.ModelCustomMethod('get_fallback_access', True),
        types.rest.ModelCustomMethod('actions_list', True),
        types.rest.ModelCustomMethod('list_assignables', True),
        types.rest.ModelCustomMethod('create_from_assignable', True),
        types.rest.ModelCustomMethod('add_log', True),
    ]

    def get_items(
        self, *args: typing.Any, **kwargs: typing.Any
    ) -> typing.Generator[ServicePoolItem, None, None]:
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

    def item_as_dict(self, item: 'Model') -> ServicePoolItem:
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
        val: ServicePoolItem = {
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
            'osmanager_id': item.osmanager.uuid if item.osmanager else None,
        }
        if summary:
            return val

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

        val['state'] = state
        val['thumb'] = item.image.thumb64 if item.image is not None else DEFAULT_THUMB_BASE64
        val['user_services_count'] = valid_count
        val['user_services_in_preparation'] = preparing_count
        val['tags'] = [tag.tag for tag in item.tags.all()]
        val['restrained'] = restrained
        val['permission'] = permissions.effective_permissions(self._user, item)
        val['info'] = Services.service_info(item.service)
        val['pool_group_id'] = poolgroup_id
        val['pool_group_name'] = poolgroup_name
        val['pool_group_thumb'] = poolgroup_thumb
        val['usage'] = str(item.usage(usage_count).percent) + '%'

        return val

    # Gui related
    def get_gui(self, for_type: str) -> list[types.ui.GuiElement]:
        # if OSManager.objects.count() < 1:  # No os managers, can't create db
        #    raise exceptions.rest.ResponseError(gettext('Create at least one OS Manager before creating a new service pool'))
        if Service.objects.count() < 1:
            raise exceptions.rest.ResponseError(
                gettext('Create at least a service before creating a new service pool')
            )

        gui = (
            (
                ui_utils.GuiBuilder()
                .add_stock_field(types.rest.stock.StockField.NAME)
                .add_stock_field(types.rest.stock.StockField.COMMENTS)
                .add_stock_field(types.rest.stock.StockField.TAGS)
            )
            .set_order(-95)
            .add_text(
                name='short_name',
                label=gettext('Short name'),
                tooltip=gettext('Short name for user service visualization'),
                length=32,
            )
            .set_order(100)
            .add_choice(
                name='service_id',
                choices=[ui.gui.choice_item('', '')]
                + ui.gui.sorted_choices(
                    [ui.gui.choice_item(v.uuid, v.provider.name + '\\' + v.name) for v in Service.objects.all()]
                ),
                label=gettext('Base service'),
                tooltip=gettext('Service used as base of this service pool'),
                readonly=True,
            )
            .add_choice(
                name='osmanager_id',
                choices=[ui.gui.choice_item(-1, '')]
                + ui.gui.sorted_choices([ui.gui.choice_item(v.uuid, v.name) for v in OSManager.objects.all()]),
                label=gettext('OS Manager'),
                tooltip=gettext('OS Manager used as base of this service pool'),
                readonly=True,
            )
            .add_checkbox(
                name='publish_on_save',
                default=True,
                label=gettext('Publish on save'),
                tooltip=gettext('If active, the service will be published when saved'),
            )
            .new_tab(types.ui.Tab.DISPLAY)
            .add_checkbox(
                name='visible',
                default=True,
                label=gettext('Visible'),
                tooltip=gettext('If active, transport will be visible for users'),
            )
            .add_image_choice()
            .add_image_choice(
                name='pool_group_id',
                choices=[
                    ui.gui.choice_image(v.uuid, v.name, v.thumb64) for v in ServicePoolGroup.objects.all()
                ],
                label=gettext('Pool group'),
                tooltip=gettext('Pool group for this pool (for pool classify on display)'),
            )
            .add_text(
                name='calendar_message',
                label=gettext('Calendar access denied text'),
                tooltip=gettext('Custom message to be shown to users if access is limited by calendar rules.'),
            )
            .add_text(
                name='custom_message',
                label=gettext('Custom launch message text'),
                tooltip=gettext(
                    'Custom message to be shown to users, if active, when trying to start a service from this pool.'
                ),
            )
            .add_checkbox(
                name='display_custom_message',
                default=False,
                label=gettext('Enable custom launch message'),
                tooltip=gettext('If active, the custom launch message will be shown to users'),
            )
            .new_tab(gettext('Availability'))
            .add_numeric(
                name='initial_srvs',
                default=0,
                min_value=0,
                label=gettext('Initial available services'),
                tooltip=gettext('Services created initially for this service pool'),
            )
            .add_numeric(
                name='cache_l1_srvs',
                default=0,
                min_value=0,
                label=gettext('Services to keep in cache'),
                tooltip=gettext('Services kept in cache for improved user service assignation'),
            )
            .add_numeric(
                name='cache_l2_srvs',
                default=0,
                min_value=0,
                label=gettext('Services to keep in L2 cache'),
                tooltip=gettext('Services kept in cache of level2 for improved service assignation'),
            )
            .add_numeric(
                name='max_srvs',
                default=0,
                min_value=0,
                label=gettext('Max services per user'),
                tooltip=gettext('Maximum number of services that can be assigned to a user from this pool'),
            )
            .add_checkbox(
                name='show_transports',
                default=False,
                label=gettext('Show transports'),
                tooltip=gettext('If active, transports will be shown to users'),
            )
            .new_tab(types.ui.Tab.ADVANCED)
            .add_checkbox(
                name='allow_users_remove',
                default=False,
                label=gettext('Allow removal by users'),
                tooltip=gettext(
                    'If active, the user will be allowed to remove the service "manually". Be careful with this, because the user will have the "power" to delete its own service'
                ),
            )
            .add_checkbox(
                name='allow_users_reset',
                default=False,
                label=gettext('Allow reset by users'),
                tooltip=gettext('If active, the user will be allowed to reset the service'),
            )
            .add_checkbox(
                name='ignores_unused',
                default=False,
                label=gettext('Ignores unused'),
                tooltip=gettext(
                    'If the option is enabled, UDS will not attempt to detect and remove the user services assigned but not in use.'
                ),
            )
            .add_choice(
                name='account_id',
                choices=[ui.gui.choice_item('', '')]
                + ui.gui.sorted_choices([ui.gui.choice_item(v.uuid, v.name) for v in Account.objects.all()]),
                label=gettext('Account'),
                tooltip=gettext('Account used for this service pool'),
                readonly=True,
            )
        )
        return gui.build()

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
                            raise exceptions.rest.RequestError(
                                gettext('This service requires an OS Manager')
                            ) from None
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
                raise exceptions.rest.RequestError(gettext('This service requires an OS Manager')) from e

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
            logger.debug('Account id: %s', account_id)

            if account_id != '-1':
                try:
                    fields['account_id'] = Account.objects.get(uuid=process_uuid(account_id)).id
                except Exception:
                    logger.exception('Getting account ID')

            # **** IMAGE ***
            image_id = fields['image_id']
            fields['image_id'] = None
            logger.debug('Image id: %s', image_id)
            try:
                if image_id != '-1':
                    image = Image.objects.get(uuid=process_uuid(image_id))
                    fields['image_id'] = image.id
            except Exception:
                logger.exception('At image recovering')

            # Servicepool Group
            pool_group_id = fields['pool_group_id']
            del fields['pool_group_id']
            fields['servicesPoolGroup_id'] = None
            logger.debug('pool_group_id: %s', pool_group_id)
            try:
                if pool_group_id != '-1':
                    spgrp = ServicePoolGroup.objects.get(uuid=process_uuid(pool_group_id))
                    fields['servicesPoolGroup_id'] = spgrp.id
            except Exception:
                logger.exception('At service pool group recovering')

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
        self.check_access(item, types.permissions.PermissionType.MANAGEMENT)

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
