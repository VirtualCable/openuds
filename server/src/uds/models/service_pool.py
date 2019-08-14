# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2019 Virtual Cable S.L.
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

"""
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
"""
import typing
import logging
import pickle
from datetime import datetime, timedelta

from django.db import models, transaction
from django.db.models import signals

from uds.core.environment import Environment
from uds.core.util import log
from uds.core.util import states
from uds.core.services.Exceptions import InvalidServiceException
from uds.models.uuid_model import UUIDModel
from uds.models.Tag import TaggingMixin

from uds.models.os_manager import OSManager
from uds.models.service import Service
from uds.models.transport import Transport
from uds.models.group import Group
from uds.models.image import Image
from uds.models.service_pool_group import ServicePoolGroup
from uds.models.calendar import Calendar
from uds.models.account import Account

from uds.models.util import NEVER
from uds.models.util import getSqlDatetime

from uds.core.util.calendar import CalendarChecker

# Not imported in runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.models.user_service import UserService
    from uds.models.service_pool_publication import ServicePoolPublication


logger = logging.getLogger(__name__)

# pylint: disable=too-many-public-methods
class ServicePool(UUIDModel, TaggingMixin):  #  type: ignore
    """
    A deployed service is the Service produced element that is assigned finally to an user (i.e. a Virtual Machine, etc..)
    """
    # pylint: disable=model-missing-unicode
    name = models.CharField(max_length=128, default='')
    short_name = models.CharField(max_length=32, default='')
    comments = models.CharField(max_length=256, default='')
    service = models.ForeignKey(Service, null=True, blank=True, related_name='deployedServices', on_delete=models.CASCADE)
    osmanager = models.ForeignKey(OSManager, null=True, blank=True, related_name='deployedServices', on_delete=models.CASCADE)
    transports = models.ManyToManyField(Transport, related_name='deployedServices', db_table='uds__ds_trans')
    assignedGroups = models.ManyToManyField(Group, related_name='deployedServices', db_table='uds__ds_grps')
    state = models.CharField(max_length=1, default=states.servicePool.ACTIVE, db_index=True)
    state_date = models.DateTimeField(default=NEVER)
    show_transports = models.BooleanField(default=True)
    visible = models.BooleanField(default=True)
    allow_users_remove = models.BooleanField(default=False)
    allow_users_reset = models.BooleanField(default=False)

    ignores_unused = models.BooleanField(default=False)

    image = models.ForeignKey(Image, null=True, blank=True, related_name='deployedServices', on_delete=models.SET_NULL)

    servicesPoolGroup = models.ForeignKey(ServicePoolGroup, null=True, blank=True, related_name='servicesPools', on_delete=models.SET_NULL)

    accessCalendars = models.ManyToManyField(Calendar, related_name='accessSP', through='CalendarAccess')
    # Default fallback action for access
    fallbackAccess = models.CharField(default=states.action.ALLOW, max_length=8)
    actionsCalendars = models.ManyToManyField(Calendar, related_name='actionsSP', through='CalendarAction')

    # Usage accounting
    account = models.ForeignKey(Account, null=True, blank=True, related_name='servicesPools', on_delete=models.CASCADE)

    initial_srvs = models.PositiveIntegerField(default=0)
    cache_l1_srvs = models.PositiveIntegerField(default=0)
    cache_l2_srvs = models.PositiveIntegerField(default=0)
    max_srvs = models.PositiveIntegerField(default=0)
    current_pub_revision = models.PositiveIntegerField(default=1)

    # Meta service related
    # meta_pools = models.ManyToManyField('self', symmetrical=False)

    class Meta(UUIDModel.Meta):
        """
        Meta class to declare the name of the table at database
        """
        db_table = 'uds__deployed_service'
        app_label = 'uds'

    def getEnvironment(self):
        """
        Returns an environment valid for the record this object represents
        """
        return Environment.getEnvForTableElement(self._meta.verbose_name, self.id)

    def activePublication(self) -> typing.Optional['ServicePoolPublication']:
        """
        Returns the current valid publication for this deployed service.

        Returns:
            Publication db record if this deployed service has an valid active publication.

            None if there is no valid publication for this deployed service.
        """
        try:
            return self.publications.filter(state=states.publication.USABLE)[0]
        except Exception:
            return None

    def transformsUserOrPasswordForService(self):
        return self.osmanager.getType().transformsUserOrPasswordForService()

    def processUserPassword(self, username, password):
        """
        This method is provided for consistency between UserService and DeployedService
        There is no posibility to check the username and password that a user will use to
        connect to a service at this level, because here there is no relation between both.

        The only function of this method is allow Transport to transform username/password in
        getConnectionInfo without knowing if it is requested by a DeployedService or an UserService
        """
        return [username, password]

    @staticmethod
    def getRestraineds() -> typing.Iterable['DeployedService']:
        from uds.models.user_service import UserService  # pylint: disable=redefined-outer-name
        from uds.core.util.Config import GlobalConfig
        from django.db.models import Count

        if GlobalConfig.RESTRAINT_TIME.getInt() <= 0:
            return []  # Do not perform any restraint check if we set the globalconfig to 0 (or less)

        date = typing.cast(datetime, getSqlDatetime()) - timedelta(seconds=GlobalConfig.RESTRAINT_TIME.getInt())
        min_ = GlobalConfig.RESTRAINT_COUNT.getInt()

        res = []
        for v in UserService.objects.filter(state=states.userService.ERROR, state_date__gt=date).values('deployed_service').annotate(how_many=Count('deployed_service')).order_by('deployed_service'):
            if v['how_many'] >= min_:
                res.append(v['deployed_service'])
        return DeployedService.objects.filter(pk__in=res)

    @property
    def is_meta(self) -> bool:
        return self.memberOfMeta.count() > 0

    @property
    def visual_name(self) -> str:
        logger.debug("SHORT: %s %s %s", self.short_name, self.short_name is not None, self.name)
        if self.short_name is not None and str(self.short_name).strip() != '':
            return str(self.short_name)
        return str(self.name)

    def isRestrained(self) -> bool:
        """
        Maybe this deployed service is having problems, and that may block some task in some
        situations.

        To avoid this, we will use a "restrain" policy, where we restrain a deployed service for,
        for example, create new cache elements is reduced.

        The policy to check is that if a Deployed Service has 3 errors in the last 20 Minutes (by default), it is
        considered restrained.

        The time that a service is in restrain mode is 20 minutes by default (1200 secs), but it can be modified
        at globalconfig variables
        """
        from uds.core.util.Config import GlobalConfig

        if GlobalConfig.RESTRAINT_TIME.getInt() <= 0:
            return False  # Do not perform any restraint check if we set the globalconfig to 0 (or less)

        date = typing.cast(datetime, getSqlDatetime()) - timedelta(seconds=GlobalConfig.RESTRAINT_TIME.getInt())
        if self.userServices.filter(state=states.userService.ERROR, state_date__gt=date).count() >= GlobalConfig.RESTRAINT_COUNT.getInt():
            return True

        return False

    def isInMaintenance(self) -> bool:
        return self.service is not None and self.service.isInMaintenance()

    def isVisible(self) -> bool:
        return self.visible

    def isUsable(self) -> bool:
        return self.state == states.servicePool.ACTIVE and not self.isInMaintenance() and not self.isRestrained()

    def toBeReplaced(self, forUser) ->  typing.Optional[datetime]:
        activePub = self.activePublication()
        if activePub is None or activePub.revision == self.current_pub_revision - 1:
            return None

        # Return the date
        try:
            if activePub and activePub.id != self.assignedUserServices().filter(user=forUser)[0].publication.id:
                ret = self.recoverValue('toBeReplacedIn')
                if ret is not None:
                    return pickle.loads(ret)
        except Exception:
            # logger.exception('Recovering publication death line')
            pass

        return None

    def isAccessAllowed(self, chkDateTime=None) -> bool:
        """
        Checks if the access for a service pool is allowed or not (based esclusively on associated calendars)
        """
        if chkDateTime is None:
            chkDateTime = getSqlDatetime()

        access = self.fallbackAccess
        # Let's see if we can access by current datetime
        for ac in self.calendarAccess.order_by('priority'):
            if CalendarChecker(ac.calendar).check(chkDateTime) is True:
                access = ac.access
                break  # Stops on first rule match found

        return access == states.action.ALLOW

    def getDeadline(self, chkDateTime=None):
        """
        Gets the deadline for an access on chkDateTime
        """
        if chkDateTime is None:
            chkDateTime = getSqlDatetime()

        if self.isAccessAllowed(chkDateTime) is False:
            return -1

        deadLine = None

        for ac in self.calendarAccess.all():
            if ac.access == states.action.ALLOW and self.fallbackAccess == states.action.DENY:
                nextE = CalendarChecker(ac.calendar).nextEvent(chkDateTime, False)
                if deadLine is None or deadLine > nextE:
                    deadLine = nextE
            elif ac.access == states.action.DENY:  # DENY
                nextE = CalendarChecker(ac.calendar).nextEvent(chkDateTime, True)
                if deadLine is None or deadLine > nextE:
                    deadLine = nextE

        if deadLine is None:
            if self.fallbackAccess == states.action.ALLOW:
                return None
            else:
                return -1

        return int((deadLine - chkDateTime).total_seconds())

    def storeValue(self, name, value):
        """
        Stores a value inside custom storage

        Args:
            name: Name of the value to store
            value: Value of the value to store
        """
        self.getEnvironment().storage.put(name, value)

    def recoverValue(self, name):
        """
        Recovers a value from custom storage

        Args:
            name: Name of values to recover

        Returns:
            Stored value, None if no value was stored
        """
        return self.getEnvironment().storage.get(name)

    def setState(self, state, save=True):
        """
        Updates the state of this object and, optionally, saves it

        Args:
            state: new State to store at record

            save: Defaults to true. If false, record will not be saved to db, just modified

        """
        self.state = state
        self.state_date = getSqlDatetime()
        if save is True:
            self.save()

    def remove(self):
        """
        Marks the deployed service for removing.

        The background worker will be the responsible for removing the deployed service
        """
        self.setState(states.servicePool.REMOVABLE)

    def removed(self):
        """
        Mark the deployed service as removed.

        A background worker will check for removed deloyed services and clean database of them.
        """
        # self.transports.clear()
        # self.assignedGroups.clear()
        # self.osmanager = None
        # self.service = None
        # self.setState(State.REMOVED)
        self.delete()

    def markOldUserServicesAsRemovables(self, activePub):
        """
        Used when a new publication is finished.

        Marks all user deployed services that belongs to this deployed service, that do not belongs
        to "activePub" and are not in use as removable.

        Also cancels all preparing user services

        Better see the code, it's easier to understand :-)

        Args:
            activePub: Active publication used as "current" publication to make checks
        """
        now = getSqlDatetime()
        if activePub is None:
            logger.error('No active publication, don\'t know what to erase!!! (ds = %s)', self)
            return
        for ap in self.publications.exclude(id=activePub.id):
            for u in ap.userServices.filter(state=states.userService.PREPARING):
                u.cancel()
            with transaction.atomic():
                ap.userServices.exclude(cache_level=0).filter(state=states.userService.USABLE).update(state=states.userService.REMOVABLE, state_date=now)
                ap.userServices.filter(cache_level=0, state=states.userService.USABLE, in_use=False).update(state=states.userService.REMOVABLE, state_date=now)

    def validateGroups(self, grps):
        """
        Ensures that at least a group of grps (database groups) has access to this Service Pool
        raise an InvalidUserException if fails check
        """
        from uds.core import auths
        if not set(grps) & set(self.assignedGroups.all()):
            raise auths.Exceptions.InvalidUserException()

    def validatePublication(self):
        """
        Ensures that, if this service has publications, that a publication is active
        raises an IvalidServiceException if check fails
        """
        if self.activePublication() is None and self.service.getType().publicationType is not None:
            raise InvalidServiceException()

    def validateTransport(self, transport):
        try:
            self.transports.get(id=transport.id)
        except:
            raise InvalidServiceException()

    def validateUser(self, user) -> None:
        """
        Validates that the user has access to this deployed service

        Args:
            user: User (db record) to check if has access to this deployed service

        Returns:
            True if has access

        Raises:
            InvalidUserException() if user do not has access to this deployed service

            InvalidServiceException() if user has rights to access, but the deployed service is not ready (no active publication)

        """
        # We have to check if at least one group from this user is valid for this deployed service

        logger.debug('User: %s', user.id)
        logger.debug('DeployedService: %s', self.id)
        self.validateGroups(user.getGroups())
        self.validatePublication()

    # Stores usage accounting information
    def saveAccounting(self, userService, start, end):
        if self.account is None:
            return None

        return self.account.addUsageAccount(userService, start, end)

    @staticmethod
    def getDeployedServicesForGroups(groups) -> typing.List['DeployedService']:
        """
        Return deployed services with publications for the groups requested.

        Args:
            groups: List of groups to check

        Returns:
            List of accesible deployed services
        """
        from uds.core import services
        # Get services that HAS publications
        list1 = DeployedService.objects.filter(assignedGroups__in=groups, assignedGroups__state=states.group.ACTIVE,
                                               state=states.servicePool.ACTIVE, visible=True).distinct().annotate(cuenta=models.Count('publications')).exclude(cuenta=0)
        # Now get deployed services that DO NOT NEED publication
        doNotNeedPublishing = [t.type() for t in services.factory().servicesThatDoNotNeedPublication()]
        list2 = DeployedService.objects.filter(assignedGroups__in=groups, assignedGroups__state=states.group.ACTIVE, service__data_type__in=doNotNeedPublishing, state=states.servicePool.ACTIVE, visible=True)
        # And generate a single list without duplicates
        return list(set([r for r in list1] + [r for r in list2]))

    def publish(self, changeLog=None):
        """
        Launches the publication of this deployed service.

        No check is done, it simply redirects the request to PublicationManager, where checks are done.
        """
        from uds.core.managers.PublicationManager import PublicationManager
        PublicationManager.manager().publish(self, changeLog)

    def unpublish(self):
        """
        Unpublish (removes) current active publcation.

        It checks that there is an active publication, and then redirects the request to the publication itself
        """
        pub = self.activePublication()
        if pub is not None:
            pub.unpublish()

    def cachedUserServices(self):
        """
        ':rtype uds.models.user_service.UserService'
        Utility method to access the cached user services (level 1 and 2)

        Returns:
            A list of db records (userService) with cached user services
        """
        return self.userServices.exclude(cache_level=0)

    def assignedUserServices(self):
        """
        Utility method to access the assigned user services

        Returns:
            A list of db records (userService) with assinged user services
        """
        return self.userServices.filter(cache_level=0)

    def erroneousUserServices(self):
        """
        Utility method to locate invalid assigned user services.

        If an user deployed service is assigned, it MUST have an user associated.

        If it don't has an user associated, the user deployed service is wrong.
        """
        return self.userServices.filter(cache_level=0, user=None)

    def usage(self):
        """
        Returns the % used services, related to "maximum" user services
        If no "maximum" number of services, will return 0% ofc
        """
        maxs = self.max_srvs
        if maxs == 0:
            maxs = self.service.getInstance().maxDeployed

        if maxs <= 0:
            return 0

        return 100 * self.assignedUserServices().count() // maxs

    def testServer(self, host, port, timeout=4):
        return self.service.testServer(host, port, timeout)

    # parent accessors
    @property
    def proxy(self):
        return self.service.proxy

    # Utility for logging
    def log(self, message, level=log.INFO):
        log.doLog(self, level, message, log.INTERNAL)

    @staticmethod
    def beforeDelete(sender, **kwargs):
        """
        Used to invoke the Service class "Destroy" before deleting it from database.

        The main purpuse of this hook is to call the "destroy" method of the object to delete and
        to clear related data of the object (environment data such as own storage, cache, etc...

        :note: If destroy raises an exception, the deletion is not taken.
        """
        from uds.core.util.permissions import clean
        toDelete = kwargs['instance']

        logger.debug('Deleting Deployed Service %s', toDelete)
        toDelete.getEnvironment().clearRelatedData()

        # Clears related logs
        log.clearLogs(toDelete)

        # Clears related permissions
        clean(toDelete)

    def __str__(self):
        return 'Deployed service {}({}) with {} as initial, {} as L1 cache, {} as L2 cache, {} as max'.format(
            self.name, self.id, self.initial_srvs, self.cache_l1_srvs, self.cache_l2_srvs, self.max_srvs)


# Connects a pre deletion signal to Authenticator
signals.pre_delete.connect(ServicePool.beforeDelete, sender=ServicePool)

# For now, keep back compat with model name
DeployedService = ServicePool
