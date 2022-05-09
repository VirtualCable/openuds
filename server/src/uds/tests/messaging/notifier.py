import random
import typing


from django.test import TestCase
from django.test.client import Client
from django.conf import settings

from uds.tests import fixtures, tools
from uds.core import messaging

class TestEmailNotifier(TestCase):
    """
    Test Email Notifier
    """

    def setUp(self):
        # Setup smtp server
        from aiosmtpd.controller import Controller
        from aiosmtpd.handlers import Debugging

        self.smtp_server = Controller(
            handler=Debugging(),
            hostname='localhost',
            port=1025,
        )
        self.smtp_server.start()
        
    def tearDown(self):
        # Stop smtp debug server
        self.smtp_server.stop()

    def test_email_notifier(self):
        """
        Test email notifier
        """
        notifier = fixtures.notifiers.createEmailNotifier(
            host='localhost',
            port=self.smtp_server.port,
            enableHtml=False
        )

        notifier.getInstance().notify(
            'Group',
            'Identificator',
            messaging.NotificationLevel.CRITICAL,
            'Test message cañón',
        )

