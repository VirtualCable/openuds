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
#      and/or other materials provided with the distributiopenStack.
#    * Neither the name of Virtual Cable S.L.U. nor the names of its contributors
#      may be used to endorse or promote products derived from this software
#      without specific prior written permissiopenStack.
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
import datetime
import secrets
import typing
import time

from django.utils.translation import gettext_noop as _

from uds.core import messaging, exceptions, types
from uds.core.ui import gui
from uds.core.util.model import sql_now
from uds.core.util.utils import ignore_exceptions

from . import telegram

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

TELEGRAM_TYPE = 'telegramNotifications'


class TelegramNotifier(messaging.Notifier):
    """
    Email notifier
    """

    type_name = _('Telegram notifications')
    # : Type used internally to identify this provider
    type_type = TELEGRAM_TYPE
    # : Description shown at administration interface for this provider
    type_description = _('Telegram notifications')
    # : Icon file used as icon for this provider. This string will be translated
    # : BEFORE sending it to administration interface, so don't forget to
    # : mark it as _ (using gettext_noop)
    icon_file = 'telegram.png'

    access_token = gui.TextField(
        length=64,
        label=_('Access Token'),
        order=2,
        tooltip=_('Access Token'),
        required=True,
        default='',
        tab=_('Telegram'),
        old_field_name='accessToken',
    )

    # Secret key used to validate join and subscribe requests
    secret = gui.TextField(
        length=64,
        label=_('Secret'),
        order=3,
        tooltip=_('Secret key used to validate subscribtion requests (using /join or /subscribe commands)'),
        required=True,
        default='',
        tab=_('Telegram'),
    )

    # The bot will allow commmand (/join {secret} or /subscribe {secret} and /leave or /unsubscribe) to subscribe and unsubscribe
    # For this to work, we will process the message and check if it is a command from time to time
    # This var defines the delay in secods between checks (1 hour by default, we do not need to check this every second)
    check_delay = gui.NumericField(
        length=3,
        label=_('Check delay'),
        order=4,
        tooltip=_('Delay in seconds between checks for commands'),
        required=True,
        default=3600,
        min_value=60,
        max_value=86400,
        tab=_('Telegram'),
        old_field_name='checkDelay',
    )

    def initialize(self, values: 'types.core.ValuesType' = None) -> None:
        """
        We will use the "autosave" feature for form fields
        """
        if not values:
            return

        # check hostname for stmp server si valid and is in the right format
        # that is a hostname or ip address with optional port
        # if hostname is not valid, we will raise an exception
        for i in (self.access_token, self.secret):
            s = i.value.strip()
            if not s:
                raise exceptions.ui.ValidationError(_('Invalid value for {}').format(i.label))
            i.value = s

    def init_gui(self) -> None:
        self.secret.default = self.secret.default or secrets.token_urlsafe(8)
        return super().init_gui()

    def notify(self, group: str, identificator: str, level: messaging.LogLevel, message: str) -> None:
        telegram_msg = f'{group} - {identificator} - {str(level)}: {message}'
        logger.debug('Sending telegram message: %s', telegram_msg)
        # load chat_ids
        with self.storage.as_dict() as storage:
            chat_ids: list[int] = storage.get('chat_ids', [])
        t = telegram.Telegram(self.access_token.value)  # Only writing, can ingnore last_offset
        for chad_id in chat_ids:
            with ignore_exceptions():
                t.send_message(chad_id, telegram_msg)
                # Wait a bit, so we don't send more than 10 messages per second
                time.sleep(0.1)

    def subscribe_user(self, chat_id: int) -> None:
        # we do not expect to have a lot of users, so we will use a simple storage
        # that holds a list of chat_ids
        with self.storage.as_dict() as storage:
            chat_ids: list[int] = storage.get('chat_ids', [])
            if chat_id not in chat_ids:
                chat_ids.append(chat_id)
                storage['chat_ids'] = chat_ids
                logger.info('User %s subscribed to notifications', chat_id)

    def unsubscrite_user(self, chat_id: int) -> None:
        # we do not expect to have a lot of users, so we will use a simple storage
        # that holds a list of chat_ids
        with self.storage.as_dict() as storage:
            chat_ids: list[int] = storage.get('chat_ids', [])
            if chat_id in chat_ids:
                chat_ids.remove(chat_id)
                storage['chat_ids'] = chat_ids
                logger.info('User %s unsubscribed from notifications', chat_id)

    def retrieve_messages(self) -> None:
        if not self.access_token.value.strip():
            return  # no access token, no messages
        # Time of last retrieve
        with self.storage.as_dict() as storage:
            last_check: typing.Optional[datetime.datetime] = storage.get('last_check')
            now = sql_now()

            # If last check is not set, we will set it to now
            if last_check is None:
                last_check = now - datetime.timedelta(seconds=self.check_delay.as_int() + 1)
                storage['last_check'] = last_check

            # If not enough time has passed, we will not check
            if last_check + datetime.timedelta(seconds=self.check_delay.as_int()) > now:
                return

            # Update last check
            storage['last_check'] = now
            last_offset = storage.get('last_offset', 0)

            t = telegram.Telegram(self.access_token.value, last_offset=last_offset)
            with ignore_exceptions():  # In case getUpdates fails, ignore it
                for update in t.get_updates():
                    # Process update
                    with ignore_exceptions():  # Any failure will be ignored and next update will be processed
                        message = update.text.strip()
                        if message.split(' ')[0] in ('/join', '/subscribe'):
                            try:
                                secret = message.split(' ')[1]
                                if secret != self.secret.value:
                                    raise Exception()
                            except Exception:
                                logger.warning(
                                    'Invalid subscribe command received from telegram bot (invalid secret: %s)',
                                    message,
                                )
                            self.subscribe_user(update.chat.id)
                            t.send_message(update.chat.id, _('You have been subscribed to notifications'))
                        elif message in ('/leave', '/unsubscribe'):
                            self.unsubscrite_user(update.chat.id)
                            t.send_message(update.chat.id, _('You have been unsubscribed from notifications'))
                storage['last_offset'] = t.last_offset
