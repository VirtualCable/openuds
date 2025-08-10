# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2024 Virtual Cable S.L.U.
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
import collections.abc
import dataclasses
import datetime
import logging
import typing

from django.utils.translation import gettext as _
from django.db.models import Model

import uds.core.types.permissions
from uds import models
from uds.core import exceptions, types
from uds.core.managers.userservice import UserServiceManager
from uds.core.types.rest import Table
from uds.core.types.states import State
from uds.core.util import ensure, log, permissions, ui as ui_utils
from uds.core.util.model import process_uuid
from uds.REST.model import DetailHandler


logger = logging.getLogger(__name__)


@dataclasses.dataclass
class UserServiceItem(types.rest.BaseRestItem):
    id: str
    pool_id: str
    unique_id: str
    friendly_name: str
    state: str
    os_state: str
    state_date: datetime.datetime
    creation_date: datetime.datetime
    revision: str
    ip: str
    actor_version: str

    # For cache
    cache_level: int | types.rest.NotRequired = types.rest.NotRequired.field()

    # Optional, used on some cases (e.g. assigned services)
    pool_name: str | types.rest.NotRequired = types.rest.NotRequired.field()

    # For assigned
    owner: str | types.rest.NotRequired = types.rest.NotRequired.field()
    owner_info: dict[str, str] | types.rest.NotRequired = types.rest.NotRequired.field()
    in_use: bool | types.rest.NotRequired = types.rest.NotRequired.field()
    in_use_date: datetime.datetime | types.rest.NotRequired = types.rest.NotRequired.field()
    source_host: str | types.rest.NotRequired = types.rest.NotRequired.field()
    source_ip: str | types.rest.NotRequired = types.rest.NotRequired.field()


class AssignedUserService(DetailHandler[UserServiceItem]):
    """
    Rest handler for Assigned Services, wich parent is Service
    """

    CUSTOM_METHODS = ['reset']

    @staticmethod
    def userservice_item(
        item: models.UserService,
        props: typing.Optional[dict[str, typing.Any]] = None,
        is_cache: bool = False,
    ) -> 'UserServiceItem':
        """
        Converts an assigned/cached service db item to a dictionary for REST response
        Args:
            item: item to convert
            props: properties to include
            is_cache: If item is from cache or not
        """
        if props is None:
            props = dict(item.properties)

        val = UserServiceItem(
            id=item.uuid,
            pool_id=item.deployed_service.uuid,
            unique_id=item.unique_id,
            friendly_name=item.friendly_name,
            state=(
                item.state
                if not (props.get('destroy_after') and item.state == State.PREPARING)
                else State.CANCELING
            ),  # Destroy after means that we need to cancel AFTER finishing preparing, but not before...
            os_state=item.os_state,
            state_date=item.state_date,
            creation_date=item.creation_date,
            revision=item.publication and str(item.publication.revision) or '',
            ip=props.get('ip', _('unknown')),
            actor_version=props.get('actor_version', _('unknown')),
        )

        if is_cache:
            val.cache_level = item.cache_level
        else:
            if item.user is None:
                owner = ''
                owner_info = {'auth_id': '', 'user_id': ''}
            else:
                owner = item.user.pretty_name
                owner_info = {
                    'auth_id': item.user.manager.uuid,
                    'user_id': item.user.uuid,
                }

            val.owner = owner
            val.owner_info = owner_info
            val.in_use = item.in_use
            val.in_use_date = item.in_use_date
            val.source_host = item.src_hostname
            val.source_ip = item.src_ip

        return val

    def get_items(
        self, parent: 'Model', item: typing.Optional[str]
    ) -> types.rest.ItemsResult['UserServiceItem']:
        parent = ensure.is_instance(parent, models.ServicePool)

        try:
            if not item:
                # First, fetch all properties for all assigned services on this pool
                # We can cache them, because they are going to be readed anyway...
                properties: dict[str, typing.Any] = collections.defaultdict(dict)
                for id, key, value in models.Properties.objects.filter(
                    owner_type='userservice',
                    owner_id__in=parent.assigned_user_services().values_list('uuid', flat=True),
                ).values_list('owner_id', 'key', 'value'):
                    properties[id][key] = value

                return [
                    AssignedUserService.userservice_item(k, properties.get(k.uuid, {}))
                    for k in parent.assigned_user_services()
                    .all()
                    .prefetch_related('deployed_service', 'publication', 'user')
                ]
            return AssignedUserService.userservice_item(
                parent.assigned_user_services().get(process_uuid(uuid=process_uuid(item))),
                props={
                    k: v
                    for k, v in models.Properties.objects.filter(
                        owner_type='userservice', owner_id=process_uuid(item)
                    ).values_list('key', 'value')
                },
            )
        except Exception as e:
            logger.error('Error getting user service %s: %s', item, e)
            raise exceptions.rest.ResponseError(_('Error getting user service')) from e

    def get_table(self, parent: 'Model') -> types.rest.Table:
        parent = ensure.is_instance(parent, models.ServicePool)
        table_info = ui_utils.TableBuilder(_('Assigned Services')).datetime_column(
            name='creation_date', title=_('Creation date')
        )
        if parent.service.get_type().publication_type is not None:
            table_info.text_column(name='revision', title=_('Revision'))

        return (
            table_info.text_column(name='unique_id', title='Unique ID')
            .text_column(name='ip', title=_('IP'))
            .text_column(name='friendly_name', title=_('Friendly name'))
            .dict_column(name='state', title=_('status'), dct=State.literals_dict())
            .datetime_column(name='state_date', title=_('Status date'))
            .text_column(name='in_use', title=_('In Use'))
            .text_column(name='source_host', title=_('Src Host'))
            .text_column(name='source_ip', title=_('Src Ip'))
            .text_column(name='owner', title=_('Owner'))
            .text_column(name='actor_version', title=_('Actor version'))
            .row_style(prefix='row-state-', field='state')
        ).build()

    def get_logs(self, parent: 'Model', item: str) -> list[typing.Any]:
        parent = ensure.is_instance(parent, models.ServicePool)
        try:
            user_service: models.UserService = parent.assigned_user_services().get(uuid=process_uuid(item))
            logger.debug('Getting logs for %s', user_service)
            return log.get_logs(user_service)
        except models.UserService.DoesNotExist:
            raise exceptions.rest.NotFound(_('User service not found')) from None
        except Exception as e:
            logger.error('Error getting user service logs for %s: %s', item, e)
            raise exceptions.rest.ResponseError(_('Error getting user service logs')) from e

    # This is also used by CachedService, so we use "userServices" directly and is valid for both
    def delete_item(self, parent: 'Model', item: str, cache: bool = False) -> None:
        parent = ensure.is_instance(parent, models.ServicePool)
        try:
            if cache:
                userservice = parent.cached_users_services().get(uuid=process_uuid(item))
            else:
                userservice = parent.assigned_user_services().get(uuid=process_uuid(item))
        except Exception as e:
            logger.error('Error deleting user service %s from %s: %s', item, parent, e)
            raise exceptions.rest.ResponseError(_('Error deleting user service')) from None

        if userservice.user:  # All assigned services have a user
            log_string = f'Deleted assigned user service {userservice.friendly_name} to user {userservice.user.pretty_name} by {self._user.pretty_name}'
        else:
            log_string = f'Deleted cached user service {userservice.friendly_name} by {self._user.pretty_name}'

        if userservice.state in (State.USABLE, State.REMOVING):
            userservice.release()
        elif userservice.state == State.PREPARING:
            userservice.cancel()
        elif userservice.state == State.REMOVABLE:
            raise exceptions.rest.RequestError(_('Item already being removed')) from None
        else:
            raise exceptions.rest.RequestError(_('Item is not removable')) from None

        log.log(parent, types.log.LogLevel.INFO, log_string, types.log.LogSource.ADMIN)
        log.log(userservice, types.log.LogLevel.INFO, log_string, types.log.LogSource.ADMIN)

    # Only owner is allowed to change right now
    def save_item(self, parent: 'Model', item: typing.Optional[str]) -> typing.Any:
        parent = ensure.is_instance(parent, models.ServicePool)
        if not item:
            raise exceptions.rest.RequestError('Only modify is allowed')
        fields = self.fields_from_params(['auth_id:_', 'user_id:_', 'ip:_'])

        userservice = parent.userServices.get(uuid=process_uuid(item))
        if 'user_id' in fields and 'auth_id' in fields:
            user = models.User.objects.get(uuid=process_uuid(fields['user_id']))

            log_string = f'Changed ownership of user service {userservice.friendly_name} from {userservice.user} to {user.pretty_name} by {self._user.pretty_name}'

            # If there is another service that has this same owner, raise an exception
            if (
                parent.userServices.filter(user=user)
                .exclude(uuid=userservice.uuid)
                .exclude(state__in=State.INFO_STATES)
                .count()
                > 0
            ):
                raise exceptions.rest.RequestError(
                    f'There is already another user service assigned to {user.pretty_name}'
                )

            userservice.user = user
            userservice.save()
        elif 'ip' in fields:
            log_string = f'Changed IP of user service {userservice.friendly_name} to {fields["ip"]} by {self._user.pretty_name}'
            userservice.log_ip(fields['ip'])
        else:
            raise exceptions.rest.RequestError('Invalid fields')

        # Log change
        log.log(parent, types.log.LogLevel.INFO, log_string, types.log.LogSource.ADMIN)
        log.log(userservice, types.log.LogLevel.INFO, log_string, types.log.LogSource.ADMIN)

        return {'id': userservice.uuid}

    def reset(self, parent: 'models.ServicePool', item: str) -> typing.Any:
        userservice = parent.userServices.get(uuid=process_uuid(item))
        UserServiceManager.manager().reset(userservice)


class CachedService(AssignedUserService):
    """
    Rest handler for Cached Services, which parent is ServicePool
    """

    CUSTOM_METHODS = []  # Remove custom methods from assigned services

    def get_items(
        self, parent: 'Model', item: typing.Optional[str]
    ) -> types.rest.ItemsResult['UserServiceItem']:
        parent = ensure.is_instance(parent, models.ServicePool)

        try:
            if not item:
                return [
                    AssignedUserService.userservice_item(k, is_cache=True)
                    for k in parent.cached_users_services()
                    .all()
                    .prefetch_related('deployed_service', 'publication')
                ]
            cached_userservice: models.UserService = parent.cached_users_services().get(uuid=process_uuid(item))
            return AssignedUserService.userservice_item(cached_userservice, is_cache=True)
        except models.UserService.DoesNotExist:
            raise exceptions.rest.NotFound(_('User service not found')) from None
        except Exception as e:
            logger.error('Error getting user service %s: %s', item, e)
            raise exceptions.rest.ResponseError(_('Error getting user service')) from e

    def get_table(self, parent: 'Model') -> types.rest.Table:
        parent = ensure.is_instance(parent, models.ServicePool)
        table_info = (
            ui_utils.TableBuilder(_('Cached Services'))
            .datetime_column(name='creation_date', title=_('Creation date'))
            .text_column(name='revision', title=_('Revision'))
            .text_column(name='unique_id', title='Unique ID')
            .text_column(name='ip', title=_('IP'))
            .text_column(name='friendly_name', title=_('Friendly name'))
            .dict_column(name='state', title=_('State'), dct=State.literals_dict())
        )
        if parent.state != State.LOCKED:
            table_info = table_info.text_column(name='cache_level', title=_('Cache level')).text_column(
                name='actor_version', title=_('Actor version')
            )

        return table_info.build()

    def delete_item(self, parent: 'Model', item: str, cache: bool = False) -> None:
        return super().delete_item(parent, item, cache=True)

    def get_logs(self, parent: 'Model', item: str) -> list[typing.Any]:
        parent = ensure.is_instance(parent, models.ServicePool)
        try:
            userservice = parent.cached_users_services().get(uuid=process_uuid(item))
            logger.debug('Getting logs for %s', item)
            return log.get_logs(userservice)
        except Exception as e:
            logger.error('Error getting user service logs for %s: %s', item, e)
            raise exceptions.rest.ResponseError(_('Error getting user service logs')) from None


@dataclasses.dataclass
class GroupItem(types.rest.BaseRestItem):
    id: str
    auth_id: str
    name: str
    group_name: str
    comments: str
    state: str
    type: str
    auth_name: str


class Groups(DetailHandler[GroupItem]):
    """
    Processes the groups detail requests of a Service Pool
    """

    def get_items(self, parent: 'Model', item: typing.Optional[str]) -> list['GroupItem']:
        parent = typing.cast(typing.Union['models.ServicePool', 'models.MetaPool'], parent)

        return [
            GroupItem(
                id=group.uuid,
                auth_id=group.manager.uuid,
                name=group.name,
                group_name=group.pretty_name,
                comments=group.comments,
                state=group.state,
                type='meta' if group.is_meta else 'group',
                auth_name=group.manager.name,
            )
            for group in typing.cast(collections.abc.Iterable[models.Group], parent.assignedGroups.all())
        ]

    def get_table(self, parent: 'Model') -> Table:
        parent = typing.cast(typing.Union['models.ServicePool', 'models.MetaPool'], parent)
        return (
            ui_utils.TableBuilder(_('Assigned groups'))
            .text_column(name='group_name', title=_('Name'))
            .text_column(name='comments', title=_('comments'))
            .dict_column(name='state', title=_('State'), dct=State.literals_dict())
            .row_style(prefix='row-state-', field='state')
            .build()
        )

    def save_item(self, parent: 'Model', item: typing.Optional[str]) -> typing.Any:
        parent = typing.cast(typing.Union['models.ServicePool', 'models.MetaPool'], parent)

        group: models.Group = models.Group.objects.get(uuid=process_uuid(self._params['id']))
        parent.assignedGroups.add(group)
        log.log(
            parent,
            types.log.LogLevel.INFO,
            f'Added group {group.pretty_name} by {self._user.pretty_name}',
            types.log.LogSource.ADMIN,
        )

        return {'id': group.uuid}

    def delete_item(self, parent: 'Model', item: str) -> None:
        parent = typing.cast(typing.Union['models.ServicePool', 'models.MetaPool'], parent)
        group: models.Group = models.Group.objects.get(uuid=process_uuid(self._args[0]))
        parent.assignedGroups.remove(group)
        log.log(
            parent,
            types.log.LogLevel.INFO,
            f'Removed group {group.pretty_name} by {self._user.pretty_name}',
            types.log.LogSource.ADMIN,
        )


@dataclasses.dataclass
class TransportItem(types.rest.BaseRestItem):
    id: str
    name: str
    type: dict[str, typing.Any]  # TypeInfo
    comments: str
    priority: int
    trans_type: str


class Transports(DetailHandler[TransportItem]):
    """
    Processes the transports detail requests of a Service Pool
    """

    def get_items(self, parent: 'Model', item: typing.Optional[str]) -> list['TransportItem']:
        parent = ensure.is_instance(parent, models.ServicePool)

        return [
            TransportItem(
                id=trans.uuid,
                name=trans.name,
                type=self.as_typeinfo(trans.get_type()).as_dict(),
                comments=trans.comments,
                priority=trans.priority,
                trans_type=trans.get_type().mod_name(),
            )
            for trans in parent.transports.all()
        ]

    def get_table(self, parent: 'Model') -> Table:
        parent = ensure.is_instance(parent, models.ServicePool)
        return (
            ui_utils.TableBuilder(_('Assigned transports'))
            .numeric_column(name='priority', title=_('Priority'), width='6em')
            .text_column(name='name', title=_('Name'))
            .text_column(name='trans_type', title=_('Type'))
            .text_column(name='comments', title=_('Comments'))
            .build()
        )

    def save_item(self, parent: 'Model', item: typing.Optional[str]) -> typing.Any:
        parent = ensure.is_instance(parent, models.ServicePool)
        transport: models.Transport = models.Transport.objects.get(uuid=process_uuid(self._params['id']))
        parent.transports.add(transport)
        log.log(
            parent,
            types.log.LogLevel.INFO,
            f'Added transport {transport.name} by {self._user.pretty_name}',
            types.log.LogSource.ADMIN,
        )

        return {'id': transport.uuid}

    def delete_item(self, parent: 'Model', item: str) -> None:
        parent = ensure.is_instance(parent, models.ServicePool)
        transport: models.Transport = models.Transport.objects.get(uuid=process_uuid(self._args[0]))
        parent.transports.remove(transport)
        log.log(
            parent,
            types.log.LogLevel.INFO,
            f'Removed transport {transport.name} by {self._user.pretty_name}',
            types.log.LogSource.ADMIN,
        )


@dataclasses.dataclass
class PublicationItem(types.rest.BaseRestItem):
    id: str
    revision: int
    publish_date: datetime.datetime
    state: str
    reason: str
    state_date: datetime.datetime


class Publications(DetailHandler[PublicationItem]):
    """
    Processes the publications detail requests of a Service Pool
    """

    CUSTOM_METHODS = ['publish', 'cancel']  # We provided these custom methods

    def publish(self, parent: 'Model') -> typing.Any:
        """
        Custom method "publish", provided to initiate a publication of a deployed service
        :param parent: Parent service pool
        """
        parent = ensure.is_instance(parent, models.ServicePool)
        change_log = self._params['changelog'] if 'changelog' in self._params else None

        if (
            permissions.has_access(self._user, parent, uds.core.types.permissions.PermissionType.MANAGEMENT)
            is False
        ):
            logger.debug('Management Permission failed for user %s', self._user)
            raise exceptions.rest.AccessDenied(_('Access denied to publish service pool')) from None

        logger.debug('Custom "publish" invoked for %s', parent)
        parent.publish(change_log)  # Can raise exceptions that will be processed on response

        log.log(
            parent,
            types.log.LogLevel.INFO,
            f'Initiated publication v{parent.current_pub_revision} by {self._user.pretty_name}',
            types.log.LogSource.ADMIN,
        )

        return self.success()

    def cancel(self, parent: 'Model', uuid: str) -> typing.Any:
        """
        Invoked to cancel a running publication
        Double invocation (this means, invoking cancel twice) will mean that is a "forced cancelation"
        :param parent: Parent service pool
        :param uuid: uuid of the publication
        """
        parent = ensure.is_instance(parent, models.ServicePool)
        if (
            permissions.has_access(self._user, parent, uds.core.types.permissions.PermissionType.MANAGEMENT)
            is False
        ):
            logger.debug('Management Permission failed for user %s', self._user)
            raise exceptions.rest.AccessDenied(_('Access denied to cancel service pool publication')) from None

        try:
            ds = models.ServicePoolPublication.objects.get(uuid=process_uuid(uuid))
            ds.cancel()
        except Exception as e:
            raise exceptions.rest.ResponseError(str(e)) from e

        log.log(
            parent,
            types.log.LogLevel.INFO,
            f'Canceled publication v{parent.current_pub_revision} by {self._user.pretty_name}',
            types.log.LogSource.ADMIN,
        )

        return self.success()

    def get_items(self, parent: 'Model', item: typing.Optional[str]) -> list['PublicationItem']:
        parent = ensure.is_instance(parent, models.ServicePool)
        return [
            PublicationItem(
                id=i.uuid,
                revision=i.revision,
                publish_date=i.publish_date,
                state=i.state,
                reason=State.from_str(i.state).is_errored() and i.get_instance().error_reason() or '',
                state_date=i.state_date,
            )
            for i in parent.publications.all()
        ]

    def get_table(self, parent: 'Model') -> Table:
        parent = ensure.is_instance(parent, models.ServicePool)
        return (
            ui_utils.TableBuilder(_('Publications'))
            .numeric_column(name='revision', title=_('Revision'), width='6em')
            .datetime_column(name='publish_date', title=_('Publish date'))
            .dict_column(name='state', title=_('State'), dct=State.literals_dict())
            .text_column(name='reason', title=_('Reason'))
            .row_style(prefix='row-state-', field='state')
        ).build()


@dataclasses.dataclass
class ChangelogItem(types.rest.BaseRestItem):
    revision: int
    stamp: datetime.datetime
    log: str


class Changelog(DetailHandler[ChangelogItem]):
    """
    Processes the transports detail requests of a Service Pool
    """

    def get_items(self, parent: 'Model', item: typing.Optional[str]) -> list['ChangelogItem']:
        parent = ensure.is_instance(parent, models.ServicePool)
        return [
            ChangelogItem(
                revision=i.revision,
                stamp=i.stamp,
                log=i.log,
            )
            for i in parent.changelog.all()
        ]

    def get_table(self, parent: 'Model') -> types.rest.Table:
        parent = ensure.is_instance(parent, models.ServicePool)
        return (
            ui_utils.TableBuilder(_('Changelog'))
            .numeric_column(name='revision', title=_('Revision'), width='6em')
            .datetime_column(name='stamp', title=_('Publish date'))
            .text_column(name='log', title=_('Comment'))
        ).build()
