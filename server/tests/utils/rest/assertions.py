# -*- coding: utf-8 -*-
#
# Copyright (c) 2022 Virtual Cable S.L.U.
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
import logging
import typing
import collections.abc

from uds import models
from uds.core.managers.crypto import CryptoManager

from .. import ensure_data


logger = logging.getLogger(__name__)


def assert_user_is(
    user: models.User,
    compare_to: collections.abc.Mapping[str, typing.Any],
    compare_uuid: bool=False,
    compare_password: bool=False,
) -> bool:
    ignore_fields = ['password', 'groups', 'mfa_data', 'last_access', 'role']

    if not compare_uuid:
        ignore_fields.append('id')

    # If last_access is present, compare it here, because it's a datetime object
    if 'last_access' in compare_to:
        if int(user.last_access.timestamp()) != compare_to['last_access']:
            logger.info(
                'User last_access do not match: %s != %s',
                user.last_access.timestamp(),
                compare_to['last_access'],
            )
            return False

    if ensure_data(user, compare_to, ignore_keys=ignore_fields):
        # Compare groups
        if 'groups' in compare_to:
            groups = set(i.uuid for i in user.groups.all() if i.is_meta is False)
            compare_to_groups = set(compare_to['groups'])
            # Ensure groups are PART compare_to_groups
            if groups - compare_to_groups != set():
                logger.info(
                    'User groups do not match: %s != %s', groups, compare_to_groups
                )
                return False

        # Compare mfa_data
        if 'mfa_data' in compare_to:
            if user.mfa_data != compare_to['mfa_data']:
                logger.info(
                    'User mfa_data do not match: %s != %s',
                    user.mfa_data,
                    compare_to['mfa_data'],
                )
                return False

        # Compare password
        if compare_password:
            if not CryptoManager().check_hash(compare_to['password'], user.password):
                logger.info(
                    'User password do not match: %s != %s',
                    user.password,
                    compare_to['password'],
                )
                return False

        return True

    return False


def assert_group_is(
    group: models.Group, compare_to: collections.abc.Mapping[str, typing.Any], compare_uuid: bool=False
) -> bool:
    ignore_fields = ['groups', 'users', 'is_meta', 'type', 'pools']

    if not compare_uuid:
        ignore_fields.append('id')

    if ensure_data(group, compare_to, ignore_keys=ignore_fields):
        if group.is_meta:
            grps = set(i.uuid for i in group.groups.all())
            compare_to_groups = set(compare_to['groups'])
            if grps != compare_to_groups:
                logger.info(
                    'Group groups do not match: %s != %s', grps, compare_to_groups
                )
                return False

        if 'type' in compare_to:
            if group.is_meta != (compare_to['type'] == 'meta'):
                logger.info(
                    'Group type do not match: %s != %s',
                    group.is_meta,
                    compare_to['type'],
                )
                return False

        if 'pools' in compare_to:
            pools = set(i.uuid for i in group.deployedServices.all())
            compare_to_pools = set(compare_to['pools'])
            if pools != compare_to_pools:
                logger.info(
                    'Group pools do not match: %s != %s', pools, compare_to_pools
                )
                return False

        return True

    return False


def assert_servicepool_is(
    pool: models.ServicePool,
    compare_to: collections.abc.Mapping[str, typing.Any],
    compare_uuid: bool=False,
) -> bool:
    ignore_fields = [
        'tags',
        'parent',
        'parent_type',
        'thumb',
        'account',
        'service_id',
        'provider_id',
        'meta_member',
        'user_services_count',
        'user_services_in_preparation',
        'restrained',
        'permission',
        'info',
        'pool_group_id',
        'pool_group_name',
        'pool_group_thumb',
        'usage',
        'osmanager_id',
    ]

    if not compare_uuid:
        ignore_fields.append('id')

    if ensure_data(pool, compare_to, ignore_keys=ignore_fields):
        return True

    return False
