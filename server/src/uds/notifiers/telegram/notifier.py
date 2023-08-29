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

from uds.core import messaging, exceptions
from uds.core.ui import gui
from uds.core.util.model import getSqlDatetime
from uds.core.util.tools import ignoreExceptions

from . import telegram

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.module import Module

logger = logging.getLogger(__name__)

TELEGRAM_TYPE = 'telegramNotifications'


class TelegramNotifier(messaging.Notifier):
    """
    Email notifier
    """

    typeName = _('Telegram notifications')
    # : Type used internally to identify this provider
    typeType = TELEGRAM_TYPE
    # : Description shown at administration interface for this provider
    typeDescription = _('Telegram notifications')
    # : Icon file used as icon for this provider. This string will be translated
    # : BEFORE sending it to administration interface, so don't forget to
    # : mark it as _ (using gettext_noop)
    iconFile = 'telegram.png'

    botname = gui.TextField(
        length=64,
        label=_('Bot Name'),
        order=1,
        tooltip=_('Bot name'),
        required=True,
        default='',
        tab=_('Telegram'),
    )

    accessToken = gui.TextField(
        length=64,
        label=_('Access Token'),
        order=2,
        tooltip=_('Access Token'),
        required=True,
        default='',
        tab=_('Telegram'),
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
    checkDelay = gui.NumericField(
        length=3,
        label=_('Check delay'),
        order=3,
        tooltip=_('Delay in seconds between checks for commands'),
        required=True,
        default=3600,
        minValue=60,
        maxValue=86400,
        tab=_('Telegram'),
    )

    def initialize(self, values: 'Module.ValuesType' = None):
        """
        We will use the "autosave" feature for form fields
        """
        if not values:
            return

        # check hostname for stmp server si valid and is in the right format
        # that is a hostname or ip address with optional port
        # if hostname is not valid, we will raise an exception
        for i in (self.botname, self.accessToken, self.secret):
            s = i.cleanStr()
            if not s:
                raise exceptions.ValidationError(_('Invalid value for {}').format(i.label))
            i.value = s

    def initGui(self) -> None:
        self.secret.default = self.secret.default or secrets.token_urlsafe(8)
        return super().initGui()

    def notify(self, group: str, identificator: str, level: messaging.LogLevel, message: str) -> None:
        telegramMsg = f'{group} - {identificator} - {str(level)}: {message}'
        logger.debug('Sending telegram message: %s', telegramMsg)
        # load chatIds
        chatIds = self.storage.getPickle('chatIds') or []
        t = telegram.Telegram(self.accessToken.value, self.botname.value)
        for chatId in chatIds:
            with ignoreExceptions():
                t.sendMessage(chatId, telegramMsg)
                # Wait a bit, so we don't send more than 10 messages per second
                time.sleep(0.1)

    def subscribeUser(self, chatId: int) -> None:
        # we do not expect to have a lot of users, so we will use a simple storage
        # that holds a list of chatIds
        chatIds = self.storage.getPickle('chatIds') or []
        if chatId not in chatIds:
            chatIds.append(chatId)
            self.storage.putPickle('chatIds', chatIds)
            logger.info('User %s subscribed to notifications', chatId)

    def unsubscriteUser(self, chatId: int) -> None:
        # we do not expect to have a lot of users, so we will use a simple storage
        # that holds a list of chatIds
        chatIds = self.storage.getPickle('chatIds') or []
        if chatId in chatIds:
            chatIds.remove(chatId)
            self.storage.putPickle('chatIds', chatIds)
            logger.info('User %s unsubscribed from notifications', chatId)

    def retrieveMessages(self) -> None:
        if not self.accessToken.value.strip():
            return  # no access token, no messages
        # Time of last retrieve
        lastCheck: typing.Optional[datetime.datetime] = self.storage.getPickle('lastCheck')
        now = getSqlDatetime()

        # If last check is not set, we will set it to now
        if lastCheck is None:
            lastCheck = now - datetime.timedelta(seconds=self.checkDelay.num() + 1)
            self.storage.putPickle('lastCheck', lastCheck)

        # If not enough time has passed, we will not check
        if lastCheck + datetime.timedelta(seconds=self.checkDelay.num()) > now:
            return

        # Update last check
        self.storage.putPickle('lastCheck', now)

        lastOffset = self.storage.getPickle('lastOffset') or 0
        t = telegram.Telegram(self.accessToken.value, last_offset=lastOffset)
        with ignoreExceptions():  # In case getUpdates fails, ignore it
            for update in t.getUpdates():
                # Process update
                with ignoreExceptions():  # Any failure will be ignored and next update will be processed
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
                        self.subscribeUser(update.chat.id)
                        t.sendMessage(update.chat.id, _('You have been subscribed to notifications'))
                    elif message in ('/leave', '/unsubscribe'):
                        self.unsubscriteUser(update.chat.id)
                        t.sendMessage(update.chat.id, _('You have been unsubscribed from notifications'))
            self.storage.putPickle('lastOffset', t.lastOffset)
