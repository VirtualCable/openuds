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
@Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import datetime
import logging
import typing

from django.utils.translation import gettext_lazy as _

from uds.REST.model import ModelHandler
from uds.core import types
import uds.core.types.permissions
from uds.core.util import permissions, ensure, ui as ui_utils
from uds.models import Account
from .accountsusage import AccountsUsage

if typing.TYPE_CHECKING:
    from django.db.models import Model

logger = logging.getLogger(__name__)

# Enclosed methods under /item path


class AccountItem(types.rest.BaseRestItem):
    id: str
    name: str
    tags: typing.List[str]
    comments: str
    time_mark: typing.Optional[datetime.datetime]
    permission: int


class Accounts(ModelHandler[AccountItem]):
    """
    Processes REST requests about accounts
    """

    MODEL = Account
    DETAIL = {'usage': AccountsUsage}

    CUSTOM_METHODS = [
        types.rest.ModelCustomMethod('clear', True),
        types.rest.ModelCustomMethod('timemark', True),
    ]

    FIELDS_TO_SAVE = ['name', 'comments', 'tags']

    TABLE = (
        ui_utils.TableBuilder(_('Accounts'))
        .text_column(name='name', title=_('Name'))
        .text_column(name='comments', title=_('Comments'))
        .datetime_column(name='time_mark', title=_('Time mark'))
        .text_column(name='tags', title=_('tags'), visible=False)
        .build()
    )

    def item_as_dict(self, item: 'Model') -> AccountItem:
        item = ensure.is_instance(item, Account)
        return {
            'id': item.uuid,
            'name': item.name,
            'tags': [tag.tag for tag in item.tags.all()],
            'comments': item.comments,
            'time_mark': item.time_mark,
            'permission': permissions.effective_permissions(self._user, item),
        }

    def get_gui(self, for_type: str) -> list[types.ui.GuiElement]:
        return (
            ui_utils.GuiBuilder()
            .add_stock_field(types.rest.stock.StockField.NAME)
            .add_stock_field(types.rest.stock.StockField.COMMENTS)
            .add_stock_field(types.rest.stock.StockField.TAGS)
        ).build()

    def timemark(self, item: 'Model') -> typing.Any:
        """
        API:
            Generates a time mark associated with the account.
            This is useful to easily identify when the account data was last updated.
            (For example, one user enters an service, we get the usage data and "timemark" it, later read again
            and we can identify that all data before this timemark has already been processed)

            Arguments:
                item: Account to timemark

        """
        item = ensure.is_instance(item, Account)
        item.time_mark = datetime.datetime.now()
        item.save()
        return ''

    def clear(self, item: 'Model') -> typing.Any:
        """
        Api documentation for the method. From here, will be used by the documentation generator
        Always starts with API:
        API:
            Clears all usage associated with the account
        """
        item = ensure.is_instance(item, Account)
        self.check_access(item, uds.core.types.permissions.PermissionType.MANAGEMENT)
        return item.usages.filter(user_service=None).delete()
