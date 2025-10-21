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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import dataclasses
import datetime
import logging
import typing

from django.utils.translation import gettext as _
from django.db.models import Model

from uds.core import exceptions, types
from uds.core.types.rest import TableInfo
from uds.core.util import ensure, permissions, ui as ui_utils
from uds.core.util.model import process_uuid
from uds.models import Account, AccountUsage
from uds.REST.model import DetailHandler


logger = logging.getLogger(__name__)


@dataclasses.dataclass
class AccountItem(types.rest.BaseRestItem):
    uuid: str
    pool_uuid: str
    pool_name: str
    user_uuid: str
    user_name: str
    start: datetime.datetime
    end: datetime.datetime
    running: bool
    elapsed: str
    elapsed_timemark: str
    permission: int


class AccountsUsage(DetailHandler[AccountItem]):  # pylint: disable=too-many-public-methods
    """
    Detail handler for Services, whose parent is a Provider
    """

    @staticmethod
    def usage_to_dict(item: 'AccountUsage', perm: int) -> AccountItem:
        """
        Convert an account usage to a dictionary
        :param item: Account usage item (db)
        :param perm: permission
        """
        return AccountItem(
            uuid=item.uuid,
            pool_uuid=item.pool_uuid,
            pool_name=item.pool_name,
            user_uuid=item.user_uuid,
            user_name=item.user_name,
            start=item.start,
            end=item.end,
            running=item.user_service is not None,
            elapsed=item.elapsed,
            elapsed_timemark=item.elapsed_timemark,
            permission=perm,
        )

    def get_items(self, parent: 'Model', item: typing.Optional[str]) -> types.rest.ItemsResult[AccountItem]:
        parent = ensure.is_instance(parent, Account)
        # Check what kind of access do we have to parent provider
        perm = permissions.effective_permissions(self._user, parent)
        try:
            if not item:
                return [AccountsUsage.usage_to_dict(k, perm) for k in self.filter_queryset(parent.usages.all())]
            k = parent.usages.get(uuid=process_uuid(item))
            return AccountsUsage.usage_to_dict(k, perm)
        except Exception:
            logger.exception('itemId %s', item)
            raise exceptions.rest.NotFound(_('Account usage not found: {}').format(item)) from None

    def get_table(self, parent: 'Model') -> TableInfo:
        parent = ensure.is_instance(parent, Account)
        return (
            ui_utils.TableBuilder(_('Usages of {0}').format(parent.name))
            .text_column(name='pool_name', title=_('Pool name'))
            .text_column(name='user_name', title=_('User name'))
            .text_column(name='running', title=_('Running'))
            .datetime_column(name='start', title=_('Starts'))
            .datetime_column(name='end', title=_('Ends'))
            .text_column(name='elapsed', title=_('Elapsed'))
            .datetime_column(name='elapsed_timemark', title=_('Elapsed timemark'))
            .row_style(prefix='row-running-', field='running')
            .build()
        )

    def save_item(self, parent: 'Model', item: typing.Optional[str]) -> AccountItem:
        raise exceptions.rest.RequestError('Accounts usage cannot be edited')

    def delete_item(self, parent: 'Model', item: str) -> None:
        parent = ensure.is_instance(parent, Account)
        logger.debug('Deleting account usage %s from %s', item, parent)
        try:
            usage = parent.usages.get(uuid=process_uuid(item))
            usage.delete()
        except Exception:
            logger.error('Error deleting account usage %s from %s', item, parent)
            raise exceptions.rest.NotFound(_('Account usage not found: {}').format(item)) from None
