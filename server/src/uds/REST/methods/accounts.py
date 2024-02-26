# -*- coding: utf-8 -*-

#
# Copyright (c) 2017-2023 Virtual Cable S.L.U.
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
@itemor: Adolfo Gómez, dkmaster at dkmon dot com
"""
import datetime
import logging
import typing
import collections.abc

from django.utils.translation import gettext_lazy as _

from uds.REST.model import ModelHandler
from uds.core import types
import uds.core.types.permissions
from uds.core.util import permissions, ensure
from uds.models import Account
from .accountsusage import AccountsUsage

if typing.TYPE_CHECKING:
    from django.db.models import Model

logger = logging.getLogger(__name__)

# Enclosed methods under /item path


class Accounts(ModelHandler):
    """
    Processes REST requests about accounts
    """

    model = Account
    detail = {'usage': AccountsUsage}

    custom_methods = [('clear', True), ('timemark', True)]

    save_fields = ['name', 'comments', 'tags']

    table_title = _('Accounts')
    table_fields = [
        {'name': {'title': _('Name'), 'visible': True}},
        {'comments': {'title': _('Comments')}},
        {'time_mark': {'title': _('Time mark'), 'type': 'callback'}},
        {'tags': {'title': _('tags'), 'visible': False}},
    ]

    def item_as_dict(self, item: 'Model') -> types.rest.ItemDictType:
        item = ensure.is_instance(item, Account)
        return {
            'id': item.uuid,
            'name': item.name,
            'tags': [tag.tag for tag in item.tags.all()],
            'comments': item.comments,
            'time_mark': item.time_mark,
            'permission': permissions.effective_permissions(self._user, item),
        }

    def get_gui(self, type_: str) -> list[typing.Any]:
        return self.add_default_fields([], ['name', 'comments', 'tags'])

    def timemark(self, item: 'Model') -> typing.Any:
        item = ensure.is_instance(item, Account)
        item.time_mark = datetime.datetime.now()
        item.save()
        return ''

    def clear(self, item: 'Model') -> typing.Any:
        item = ensure.is_instance(item, Account)
        self.ensure_has_access(item, uds.core.types.permissions.PermissionType.MANAGEMENT)
        return item.usages.filter(user_service=None).delete()
