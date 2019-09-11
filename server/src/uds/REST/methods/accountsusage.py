# -*- coding: utf-8 -*-

#
# Copyright (c) 2017-2019 Virtual Cable S.L.
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

"""
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing

from django.utils.translation import ugettext as _

from uds.REST import RequestError
from uds.REST.model import DetailHandler
from uds.core.util import permissions
from uds.core.util.model import processUuid

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.models import AccountUsage, Account

logger = logging.getLogger(__name__)


class AccountsUsage(DetailHandler):  # pylint: disable=too-many-public-methods
    """
    Detail handler for Services, whose parent is a Provider
    """

    @staticmethod
    def usageToDict(item: 'AccountUsage', perm: int) -> typing.Dict[str, typing.Any]:
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
            'permission': perm
        }

        return retVal

    def getItems(self, parent: 'Account', item: typing.Optional[str]):
        # Check what kind of access do we have to parent provider
        perm = permissions.getEffectivePermission(self._user, parent)
        try:
            if not item:
                return [AccountsUsage.usageToDict(k, perm) for k in parent.usages.all()]
            k = parent.usages.get(uuid=processUuid(item))
            return AccountsUsage.usageToDict(k, perm)
        except Exception:
            logger.exception('itemId %s', item)
            self.invalidItemException()

    def getFields(self, parent: 'Account') -> typing.List[typing.Any]:
        return [
            {'pool_name': {'title': _('Pool name')}},
            {'user_name': {'title': _('User name')}},
            {'running': {'title': _('Running')}},
            {'start': {'title': _('Starts'), 'type': 'datetime'}},
            {'end': {'title': _('Ends'), 'type': 'datetime'}},
            {'elapsed': {'title': _('Elapsed')}},
            {'elapsed_timemark': {'title': _('Elapsed timemark')}},
        ]

    def getRowStyle(self, parent: 'Account') -> typing.Dict[str, typing.Any]:
        return {'field': 'running', 'prefix': 'row-running-'}

    def saveItem(self, parent: 'Account', item: typing.Optional[str]) -> None:
        raise RequestError('Accounts usage cannot be edited')

    def deleteItem(self, parent: 'Account', item: str) -> None:
        logger.debug('Deleting account usage %s from %s', item, parent)
        try:
            usage = parent.usages.get(uuid=processUuid(item))
            usage.delete()
        except Exception:
            logger.exception('Exception')
            self.invalidItemException()

    def getTitle(self, parent: 'Account') -> str:
        try:
            return _('Usages of {0}').format(parent.name)
        except Exception:
            return _('Current usages')
