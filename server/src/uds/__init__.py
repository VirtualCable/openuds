# -*- coding: utf-8 -*-

#
# Copyright (c) 2012 Virtual Cable S.L.
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

'''
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''

# Make sure that all services are "available" at service startup

from django.db.backends.signals import connection_created
from django.dispatch import receiver
import math
import ssl


from django.apps import AppConfig

import logging

logger = logging.getLogger(__name__)


__updated__ = '2017-01-30'


# Default ssl context is unverified, as MOST servers that we will connect will be with self signed certificates...
try:
    # noinspection PyProtectedMember
    _create_unverified_https_context = ssl._create_unverified_context
    ssl._create_default_https_context = _create_unverified_https_context
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
        from . import services  # to make sure that the packages are initialized at this point
        from . import auths  # To make sure that the packages are initialized at this point
        from . import osmanagers  # To make sure that packages are initialized at this point
        from . import transports  # To make sure that packages are initialized at this point
        from . import dispatchers  # Ensure all dischatchers all also available
        from . import plugins  # To make sure plugins are loaded on memory
        from . import REST  # To make sure REST initializes all what it needs


default_app_config = 'uds.UDSAppConfig'


# Sets up several sqlite non existing methods

@receiver(connection_created)
def extend_sqlite(connection=None, **kwargs):
    if connection.vendor == "sqlite":
        logger.debug('Connection vendor is sqlite, extending methods')
        cursor = connection.cursor()
        cursor.execute('PRAGMA synchronous=OFF')
        cursor.execute('PRAGMA cache_size=8000')
        cursor.execute('PRAGMA temp_store=MEMORY')
        connection.connection.create_function("MIN", 2, min)
        connection.connection.create_function("MAX", 2, max)
        connection.connection.create_function("CEIL", 1, math.ceil)
