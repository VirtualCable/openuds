# -*- coding: utf-8 -*-
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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing

from django.db import models

from .uuid_model import UUIDModel
from .tag import TaggingMixin
from ..core.util.model import sql_now
from ..core.consts import NEVER

logger = logging.getLogger(__name__)

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.models import UserService, AccountUsage


class Account(UUIDModel, TaggingMixin):
    """
    Account storing on DB model
    """

    name = models.CharField(max_length=128, unique=False, db_index=True)
    time_mark = models.DateTimeField(default=NEVER)
    comments = models.CharField(max_length=256, default='')

    # "fake" declarations for type checking
    # objects: 'models.manager.Manager["Account"]'
    usages: 'models.manager.RelatedManager[AccountUsage]'

    def start_accounting(self, userservice: 'UserService') -> typing.Optional['AccountUsage']:
        if hasattr(userservice, 'accounting'):  # Already has an account
            return None

        start = sql_now()

        if userservice.user:
            username = userservice.user.pretty_name
            user_uuid = userservice.user.uuid
        else:
            username = '??????'
            user_uuid = '00000000-0000-0000-0000-000000000000'

        return self.usages.create(
            user_service=userservice,
            user_name=username,
            user_uuid=user_uuid,
            pool_name=userservice.deployed_service.name,
            pool_uuid=userservice.deployed_service.uuid,
            start=start,
            end=start,
        )

    def stop_accounting(self, userservice: 'UserService') -> typing.Optional['AccountUsage']:
        # if one to one does not exists, attr is not there
        if not hasattr(userservice, 'accounting'):
            return None

        tmp = userservice.accounting
        tmp.user_service = None 
        tmp.end = sql_now()
        tmp.save()
        return tmp

    class Meta:  # pyright: ignore
        """
        Meta class to declare the name of the table at database
        """

        db_table = 'uds_accounts'
        app_label = 'uds'

    def __str__(self) -> str:
        return f'Account id {self.id}, name {self.name}'
