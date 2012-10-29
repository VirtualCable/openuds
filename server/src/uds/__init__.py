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



from django.dispatch import dispatcher
from django.db.models import signals

# Make sure that all services are "available" at service startup
import services # to make sure that the packages are initialized at this point
import auths # To make sure that the packages are initialized at this point
import osmanagers # To make sure that packages are initialized at this point
import transports # To make sure that packages are initialized at this point
import models


def modify_MySQL_storage(sender, **kwargs):
    from django.db import connection
    cursor = connection.cursor()
    
    innoDbTables = ( models.UserService, models.DeployedService, models.DeployedServicePublication,
                     models.Scheduler, models.DelayedTask, )
    dicTables = { k._meta.db_table: True for k in innoDbTables }

    for model in kwargs['created_models']:
        db_table=model._meta.db_table
        if dicTables.has_key(db_table):
            stmt = 'ALTER TABLE %s ENGINE=%s' % (db_table,'InnoDB')
            cursor.execute(stmt)
        # sets charset to utf8
        stmt = 'ALTER TABLE %s CHARACTER SET \'utf8\' COLLATE \'utf8_general_ci\'' % db_table
        cursor.execute(stmt)
    

signals.post_syncdb.connect(modify_MySQL_storage, sender=models)
