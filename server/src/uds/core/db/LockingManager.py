'''
From django locking manager snippet at http://djangosnippets.org/snippets/833/
Author:
    miohtama
'''

from django.db import models, connection
import logging

__updated__ = '2014-02-19'

logger = logging.getLogger(__name__)


# Table locking in mysql at least is based on thread requesting it, so we should not have problems with a bit of care
class LockingManager(models.Manager):
    """ Add lock/unlock functionality to manager.

    Example::

        class Job(models.Model):

            manager = LockingManager()

            counter = models.IntegerField(null=True, default=0)

            @staticmethod
            def do_atomic_update(job_id)
                ''' Updates job integer, keeping it below 5 '''
                try:
                    # Ensure only one HTTP request can do this update at once.
                    Job.objects.lock()

                    job = Job.object.get(id=job_id)
                    # If we don't lock the tables two simultanous
                    # requests might both increase the counter
                    # going over 5
                    if job.counter < 5:
                        job.counter += 1
                        job.save()

                finally:
                    Job.objects.unlock()


    """

    def lock(self):
        """ Lock table.

        Locks the object model table so that atomic update is possible.
        Simulatenous database access request pend until the lock is unlock()'ed.

        Note: If you need to lock multiple tables, you need to do lock them
        all in one SQL clause and this function is not enough. To avoid
        dead lock, all tables must be locked in the same order.

        See http://dev.mysql.com/doc/refman/5.0/en/lock-tables.html
        """
        con = connection
        cursor = con.cursor()
        table = self.model._meta.db_table
        # logger.debug("Locking table %s" % table)
        cursor.execute("LOCK TABLES %s WRITE" % table)
        row = cursor.fetchone()
        return row

    def unlock(self):
        """ Unlock the table. """
        # logger.debug("Unlocked tables")
        con = connection
        cursor = con.cursor()
        # table = self.model._meta.db_table
        cursor.execute("UNLOCK TABLES")
        row = cursor.fetchone()
        return row
