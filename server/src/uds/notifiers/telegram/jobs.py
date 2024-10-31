# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2019 Virtual Cable S.L.
# All rights reserved.
#

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
