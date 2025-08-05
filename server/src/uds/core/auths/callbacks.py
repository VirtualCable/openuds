#
# Copyright (c) 2012-2023 Virtual Cable S.L.U.
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
Base module for all authenticators

Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import re
import typing
import collections.abc


from uds import models
from uds.core import types, consts
from uds.core.util import config, cache, log, security

logger = logging.getLogger(__name__)

FAILURE_CACHE: typing.Final[cache.Cache] = cache.Cache('callback_auth_failure', 5 * 60)  # 5 minutes
# Groups only A-Z, a-z, 0-9 and _ or - are allowed
RE_GROUPS: typing.Final[typing.Pattern[str]] = re.compile(r'^[A-Za-z0-9_-]+$')


def weblogin(user: models.User) -> None:
    """
    This method is called when a user logs in. It can be used to perform any action needed when a user logs in.
    """
    notify_url = config.GlobalConfig.NOTIFY_CALLBACK_URL.as_str()
    if not notify_url.startswith('https') or (fail_count := FAILURE_CACHE.get('notify_failure', 0)) >= 3:
        return

    # We are going to notify the login to the callback URL
    # This is a POST with a JSON payload
    try:
        response = security.secure_requests_session().post(
            notify_url,
            json={
                'type': 'weblogin',
                'info': {
                    'authenticator_uuid': user.manager.uuid,
                    'user_uuid': user.uuid,
                    'username': user.name,
                    'groups': [group.name for group in user.groups.all()],
                },
            },
            timeout=consts.net.SHORT_REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        FAILURE_CACHE.delete('notify_failure')

        # Get response json, and check if there is any "new" information
        # new information can be:
        # - Groups added  (new_groups)
        # - Groups removed (removed_groups)
        data = response.json()

        def _clean_list_groups(groups: collections.abc.Iterable[str]) -> collections.abc.Iterable[str]:
            for grp_name in groups:
                if not RE_GROUPS.match(grp_name):
                    logger.error('Invalid group name received from callback URL: %s', group_name)
                    continue
                yield grp_name

        # Add groups to user if they are in the list
        changed_grps: list[str] = []
        for group_name in _clean_list_groups(data.get('new_groups', [])):
            group, _ = models.Group.objects.get_or_create(name=group_name)
            changed_grps += [f'+{group_name}']
            user.groups.add(group)
        # Remove groups from user if they are in the list
        for group_name in _clean_list_groups(data.get('removed_groups', [])):
            try:
                group = models.Group.objects.get(name=group_name)
            except models.Group.DoesNotExist:
                continue
            changed_grps += [f'-{group_name}']
            user.groups.remove(group)

        # Log if groups were changed to keep track of changes
        if changed_grps:
            log.log(
                user,
                types.log.LogLevel.INFO,
                f'Groups changed by callback URL: {",".join(changed_grps)}',
                types.log.LogSource.INTERNAL,
            )

    except Exception as e:
        logger.error('Error notifying login to callback URL: %s', e)
        FAILURE_CACHE.set('notify_failure', fail_count + 1)
