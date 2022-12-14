# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2022 Virtual Cable S.L.U.
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

# Make sure that all services are "available" at service startup
import math
import ssl
import logging
from django.db import connections

from django.db.backends.signals import connection_created
# from django.db.models.signals import post_migrate
from django.dispatch import receiver


from django.apps import AppConfig


logger = logging.getLogger(__name__)


# Set default ssl context unverified, as MOST servers that we will connect will be with self signed certificates...
try:
    _create_unverified_https_context = ssl._create_unverified_context
    ssl._create_default_https_context = _create_unverified_https_context

    # Capture warnnins to logg
    logging.captureWarnings(True)
except AttributeError:
    # Legacy Python that doesn't verify HTTPS certificates by default
    pass


class UDSAppConfig(AppConfig):
    name = 'uds'
    verbose_name = 'Universal Desktop Services'

    def ready(self):
        # We have to take care with this, because it's supposed to be executed
        # with ANY command from manage.
        logger.debug('Initializing app (ready) ***************')

        # Now, ensures that all dynamic elements are loadad and present
        # To make sure that the packages are initialized at this point
        from . import services
        from . import auths
        from . import mfas
        from . import osmanagers
        from . import notifiers
        from . import transports
        from . import reports
        from . import dispatchers
        from . import plugins
        from . import REST

        # Ensure notifications table exists on local sqlite db (called "persistent" on settings.py)
        # Note: On Notification model change, we must ensure that the table is removed on the migration itself
        try:
            with connections['persistent'].schema_editor() as schema_editor:
                schema_editor.create_model(self.get_model('Notification'))
        except Exception:  # nosec: intentionally catching all exceptions
            # If it fails, it's ok, it just means that it already exists
            pass


default_app_config = 'uds.UDSAppConfig'


# Sets up several sqlite non existing methods
@receiver(connection_created)
def extend_sqlite(connection=None, **kwargs):
    if connection and connection.vendor == "sqlite":
        logger.debug('Connection vendor is sqlite, extending methods')
        cursor = connection.cursor()
        cursor.execute('PRAGMA synchronous=OFF')
        cursor.execute('PRAGMA cache_size=-16384')
        cursor.execute('PRAGMA temp_store=MEMORY')
        cursor.execute('PRAGMA journal_mode=WAL')
        cursor.execute('PRAGMA mmap_size=67108864')
        connection.connection.create_function("MIN", 2, min)
        connection.connection.create_function("MAX", 2, max)
        connection.connection.create_function("CEIL", 1, math.ceil)
