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
from django.db.models import signals
from django.utils.encoding import python_2_unicode_compatible

from uds.models.Authenticator import Authenticator
from uds.models.Util import UnsavedForeignKey
from uds.models.Util import NEVER
from uds.models.Util import getSqlDatetime
from uds.core.util import log
from uds.models.UUIDModel import UUIDModel

import logging

logger = logging.getLogger(__name__)

__updated__ = '2017-06-08'


@python_2_unicode_compatible
class User(UUIDModel):
    '''
    This class represents a single user, associated with one authenticator
    '''
    # pylint: disable=model-missing-unicode, maybe-no-member
    manager = UnsavedForeignKey(Authenticator, on_delete=models.CASCADE, related_name='users')
    name = models.CharField(max_length=128, db_index=True)
    real_name = models.CharField(max_length=128)
    comments = models.CharField(max_length=256)
    state = models.CharField(max_length=1, db_index=True)
    password = models.CharField(max_length=128, default='')  # Only used on "internal" sources
    staff_member = models.BooleanField(default=False)  # Staff members can login to admin
    is_admin = models.BooleanField(default=False)  # is true, this is a super-admin
    last_access = models.DateTimeField(default=NEVER)
    parent = models.CharField(max_length=50, default=None, null=True)
    created = models.DateTimeField(default=getSqlDatetime, blank=True)

    class Meta(UUIDModel.Meta):
        '''
        Meta class to declare default order and unique multiple field index
        '''
        unique_together = (("manager", "name"),)
        ordering = ('name',)
        app_label = 'uds'

    def getUsernameForAuth(self):
        '''
        Return the username transformed for authentication.
        This transformation is used for transports only, not for transforming
        anything at login time. Transports that will need the username, will invoke
        this method.
        The manager (an instance of uds.core.auths.Authenticator), can transform the database stored username
        so we can, for example, add @domain in some cases.
        '''
        return self.getManager().getForAuth(self.name)

    @property
    def pretty_name(self):
        return self.name + '@' + self.manager.name

    def getManager(self):
        '''
        Returns the authenticator object that owns this user.

        :note: The returned value is an instance of the authenticator class used to manage this user, not a db record.
        '''
        return self.manager.getInstance()

    def isStaff(self):
        '''
        Return true if this user is admin or staff member
        '''
        return self.staff_member or self.is_admin

    def prefs(self, modName):
        '''
        Returns the preferences for this user for the provided module name.

        Usually preferences will be associated with transports, but can be preferences registered by ANY module.

        Args:
            modName: name of the module to get preferences for


        Returns:

            The preferences for the module specified as a dictionary (can be empty if module is not found).

            If the module exists, the preferences will always contain something, but may be the values are the default ones.

        '''
        from uds.core.managers.UserPrefsManager import UserPrefsManager
        return UserPrefsManager.manager().getPreferencesForUser(modName, self)

    def updateLastAccess(self):
        '''
        Updates the last access for this user with the current time of the sql server
        '''
        self.last_access = getSqlDatetime()
        self.save()

    def logout(self):
        '''
        Invoked to log out this user
        Returns the url where to redirect user, or None if default url will be used
        '''
        return self.getManager().logout(self.name)

    def getGroups(self):
        '''
        returns the groups (and metagroups) this user belongs to
        '''
        if self.parent is not None and self.parent != '':
            try:
                usr = User.objects.get(uuid=self.parent)
            except Exception:  # If parent do not exists
                usr = self
        else:
            usr = self

        grps = list()
        for g in usr.groups.filter(is_meta=False):
            grps += (g.id,)
            yield g
        # Locate metagroups
        for g in self.manager.groups.filter(is_meta=True):
            gn = g.groups.filter(id__in=grps).count()

            logger.debug('gn = {}'.format(gn))
            logger.debug('groups count: {}'.format(g.groups.count()))

            if g.meta_if_any is True and gn > 0:
                gn = g.groups.count()

            logger.debug('gn after = {}'.format(gn))

            if gn == g.groups.count():  # If a meta group is empty, all users belongs to it. we can use gn != 0 to check that if it is empty, is not valid
                # This group matches
                yield g

    def __str__(self):
        return u"User {0}(id:{1}) from auth {2}".format(self.name, self.id, self.manager.name)

    @staticmethod
    def beforeDelete(sender, **kwargs):
        '''
        Used to invoke the Service class "Destroy" before deleting it from database.

        In this case, this method ensures that the user has no userServices assigned and, if it has,
        mark those services for removal

        :note: If destroy raises an exception, the deletion is not taken.
        '''
        toDelete = kwargs['instance']

        # first, we invoke removeUser. If this raises an exception, user will not
        # be removed
        toDelete.getManager().removeUser(toDelete.name)

        # now removes all "child" of this user, if it has children
        User.objects.filter(parent=toDelete.id).delete()

        # Remove related logs
        log.clearLogs(toDelete)

        # Removes all user services assigned to this user (unassign it and mark for removal)
        for us in toDelete.userServices.all():
            us.assignToUser(None)
            us.remove()

        logger.debug('Deleted user {0}'.format(toDelete))


signals.pre_delete.connect(User.beforeDelete, sender=User)
