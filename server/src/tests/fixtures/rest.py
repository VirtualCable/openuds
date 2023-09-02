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

from ..utils import rest


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


# Group REST structure
class GroupRestStruct(rest.RestStruct):
    id: rest.uuid_type
    name: str
    comments: str
    state: str
    type: str
    is_meta: bool
    meta_if_any: bool


# ServicePool REST structure
class ServicePoolRestStruct(rest.RestStruct):
    id: rest.uuid_type
    name: str
    short_name: str
    tags: typing.List[str]
    parent: str
    parent_type: str
    comments: str
    state: str
    thumb: str
    account: str
    account_id: rest.uuid_type
    service_id: rest.uuid_type
    provider_id: rest.uuid_type
    image_id: rest.uuid_type
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
    meta_member: typing.List[typing.Dict[str, rest.uuid_type]]
    calendar_message: str


# Provide a "random" dictionary based on a
def createUser(**kwargs) -> typing.Dict[str, typing.Any]:
    data = UserRestStruct.random_create(**kwargs).as_dict()
    data['state'] = 'A'  # Fix state to 1 char
    return data


def createGroup(**kwargs) -> typing.Dict[str, typing.Any]:
    data = GroupRestStruct.random_create(**kwargs).as_dict()
    data['state'] = 'A'  # Fix state to 1 char
    return data


def createServicePool(**kwargs) -> typing.Dict[str, typing.Any]:
    return ServicePoolRestStruct.random_create(**kwargs).as_dict()
