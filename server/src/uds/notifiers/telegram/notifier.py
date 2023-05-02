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
#    * Neither the name of Virtual Cable S.L. nor the names of its contributors
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
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import typing

from django.utils.translation import gettext_noop as _

from uds.core import messaging, exceptions
from uds.core.ui import gui
from uds.core.util import validators


# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.module import Module

logger = logging.getLogger(__name__)


class EmailNotifier(messaging.Notifier):
    """
    Email notifier
    """

    typeName = _('Telegram notifications')
    # : Type used internally to identify this provider
    typeType = 'telegramNotifications'
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
        defvalue='',
        tab=_('Telegram'),
    )

    accessToken = gui.TextField(
        length=64,
        label=_('Access Token'),
        order=2,
        tooltip=_('Access Token'),
        required=True,
        defvalue='',
        tab=_('Telegram'),
    )

    # The bot will allow commmand (/join or /subscribe and /leave or /unsubscribe) to subscribe and unsubscribe
    # For this to work, we will process the message and check if it is a command from time to time
    # This var defines the delay in secods between checks (1 hour by default, we do not need to check this every second)
    checkDelay = gui.NumericField(
        length=3,
        label=_('Check delay'),
        order=3,
        tooltip=_('Delay in seconds between checks for commands'),
        required=True,
        defvalue=3600,
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
        hostname = self.botname.cleanStr()
        if not hostname:
            raise exceptions.ValidationError(_('Invalid bot name'))

        # Done

    def notify(self, group: str, identificator: str, level: messaging.LogLevel, message: str) -> None:
        pass
