# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2019 Virtual Cable S.L.
# All rights reserved.
#

"""
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing

from uds.core import jobs

from uds.models import Notifier

from . import notifier

logger = logging.getLogger(__name__)


class TelegramReceiver(jobs.Job):
    frecuency = 60  # Once every 60 seconds
    friendly_name = 'Telegram Receiver'

    def run(self):
        logger.debug('Retrieven messages from Telegram')

        # Get all Notifiers that are telegram notifiers
        for telegramDbNotifier in Notifier.objects.filter(data_Type=notifier.TELEGRAM_TYPE):
            n = typing.cast(notifier.TelegramNotifier, telegramDbNotifier.getInstance())

            if n is None:
                logger.error('Notifier %s is not a Telegram notifier', telegramDbNotifier.name)
                continue

            n.retrieveMessages()
