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
import typing

from uds import models
from uds.core.auths.user import User as aUser
from uds.core.managers import cryptoManager

from ..utils import rest, ensure_data

# User REST structure
class UserRestStruct(rest.RestStruct):
    id: rest.uuid_type
    name: str
    real_name: str
    comments: str
    state: str
    is_admin: bool
    staff_member: bool
    groups: typing.List[rest.uuid_type]
    mfa_data: typing.Optional[str]
    password: typing.Optional[str]


# Provide a "random" dictionary based on a
def createUser(**kwargs) -> typing.Dict[str, typing.Any]:
    return UserRestStruct.random_create(**kwargs).as_dict()


def assertUserIs(
    user: models.User, compare_to: typing.Mapping[str, typing.Any], compare_uuid=False, compare_password=False
) -> bool:
    ignore_fields = ['password', 'groups', 'mfa_data', 'last_access', 'role']

    if not compare_uuid:
        ignore_fields.append('id')

    # If last_access is present, compare it here, because it's a datetime object
    if 'last_access' in compare_to:
        if int(user.last_access.timestamp()) != compare_to['last_access']:
            return False

    if ensure_data(user, compare_to, ignore_keys=ignore_fields):
        # Compare groups
        if 'groups' in compare_to:
            if set(g.dbGroup().uuid for g in aUser(user).groups()) != set(
                compare_to['groups']
            ):
                return False

        # Compare mfa_data
        if 'mfa_data' in compare_to:
            if user.mfa_data != compare_to['mfa_data']:
                return False
            
        # Compare password
        if compare_password:
            return cryptoManager().checkHash(compare_to['password'], user.password)

        return True

    return False
