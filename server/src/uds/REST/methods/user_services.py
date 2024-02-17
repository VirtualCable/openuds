# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2021 Virtual Cable S.L.
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

from django.utils.translation import gettext as _

import uds.core.types.permissions
from uds import models
from uds.core import exceptions, types
from uds.core.managers.userservice import UserServiceManager
from uds.core.types.states import State
from uds.core.util import ensure, log, permissions
from uds.core.util.model import process_uuid
from uds.REST.model import DetailHandler

if typing.TYPE_CHECKING:
    from django.db.models import Model

logger = logging.getLogger(__name__)


class AssignedService(DetailHandler):
    """
    Rest handler for Assigned Services, wich parent is Service
    """

    custom_methods = [
        'reset',
    ]

    custom_methods = ['reset']

    @staticmethod
    def item_as_dict(
        item: models.UserService,
        props: typing.Optional[dict[str, typing.Any]] = None,
        is_cache: bool = False,
    ) -> dict[str, typing.Any]:
        """
        Converts an assigned/cached service db item to a dictionary for REST response
        :param item: item to convert
        :param is_cache: If item is from cache or not
        """
        if props is None:
            props = dict(item.properties)

        val = {
            'id': item.uuid,
            'id_deployed_service': item.deployed_service.uuid,
            'unique_id': item.unique_id,
            'friendly_name': item.friendly_name,
            'state': item.state
            if not (props.get('destroy_after') and item.state == State.PREPARING)
            else State.CANCELING,  # Destroy after means that we need to cancel AFTER finishing preparing, but not before...
            'os_state': item.os_state,
            'state_date': item.state_date,
            'creation_date': item.creation_date,
            'revision': item.publication and item.publication.revision or '',
            'ip': props.get('ip', _('unknown')),
            'actor_version': props.get('actor_version', _('unknown')),
        }

        if is_cache:
            val['cache_level'] = item.cache_level
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

            val.update(
                {
                    'owner': owner,
                    'owner_info': owner_info,
                    'in_use': item.in_use,
                    'in_use_date': item.in_use_date,
                    'source_host': item.src_hostname,
                    'source_ip': item.src_ip,
                }
            )
        return val

    def get_items(self, parent: 'Model', item: typing.Optional[str]):
        parent = ensure.is_instance(parent, models.ServicePool)
        # Extract provider
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
                    AssignedService.item_as_dict(k, properties.get(k.uuid, {}))
                    for k in parent.assigned_user_services()
                    .all()
                    .prefetch_related('deployed_service', 'publication', 'user')
                ]
            return AssignedService.item_as_dict(
                parent.assigned_user_services().get(process_uuid(uuid=process_uuid(item))),
                props={
                    k: v
                    for k, v in models.Properties.objects.filter(
                        owner_type='userservice', owner_id=process_uuid(item)
                    ).values_list('key', 'value')
                },
            )
        except Exception as e:
            logger.exception('get_items')
            raise self.invalid_item_response() from e

    def get_title(self, parent: 'Model') -> str:
        return _('Assigned services')

    def get_fields(self, parent: 'Model') -> list[typing.Any]:
        parent = ensure.is_instance(parent, models.ServicePool)
        # Revision is only shown if publication type is not None
        return [
            {'creation_date': {'title': _('Creation date'), 'type': 'datetime'}},
        ] + ([
            {'revision': {'title': _('Revision')}},
        ] if parent.service.get_type().publication_type is not None else []) + [
            {'unique_id': {'title': 'Unique ID'}},
            {'ip': {'title': _('IP')}},
            {'friendly_name': {'title': _('Friendly name')}},
            {
                'state': {
                    'title': _('status'),
                    'type': 'dict',
                    'dict': State.literals_dict(),
                }
            },
            {'state_date': {'title': _('Status date'), 'type': 'datetime'}},
            {'in_use': {'title': _('In Use')}},
            {'source_host': {'title': _('Src Host')}},
            {'source_ip': {'title': _('Src Ip')}},
            {'owner': {'title': _('Owner')}},
            {'actor_version': {'title': _('Actor version')}},
        ]

    def get_row_style(self, parent: 'Model') -> types.ui.RowStyleInfo:
        return types.ui.RowStyleInfo(prefix='row-state-', field='state')

    def get_logs(self, parent: 'Model', item: str) -> list[typing.Any]:
        parent = ensure.is_instance(parent, models.ServicePool)
        try:
            userService: models.UserService = parent.assigned_user_services().get(uuid=process_uuid(item))
            logger.debug('Getting logs for %s', userService)
            return log.get_logs(userService)
        except Exception as e:
            raise self.invalid_item_response() from e

    # This is also used by CachedService, so we use "userServices" directly and is valid for both
    def delete_item(self, parent: 'Model', item: str) -> None:
        parent = ensure.is_instance(parent, models.ServicePool)
        try:
            userService: models.UserService = parent.userServices.get(uuid=process_uuid(item))
        except Exception as e:
            logger.exception('delete_item')
            raise self.invalid_item_response() from e

        if userService.user:
            logStr = f'Deleted assigned service {userService.friendly_name} to user {userService.user.pretty_name} by {self._user.pretty_name}'
        else:
            logStr = f'Deleted cached service {userService.friendly_name} by {self._user.pretty_name}'

        if userService.state in (State.USABLE, State.REMOVING):
            userService.remove()
        elif userService.state == State.PREPARING:
            userService.cancel()
        elif userService.state == State.REMOVABLE:
            raise self.invalid_item_response(_('Item already being removed'))
        else:
            raise self.invalid_item_response(_('Item is not removable'))

        log.log(parent, log.LogLevel.INFO, logStr, log.LogSource.ADMIN)

    # Only owner is allowed to change right now
    def save_item(self, parent: 'Model', item: typing.Optional[str]) -> None:
        parent = ensure.is_instance(parent, models.ServicePool)
        if not item:
            raise self.invalid_item_response('Only modify is allowed')
        fields = self.fields_from_params(['auth_id', 'user_id'])
        userService = parent.userServices.get(uuid=process_uuid(item))
        user = models.User.objects.get(uuid=process_uuid(fields['user_id']))

        logStr = f'Changed ownership of service {userService.friendly_name} from {userService.user} to {user.pretty_name} by {self._user.pretty_name}'

        # If there is another service that has this same owner, raise an exception
        if (
            parent.userServices.filter(user=user)
            .exclude(uuid=userService.uuid)
            .exclude(state__in=State.INFO_STATES)
            .count()
            > 0
        ):
            raise self.invalid_response_response(
                f'There is already another user service assigned to {user.pretty_name}'
            )

        userService.user = user  # type: ignore
        userService.save()

        # Log change
        log.log(parent, log.LogLevel.INFO, logStr, log.LogSource.ADMIN)

    def reset(self, parent: 'models.ServicePool', item: str) -> typing.Any:
        userService = parent.userServices.get(uuid=process_uuid(item))
        UserServiceManager().reset(userService)


class CachedService(AssignedService):
    """
    Rest handler for Cached Services, wich parent is Service
    """

    custom_methods: typing.ClassVar[list[str]] = []  # Remove custom methods from assigned services

    def get_items(self, parent: 'Model', item: typing.Optional[str]):
        parent = ensure.is_instance(parent, models.ServicePool)
        # Extract provider
        try:
            if not item:
                return [
                    AssignedService.item_as_dict(k, is_cache=True)
                    for k in parent.cached_users_services()
                    .all()
                    .prefetch_related('deployed_service', 'publication')
                ]
            cachedService: models.UserService = parent.cached_users_services().get(uuid=process_uuid(item))
            return AssignedService.item_as_dict(cachedService, is_cache=True)
        except Exception as e:
            logger.exception('get_items')
            raise self.invalid_item_response() from e

    def get_title(self, parent: 'Model') -> str:
        return _('Cached services')

    def get_fields(self, parent: 'Model') -> list[typing.Any]:
        return [
            {'creation_date': {'title': _('Creation date'), 'type': 'datetime'}},
            {'revision': {'title': _('Revision')}},
            {'unique_id': {'title': 'Unique ID'}},
            {'ip': {'title': _('IP')}},
            {'friendly_name': {'title': _('Friendly name')}},
            {
                'state': {
                    'title': _('State'),
                    'type': 'dict',
                    'dict': State.literals_dict(),
                }
            },
            {'cache_level': {'title': _('Cache level')}},
            {'actor_version': {'title': _('Actor version')}},
        ]

    def get_logs(self, parent: 'Model', item: str) -> list[typing.Any]:
        parent = ensure.is_instance(parent, models.ServicePool)
        try:
            userService = parent.cached_users_services().get(uuid=process_uuid(item))
            logger.debug('Getting logs for %s', item)
            return log.get_logs(userService)
        except Exception:
            raise self.invalid_item_response() from None


class Groups(DetailHandler):
    """
    Processes the groups detail requests of a Service Pool
    """

    def get_items(self, parent: 'Model', item: typing.Optional[str]):
        parent = ensure.is_instance(parent, models.ServicePool)
        group: models.Group
        return [
            {
                'id': group.uuid,
                'auth_id': group.manager.uuid,
                'name': group.name,
                'group_name': group.pretty_name,
                'comments': group.comments,
                'state': group.state,
                'type': 'meta' if group.is_meta else 'group',
                'auth_name': group.manager.name,
            }
            for group in parent.assignedGroups.all()
        ]

    def get_title(self, parent: 'Model') -> str:
        parent = ensure.is_instance(parent, models.ServicePool)
        return _('Assigned groups')

    def get_fields(self, parent: 'Model') -> list[typing.Any]:
        return [
            # Note that this field is "self generated" on client table
            {
                'group_name': {
                    'title': _('Name'),
                    'type': 'alphanumeric',
                }
            },
            {'comments': {'title': _('comments')}},
            {
                'type': {
                    'title': _('Type'),
                    # Alphanumeric, default is alphanumeric
                }
            },
            {
                'state': {
                    'title': _('State'),
                    'type': 'dict',
                    'dict': State.literals_dict(),
                }
            },
        ]

    def get_row_style(self, parent: 'Model') -> types.ui.RowStyleInfo:
        return types.ui.RowStyleInfo(prefix='row-state-', field='state')

    def save_item(self, parent: 'Model', item: typing.Optional[str]) -> None:
        parent = ensure.is_instance(parent, models.ServicePool)
        group: models.Group = models.Group.objects.get(uuid=process_uuid(self._params['id']))
        parent.assignedGroups.add(group)
        log.log(
            parent,
            log.LogLevel.INFO,
            f'Added group {group.pretty_name} by {self._user.pretty_name}',
            log.LogSource.ADMIN,
        )

    def delete_item(self, parent: 'Model', item: str) -> None:
        parent = ensure.is_instance(parent, models.ServicePool)
        group: models.Group = models.Group.objects.get(uuid=process_uuid(self._args[0]))
        parent.assignedGroups.remove(group)
        log.log(
            parent,
            log.LogLevel.INFO,
            f'Removed group {group.pretty_name} by {self._user.pretty_name}',
            log.LogSource.ADMIN,
        )


class Transports(DetailHandler):
    """
    Processes the transports detail requests of a Service Pool
    """

    def get_items(self, parent: 'Model', item: typing.Optional[str]):
        parent = ensure.is_instance(parent, models.ServicePool)

        def get_type(trans: 'models.Transport'):
            try:
                return self.type_as_dict(trans.get_type())
            except Exception:  # No type found
                return None

        return [
            {
                'id': i.uuid,
                'name': i.name,
                'type': get_type(i),
                'comments': i.comments,
                'priority': i.priority,
                'trans_type': _(i.get_type().name()),
            }
            for i in parent.transports.all()
            if get_type(i)
        ]

    def get_title(self, parent: 'Model') -> str:
        parent = ensure.is_instance(parent, models.ServicePool)
        return _('Assigned transports')

    def get_fields(self, parent: 'Model') -> list[typing.Any]:
        return [
            {'priority': {'title': _('Priority'), 'type': 'numeric', 'width': '6em'}},
            {'name': {'title': _('Name')}},
            {'trans_type': {'title': _('Type')}},
            {'comments': {'title': _('Comments')}},
        ]

    def save_item(self, parent: 'Model', item: typing.Optional[str]) -> None:
        parent = ensure.is_instance(parent, models.ServicePool)
        transport: models.Transport = models.Transport.objects.get(uuid=process_uuid(self._params['id']))
        parent.transports.add(transport)
        log.log(
            parent,
            log.LogLevel.INFO,
            f'Added transport {transport.name} by {self._user.pretty_name}',
            log.LogSource.ADMIN,
        )

    def delete_item(self, parent: 'Model', item: str) -> None:
        parent = ensure.is_instance(parent, models.ServicePool)
        transport: models.Transport = models.Transport.objects.get(uuid=process_uuid(self._args[0]))
        parent.transports.remove(transport)
        log.log(
            parent,
            log.LogLevel.INFO,
            f'Removed transport {transport.name} by {self._user.pretty_name}',
            log.LogSource.ADMIN,
        )


class Publications(DetailHandler):
    """
    Processes the publications detail requests of a Service Pool
    """

    custom_methods = ['publish', 'cancel']  # We provided these custom methods

    def publish(self, parent: 'Model'):
        """
        Custom method "publish", provided to initiate a publication of a deployed service
        :param parent: Parent service pool
        """
        parent = ensure.is_instance(parent, models.ServicePool)
        changeLog = self._params['changelog'] if 'changelog' in self._params else None

        if (
            permissions.has_access(self._user, parent, uds.core.types.permissions.PermissionType.MANAGEMENT)
            is False
        ):
            logger.debug('Management Permission failed for user %s', self._user)
            raise self.access_denied_response()

        logger.debug('Custom "publish" invoked for %s', parent)
        parent.publish(changeLog)  # Can raise exceptions that will be processed on response

        log.log(
            parent,
            log.LogLevel.INFO,
            f'Initiated publication v{parent.current_pub_revision} by {self._user.pretty_name}',
            log.LogSource.ADMIN,
        )

        return self.success()

    def cancel(self, parent: 'Model', uuid: str):
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
            raise self.access_denied_response()

        try:
            ds = models.ServicePoolPublication.objects.get(uuid=process_uuid(uuid))
            ds.cancel()
        except Exception as e:
            raise exceptions.rest.ResponseError(str(e)) from e

        log.log(
            parent,
            log.LogLevel.INFO,
            f'Canceled publication v{parent.current_pub_revision} by {self._user.pretty_name}',
            log.LogSource.ADMIN,
        )

        return self.success()

    def get_items(self, parent: 'Model', item: typing.Optional[str]):
        parent = ensure.is_instance(parent, models.ServicePool)
        return [
            {
                'id': i.uuid,
                'revision': i.revision,
                'publish_date': i.publish_date,
                'state': i.state,
                'reason': State.from_str(i.state).is_errored() and i.get_instance().error_reason() or '',
                'state_date': i.state_date,
            }
            for i in parent.publications.all()
        ]

    def get_title(self, parent: 'Model') -> str:
        parent = ensure.is_instance(parent, models.ServicePool)
        return _('Publications')

    def get_fields(self, parent: 'Model') -> list[typing.Any]:
        return [
            {'revision': {'title': _('Revision'), 'type': 'numeric', 'width': '6em'}},
            {'publish_date': {'title': _('Publish date'), 'type': 'datetime'}},
            {
                'state': {
                    'title': _('State'),
                    'type': 'dict',
                    'dict': State.literals_dict(),
                }
            },
            {'reason': {'title': _('Reason')}},
        ]

    def get_row_style(self, parent: 'Model') -> types.ui.RowStyleInfo:
        return types.ui.RowStyleInfo(prefix='row-state-', field='state')


class Changelog(DetailHandler):
    """
    Processes the transports detail requests of a Service Pool
    """

    def get_items(self, parent: 'Model', item: typing.Optional[str]):
        parent = ensure.is_instance(parent, models.ServicePool)
        return [
            {
                'revision': i.revision,
                'stamp': i.stamp,
                'log': i.log,
            }
            for i in parent.changelog.all()
        ]

    def get_title(self, parent: 'Model') -> str:
        parent = ensure.is_instance(parent, models.ServicePool)
        return _(f'Changelog')

    def get_fields(self, parent: 'Model') -> list[typing.Any]:
        return [
            {'revision': {'title': _('Revision'), 'type': 'numeric', 'width': '6em'}},
            {'stamp': {'title': _('Publish date'), 'type': 'datetime'}},
            {'log': {'title': _('Comment')}},
        ]
