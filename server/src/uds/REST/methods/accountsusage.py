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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing

from django.utils.translation import gettext as _

from uds.core import exceptions, types
from uds.core.util import ensure, permissions
from uds.core.util.model import process_uuid
from uds.models import Account, AccountUsage
from uds.REST.model import DetailHandler

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from django.db.models import Model

logger = logging.getLogger(__name__)


class AccountsUsage(DetailHandler):  # pylint: disable=too-many-public-methods
    """
    Detail handler for Services, whose parent is a Provider
    """

    @staticmethod
    def usageToDict(item: 'AccountUsage', perm: int) -> dict[str, typing.Any]:
        """
        Convert an account usage to a dictionary
        :param item: Account usage item (db)
        :param perm: permission
        """
        retVal = {
            'uuid': item.uuid,
            'pool_uuid': item.pool_uuid,
            'pool_name': item.pool_name,
            'user_uuid': item.user_uuid,
            'user_name': item.user_name,
            'start': item.start,
            'end': item.end,
            'running': item.user_service is not None,
            'elapsed': item.elapsed,
            'elapsed_timemark': item.elapsed_timemark,
            'permission': perm,
        }

        return retVal

    def get_items(self, parent: 'Model', item: typing.Optional[str]) -> types.rest.ManyItemsDictType:
        parent = ensure.is_instance(parent, Account)
        # Check what kind of access do we have to parent provider
        perm = permissions.effective_permissions(self._user, parent)
        try:
            if not item:
                return [AccountsUsage.usageToDict(k, perm) for k in parent.usages.all()]
            k = parent.usages.get(uuid=process_uuid(item))
            return AccountsUsage.usageToDict(k, perm)
        except Exception:
            logger.exception('itemId %s', item)
            raise self.invalid_item_response()

    def get_fields(self, parent: 'Model') -> list[typing.Any]:
        return [
            {'pool_name': {'title': _('Pool name')}},
            {'user_name': {'title': _('User name')}},
            {'running': {'title': _('Running')}},
            {'start': {'title': _('Starts'), 'type': 'datetime'}},
            {'end': {'title': _('Ends'), 'type': 'datetime'}},
            {'elapsed': {'title': _('Elapsed')}},
            {'elapsed_timemark': {'title': _('Elapsed timemark')}},
        ]

    def get_row_style(self, parent: 'Model') -> types.ui.RowStyleInfo:
        return types.ui.RowStyleInfo(prefix='row-running-', field='running')

    def save_item(self, parent: 'Model', item: typing.Optional[str]) -> None:
        raise exceptions.rest.RequestError('Accounts usage cannot be edited')

    def delete_item(self, parent: 'Model', item: str) -> None:
        parent = ensure.is_instance(parent, Account)
        logger.debug('Deleting account usage %s from %s', item, parent)
        try:
            usage = parent.usages.get(uuid=process_uuid(item))
            usage.delete()
        except Exception:
            logger.exception('Exception')
            raise self.invalid_item_response()

    def get_title(self, parent: 'Model') -> str:
        parent = ensure.is_instance(parent, Account)
        try:
            return _('Usages of {0}').format(parent.name)
        except Exception:
            return _('Current usages')
