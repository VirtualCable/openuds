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
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
'''

from __future__ import unicode_literals

from datetime import datetime
from django.db import models
from django.db import connection
from time import mktime

import logging

__updated__ = '2015-04-27'


logger = logging.getLogger(__name__)

NEVER = datetime(1972, 7, 1)
NEVER_UNIX = int(mktime(NEVER.timetuple()))


class UnsavedForeignKey(models.ForeignKey):
    '''
    From 1.8 of django, we need to point to "saved" objects.
    If dont, will raise an InvalidValue exception.

    We need to trick in some cases, because for example, root user is not in DB
    '''
    # Allows pointing to an unsaved object
    allow_unsaved_instance_assignment = True


def getSqlDatetime(unix=False):
    '''
    Returns the current date/time of the database server.

    We use this time as method of keeping all operations betwen different servers in sync.

    We support get database datetime for:
      * mysql
      * sqlite
    '''

    if connection.vendor == 'mysql':
        cursor = connection.cursor()
        cursor.execute('SELECT NOW()')
        date = cursor.fetchone()[0]
    else:
        date = datetime.now()  # If not know how to get database datetime, returns local datetime (this is fine for sqlite, which is local)

    if unix:
        return int(mktime(date.timetuple()))
    else:
        return date


def optimizeTable(dbTable):
    '''
    Executes table optimization
    Supported only on mysql right now
    '''
    cursor = connection.cursor()

    if connection.vendor == 'mysql':
        cursor.execute('OPTIMIZE TABLE {0}'.format(dbTable))
