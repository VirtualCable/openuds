#
# Copyright (c) 2024-2025 Virtual Cable S.L.U.
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
import typing

from uds.core import jobs, managers


from uds.models import Notifier

from . import notifier

logger = logging.getLogger(__name__)


class TelegramReceiver(jobs.Job):
    frecuency = 60  # Once every 60 seconds
    friendly_name = 'Telegram Receiver'

    def run(self) -> None:
        logger.debug('Retrieving messages from Telegram')

        # Get all Notifiers that are telegram notifiers
        for telegram_db_notifier in Notifier.objects.filter(data_type=notifier.TELEGRAM_TYPE, enabled=True):
            n = typing.cast(notifier.TelegramNotifier, telegram_db_notifier.get_instance())

            if not n:  # even if marked as telegram, it could be not a telegram notifier
                logger.error('Notifier %s is not a Telegram notifier', telegram_db_notifier.name)
                continue

            n.retrieve_messages()

    @staticmethod
    def register() -> None:
        managers.task_manager().register_job(TelegramReceiver)
