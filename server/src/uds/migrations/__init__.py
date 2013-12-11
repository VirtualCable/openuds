from __future__ import unicode_literals

from south import signals

from uds import models
import logging

logger = logging.getLogger(__name__)

# Ensure tables that needs to be in InnoDB are so
def modify_MySQL_storage(*args, **kwargs):
    from django.db import connection
    cursor = connection.cursor()
    logger.info('Converting tables')
    
    innoDbTables = ( models.UserService, models.DeployedService, models.DeployedServicePublication,
                     models.Scheduler, models.DelayedTask, models.User, models.Group, models.Authenticator,
                     models.Service, models.Provider, models.Storage)
    for model in innoDbTables:
        db_table=model._meta.db_table
        stmt = 'ALTER TABLE %s ENGINE=%s' % (db_table,'InnoDB')
        cursor.execute(stmt)
        # sets charset to utf8
        stmt = 'ALTER TABLE %s CHARACTER SET \'utf8\' COLLATE \'utf8_general_ci\'' % db_table
        cursor.execute(stmt)

#signals.post_migrate.connect(modify_MySQL_storage)
