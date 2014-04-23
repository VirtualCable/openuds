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

from django.db import models

from uds.models.Util import getSqlDatetime

from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

__updated__ = '2014-04-23'

class Cache(models.Model):
    '''
    General caching model. This model is managed via uds.core.util.Cache.Cache class
    '''
    owner = models.CharField(max_length=128, db_index=True)
    key = models.CharField(max_length=64, primary_key=True)
    value = models.TextField(default='')
    created = models.DateTimeField()  # Date creation or validation of this entry. Set at write time
    validity = models.IntegerField(default=60)  # Validity of this entry, in seconds

    class Meta:
        '''
        Meta class to declare the name of the table at database
        '''
        db_table = 'uds_utility_cache'
        app_label = 'uds'

    @staticmethod
    def cleanUp():
        '''
        Purges the cache items that are no longer vaild.
        '''
        from django.db import connection, transaction
        con = connection
        cursor = con.cursor()
        logger.info("Purging cache items")
        cursor.execute('DELETE FROM uds_utility_cache WHERE created + validity < now()')
        transaction.commit_unless_managed()

    def __unicode__(self):
        expired = getSqlDatetime() > self.created + timedelta(seconds=self.validity)
        if expired:
            expired = "Expired"
        else:
            expired = "Active"
        return u"{0} {1} = {2} ({3})".format(self.owner, self.key, self.value, expired)


