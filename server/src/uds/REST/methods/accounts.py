# -*- coding: utf-8 -*-

#
# Copyright (c) 2017 Virtual Cable S.L.
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
#    * Neither the name of Virtual Cable S.L. nor the names of its contributors
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

'''
@itemor: Adolfo Gómez, dkmaster at dkmon dot com
'''
from __future__ import unicode_literals

from django.utils.translation import ugettext_lazy as _, ugettext
from uds.models import Account
from uds.core.util import permissions

from uds.REST.model import ModelHandler

from .accountsusage import AccountsUsage

import logging

logger = logging.getLogger(__name__)

# Enclosed methods under /item path


class Accounts(ModelHandler):
    '''
    Processes REST requests about accounts
    '''
    model = Account
    detail = {'usage': AccountsUsage }

    custom_methods = [('clear', True)]

    save_fields = ['name', 'comments', 'tags']

    table_title = _('Accounts')
    table_fields = [
        {'name': {'title': _('Name'), 'visible': True}},
        {'comments': {'title': _('Comments')}},
        {'time_mark': {'title': _('Time mark')}},
        {'tags': {'title': _('tags'), 'visible': False}},
    ]

    def item_as_dict(self, account):
        return {
            'id': account.uuid,
            'name': account.name,
            'tags': [tag.tag for tag in account.tags.all()],
            'comments': account.comments,
            'time_mark': account.time_mark,
            'permission': permissions.getEffectivePermission(self._user, account)
        }

    def getGui(self, type_):
        return self.addDefaultFields([], ['name', 'comments', 'tags'])

    def clear(self, item):
        self.ensureAccess(item, permissions.PERMISSION_MANAGEMENT)
        return item.usages.filter(user_service=None).delete()

