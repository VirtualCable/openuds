# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2021 Virtual Cable S.L.U.
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
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
"""
import typing
import logging
import operator
from datetime import datetime, timedelta

from django.db import models, transaction

from uds.core.environment import Environment
from uds.core.util import log, states, calendar, serializer
from uds.core.services.exceptions import InvalidServiceException

from .uuid_model import UUIDModel
from .tag import TaggingMixin

from .os_manager import OSManager
from .service import Service
from .transport import Transport
from .group import Group
from .image import Image
from .service_pool_group import ServicePoolGroup
from .account import Account

from .util import NEVER
from .util import getSqlDatetime


# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.models import (
        UserService,
        ServicePoolPublication,
        ServicePoolPublicationChangelog,
        User,
        Group,
        MetaPoolMember,
        CalendarAccess,
        CalendarAction,
    )

logger = logging.getLogger(__name__)


# pylint: disable=too-many-public-methods
class ServicePool(UUIDModel, TaggingMixin):  #  type: ignore
    """
    A deployed service is the Service produced element that is assigned finally to an user (i.e. a Virtual Machine, etc..)
    """

    name = models.CharField(max_length=128, default='')
    short_name = models.CharField(max_length=32, default='')
    comments = models.CharField(max_length=256, default='')
    service: 'models.ForeignKey[Service]' = models.ForeignKey(
        Service,
        related_name='deployedServices',
        on_delete=models.CASCADE,
    )
    osmanager: 'models.ForeignKey[OSManager | None]' = models.ForeignKey(
        OSManager,
        null=True,
        blank=True,
        related_name='deployedServices',
        on_delete=models.CASCADE,
    )
    transports: 'models.ManyToManyField[Transport, ServicePool]' = (
        models.ManyToManyField(
            Transport, related_name='deployedServices', db_table='uds__ds_trans'
        )
    )
    assignedGroups: 'models.ManyToManyField[Group, ServicePool]' = (
        models.ManyToManyField(
            Group, related_name='deployedServices', db_table='uds__ds_grps'
        )
    )
    state = models.CharField(
        max_length=1, default=states.servicePool.ACTIVE, db_index=True
    )
    state_date = models.DateTimeField(default=NEVER)
    show_transports = models.BooleanField(default=True)
    visible = models.BooleanField(default=True)
    allow_users_remove = models.BooleanField(default=False)
    allow_users_reset = models.BooleanField(default=False)

    ignores_unused = models.BooleanField(default=False)

    image: 'models.ForeignKey[Image | None]' = models.ForeignKey(
        Image,
        null=True,
        blank=True,
        related_name='deployedServices',
        on_delete=models.SET_NULL,
    )

    servicesPoolGroup: 'models.ForeignKey[ServicePoolGroup | None]' = models.ForeignKey(
        ServicePoolGroup,
        null=True,
        blank=True,
        related_name='servicesPools',
        on_delete=models.SET_NULL,
    )

    # Message if access denied
    calendar_message = models.CharField(default='', max_length=256)
    # Default fallback action for access
    fallbackAccess = models.CharField(default=states.action.ALLOW, max_length=8)

    # Usage accounting
    account: 'models.ForeignKey[Account | None]' = models.ForeignKey(
        Account,
        null=True,
        blank=True,
        related_name='servicesPools',
        on_delete=models.CASCADE,
    )

    initial_srvs = models.PositiveIntegerField(default=0)
    cache_l1_srvs = models.PositiveIntegerField(default=0)
    cache_l2_srvs = models.PositiveIntegerField(default=0)
    max_srvs = models.PositiveIntegerField(default=0)
    current_pub_revision = models.PositiveIntegerField(default=1)

    # "fake" declarations for type checking
    objects: 'models.manager.Manager["ServicePool"]'
    publications: 'models.manager.RelatedManager[ServicePoolPublication]'
    memberOfMeta: 'models.manager.RelatedManager[MetaPoolMember]'
    userServices: 'models.manager.RelatedManager[UserService]'
    calendarAccess: 'models.manager.RelatedManager[CalendarAccess]'
    calendaraction_set: 'models.manager.RelatedManager[CalendarAction]'
    changelog: 'models.manager.RelatedManager[ServicePoolPublicationChangelog]'

    class Meta(UUIDModel.Meta):
        """
        Meta class to declare the name of the table at database
        """

        db_table = 'uds__deployed_service'
        app_label = 'uds'

    def getEnvironment(self) -> Environment:
        """
        Returns an environment valid for the record this object represents
        """
        return Environment.getEnvForTableElement(self._meta.verbose_name, self.id)  # type: ignore

    def activePublication(self) -> typing.Optional['ServicePoolPublication']:
        """
        Returns the current valid publication for this deployed service.

        Returns:
            Publication db record if this deployed service has an valid active publication.

            None if there is no valid publication for this deployed service.
        """
        try:
            return self.publications.filter(state=states.publication.USABLE)[0]  # type: ignore  # Slicing is not supported by pylance right now
        except Exception:
            return None

    def transformsUserOrPasswordForService(self) -> bool:
        if self.osmanager:
            return self.osmanager.getType().transformsUserOrPasswordForService()
        return False

    def processUserPassword(self, username, password):
        """
        This method is provided for consistency between UserService and ServicePool
        There is no posibility to check the username and password that a user will use to
        connect to a service at this level, because here there is no relation between both.

        The only function of this method is allow Transport to transform username/password in
        getConnectionInfo without knowing if it is requested by a ServicePool or an UserService
        """
        return username, password

    @staticmethod
    def getRestrainedsQuerySet() -> 'models.QuerySet[ServicePool]':
        from uds.models.user_service import (  # pylint: disable=import-outside-toplevel
            UserService,
        )
        from uds.core.util.config import (  # pylint: disable=import-outside-toplevel
            GlobalConfig,
        )
        from django.db.models import Count  # pylint: disable=import-outside-toplevel

        if GlobalConfig.RESTRAINT_TIME.getInt() <= 0:
            return (
                ServicePool.objects.none()
            )  # Do not perform any restraint check if we set the globalconfig to 0 (or less)

        date = getSqlDatetime() - timedelta(
            seconds=GlobalConfig.RESTRAINT_TIME.getInt()
        )
        min_ = GlobalConfig.RESTRAINT_COUNT.getInt()

        res = []
        for v in (
            UserService.objects.filter(
                state=states.userService.ERROR, state_date__gt=date
            )
            .values('deployed_service')
            .annotate(how_many=Count('deployed_service'))
            .order_by('deployed_service')
        ):
            if v['how_many'] >= min_:
                res.append(v['deployed_service'])
        return ServicePool.objects.filter(pk__in=res)

    @staticmethod
    def getRestraineds() -> typing.Iterator['ServicePool']:
        return ServicePool.getRestrainedsQuerySet().iterator()

    @property
    def owned_by_meta(self) -> bool:
        return self.memberOfMeta.count() > 0

    @property
    def visual_name(self) -> str:
        logger.debug(
            "SHORT: %s %s %s", self.short_name, self.short_name is not None, self.name
        )
        if self.short_name and str(self.short_name).strip():
            return str(self.short_name.strip())
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
        from uds.core.util.config import (  # pylint: disable=import-outside-toplevel
            GlobalConfig,
        )

        if GlobalConfig.RESTRAINT_TIME.getInt() <= 0:
            return False  # Do not perform any restraint check if we set the globalconfig to 0 (or less)

        date = typing.cast(datetime, getSqlDatetime()) - timedelta(
            seconds=GlobalConfig.RESTRAINT_TIME.getInt()
        )
        if (
            self.userServices.filter(
                state=states.userService.ERROR, state_date__gt=date
            ).count()
            >= GlobalConfig.RESTRAINT_COUNT.getInt()
        ):
            return True

        return False

    def isInMaintenance(self) -> bool:
        return self.service.isInMaintenance() if self.service else True

    def isVisible(self) -> bool:
        return self.visible  # type: ignore

    def isUsable(self) -> bool:
        return (
            self.state == states.servicePool.ACTIVE
            and not self.isInMaintenance()
            and not self.isRestrained()
        )

    def toBeReplaced(self, forUser: 'User') -> typing.Optional[datetime]:
        activePub: typing.Optional['ServicePoolPublication'] = self.activePublication()
        # If no publication or current revision, it's not going to be replaced
        if activePub is None:
            return None

        # If has os manager, check if it is persistent
        if self.osmanager and self.osmanager.getInstance().isPersistent():
            return None

        # Return the date
        try:
            found = typing.cast(
                'UserService',
                self.assignedUserServices().filter(
                    user=forUser, state__in=states.userService.VALID_STATES
                )[
                    0
                ],  # type: ignore  # Slicing is not supported by pylance right now
            )
            if activePub and found.publication and activePub.id != found.publication.id:
                ret = self.recoverValue('toBeReplacedIn')
                if ret:
                    return serializer.deserialize(ret)

        except Exception:  # nosec: We don't want to fail if there is any exception
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
        for ac in sorted(
            self.calendarAccess.all(), key=operator.attrgetter('priority')
        ):
            if calendar.CalendarChecker(ac.calendar).check(chkDateTime):
                access = ac.access
                break  # Stops on first rule match found

        return access == states.action.ALLOW

    def getDeadline(
        self, chkDateTime: typing.Optional[datetime] = None
    ) -> typing.Optional[int]:
        """Gets the deadline for an access on chkDateTime in seconds

        Keyword Arguments:
            chkDateTime {typing.Optional[datetime]} -- [Gets the deadline for this date instead of current] (default: {None})

        Returns:
            typing.Optional[int] -- [Returns deadline in secods. If no deadline (forever), will return None]
        """
        if chkDateTime is None:
            chkDateTime = typing.cast(datetime, getSqlDatetime())

        if self.isAccessAllowed(chkDateTime) is False:
            return -1

        deadLine = None

        for ac in self.calendarAccess.all():
            if (
                ac.access == states.action.ALLOW
                and self.fallbackAccess == states.action.DENY
            ):
                nextE = calendar.CalendarChecker(ac.calendar).nextEvent(
                    chkDateTime, False
                )
                if not deadLine or (nextE and deadLine > nextE):
                    deadLine = nextE
            elif ac.access == states.action.DENY:  # DENY
                nextE = calendar.CalendarChecker(ac.calendar).nextEvent(
                    chkDateTime, True
                )
                if not deadLine or (nextE and deadLine > nextE):
                    deadLine = nextE

        if deadLine is None:
            if self.fallbackAccess == states.action.ALLOW:
                return None
            return -1

        return int((deadLine - chkDateTime).total_seconds())

    def storeValue(self, name: str, value: typing.Any):
        """
        Stores a value inside custom storage

        Args:
            name: Name of the value to store
            value: Value of the value to store
        """
        self.getEnvironment().storage.put(name, value)

    def recoverValue(self, name: str) -> typing.Any:
        """
        Recovers a value from custom storage

        Args:
            name: Name of values to recover

        Returns:
            Stored value, None if no value was stored
        """
        return typing.cast(str, self.getEnvironment().storage.get(name))

    def setState(self, state: str, save: bool = True) -> None:
        """
        Updates the state of this object and, optionally, saves it

        Args:
            state: new State to store at record

            save: Defaults to true. If false, record will not be saved to db, just modified

        """
        self.state = state
        self.state_date = getSqlDatetime()
        if save:
            self.save()

    def remove(self) -> None:
        """
        Marks the deployed service for removing.

        The background worker will be the responsible for removing the deployed service
        """
        self.setState(states.servicePool.REMOVABLE)

    def removed(self) -> None:
        """
        Mark the deployed service as removed.
        Basically, deletes the user service
        """
        # self.transports.clear()
        # self.assignedGroups.clear()
        # self.osmanager = None
        # self.service = None
        # self.setState(State.REMOVED)
        self.delete()

    def markOldUserServicesAsRemovables(
        self,
        activePub: typing.Optional['ServicePoolPublication'],
        skipAssigned: bool = False,
    ):
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
        nonActivePub: 'ServicePoolPublication'
        userService: 'UserService'

        if activePub is None:
            logger.error(
                'No active publication, don\'t know what to erase!!! (ds = %s)', self
            )
            return
        for nonActivePub in self.publications.exclude(id=activePub.id):
            for userService in nonActivePub.userServices.filter(
                state=states.userService.PREPARING
            ):
                userService.cancel()
            with transaction.atomic():
                nonActivePub.userServices.exclude(cache_level=0).filter(
                    state=states.userService.USABLE
                ).update(state=states.userService.REMOVABLE, state_date=now)
                if not skipAssigned:
                    nonActivePub.userServices.filter(
                        cache_level=0, state=states.userService.USABLE, in_use=False
                    ).update(state=states.userService.REMOVABLE, state_date=now)

    def validateGroups(self, groups: typing.Iterable['Group']) -> None:
        """
        Ensures that at least a group of groups (database groups) has access to this Service Pool
        raise an InvalidUserException if fails check
        """
        from uds.core import auths  # pylint: disable=import-outside-toplevel

        if not set(groups) & set(
            self.assignedGroups.all()  # pylint: disable=no-member
        ):  # pylint: disable=no-member
            raise auths.exceptions.InvalidUserException()

    def validatePublication(self) -> None:
        """
        Ensures that, if this service has publications, that a publication is active
        raises an IvalidServiceException if check fails
        """
        if (
            self.activePublication() is None
            and self.service
            and self.service.getType().publicationType is not None
        ):
            raise InvalidServiceException()

    def validateTransport(self, transport) -> None:
        if (
            self.transports.filter(id=transport.id).count()    # pylint: disable=no-member
            == 0  # pylint: disable=no-member
        ):  # pylint: disable=no-member
            raise InvalidServiceException()

    def validateUser(self, user: 'User') -> None:
        """
        Validates that the user has access to this deployed service

        Args:
            user: User (db record) to check if has access to this deployed service

        Raises:
            InvalidUserException() if user do not has access to this deployed service

            InvalidServiceException() if user has rights to access, but the deployed service is not ready (no active publication)

        """
        # We have to check if at least one group from this user is valid for this deployed service

        logger.debug('User: %s', user.id)
        logger.debug('ServicePool: %s', self.id)
        self.validateGroups(user.getGroups())
        self.validatePublication()

    @staticmethod
    def getDeployedServicesForGroups(
        groups: typing.Iterable['Group'], user: typing.Optional['User'] = None
    ) -> typing.Iterable['ServicePool']:
        """
        Return deployed services with publications for the groups requested.

        Args:
            groups: List of groups to check

        Returns:
            List of accesible deployed services
        """
        from uds.core import services  # pylint: disable=import-outside-toplevel

        servicesNotNeedingPub = [
            t.type() for t in services.factory().servicesThatDoNotNeedPublication()
        ]
        # Get services that HAS publications
        query = (
            ServicePool.objects.filter(
                assignedGroups__in=groups,
                assignedGroups__state=states.group.ACTIVE,
                state=states.servicePool.ACTIVE,
                visible=True,
            )
            .annotate(
                pubs_active=models.Count(
                    'publications',
                    filter=models.Q(publications__state=states.publication.USABLE),
                    distinct=True,
                )
            )
            .annotate(
                usage_count=models.Count(
                    'userServices',
                    filter=models.Q(
                        userServices__state__in=states.userService.VALID_STATES,
                        userServices__cache_level=0,
                    ),
                    distinct=True,
                )
            )
            .prefetch_related(
                'transports',
                'transports__networks',
                'memberOfMeta',
                'osmanager',
                'publications',
                'servicesPoolGroup',
                'servicesPoolGroup__image',
                'service',
                'service__provider',
                'calendarAccess',
                'calendarAccess__calendar',
                'calendarAccess__calendar__rules',
                'image',
            )
        )

        if user:  # Optimize loading if there is some assgned service..
            query = query.annotate(
                number_in_use=models.Count(
                    'userServices',
                    filter=models.Q(
                        userServices__user=user,
                        userServices__in_use=True,
                        userServices__state__in=states.userService.USABLE,
                    ),
                )
            )
        servicePool: 'ServicePool'
        for servicePool in query:
            if typing.cast(typing.Any, servicePool).pubs_active or (
                servicePool.service
                and servicePool.service.data_type in servicesNotNeedingPub
            ):
                yield servicePool

    def publish(self, changeLog: typing.Optional[str] = None) -> None:
        """
        Launches the publication of this deployed service.

        No check is done, it simply redirects the request to PublicationManager, where checks are done.
        """
        from uds.core.managers import (  # pylint: disable=import-outside-toplevel
            publicationManager,
        )

        publicationManager().publish(self, changeLog)

    def unpublish(self) -> None:
        """
        Unpublish (removes) current active publcation.

        It checks that there is an active publication, and then redirects the request to the publication itself
        """
        pub = self.activePublication()
        if pub:
            pub.unpublish()

    def cachedUserServices(self) -> 'models.QuerySet[UserService]':
        """
        ':rtype uds.models.user_service.UserService'
        Utility method to access the cached user services (level 1 and 2)

        Returns:
            A list of db records (userService) with cached user services
        """
        return self.userServices.exclude(cache_level=0)

    def assignedUserServices(self) -> 'models.QuerySet[UserService]':
        """
        Utility method to access the assigned user services

        Returns:
            A list of db records (userService) with assinged user services
        """
        return self.userServices.filter(cache_level=0)

    def erroneousUserServices(self) -> 'models.QuerySet[UserService]':
        """
        Utility method to locate invalid assigned user services.

        If an user deployed service is assigned, it MUST have an user associated.

        If it don't has an user associated, the user deployed service is wrong.
        """
        return self.userServices.filter(cache_level=0, user=None)

    def usage(self, cachedValue=-1) -> int:
        """
        Returns the % used services, related to "maximum" user services
        If no "maximum" number of services, will return 0% ofc
        cachedValue is used to optimize (if known the number of assigned services, we can avoid to query the db)
        """
        maxs = self.max_srvs
        if maxs == 0 and self.service:
            maxs = self.service.getInstance().maxDeployed

        if maxs <= 0:
            return 0

        if cachedValue == -1:
            cachedValue = (
                self.assignedUserServices()
                .filter(state__in=states.userService.VALID_STATES)
                .count()
            )

        return 100 * cachedValue // maxs

    def testServer(
        self, host: str, port: typing.Union[str, int], timeout: float = 4
    ) -> bool:
        return bool(self.service) and self.service.testServer(host, port, timeout)

    # Utility for logging
    def log(self, message: str, level: int = log.INFO) -> None:
        log.doLog(self, level, message, log.INTERNAL)

    @staticmethod
    def beforeDelete(sender, **kwargs) -> None:  # pylint: disable=unused-argument
        """
        Used to invoke the Service class "Destroy" before deleting it from database.

        The main purpuse of this hook is to call the "destroy" method of the object to delete and
        to clear related data of the object (environment data such as own storage, cache, etc...

        :note: If destroy raises an exception, the deletion is not taken.
        """
        from uds.core.util.permissions import (    # pylint: disable=import-outside-toplevel
            clean,
        )

        toDelete: 'ServicePool' = kwargs['instance']

        logger.debug('Deleting Service Pool %s', toDelete)
        toDelete.getEnvironment().clearRelatedData()

        # Clears related logs
        log.clearLogs(toDelete)

        # Clears related permissions
        clean(toDelete)

    # returns CSV header
    @staticmethod
    def getCSVHeader(sep: str = ',') -> str:
        return sep.join(
            [
                'name',
                'initial',
                'cache_l1',
                'cache_l2',
                'max',
                'assigned_services',
                'cached_services',
            ]
        )

    # Return record as csv line using separator (default: ',')
    def toCsv(self, sep: str = ',') -> str:
        return sep.join(
            [
                self.name,
                str(self.initial_srvs),
                str(self.cache_l1_srvs),
                str(self.cache_l2_srvs),
                str(self.max_srvs),
                str(self.assignedUserServices().count()),
                str(self.cachedUserServices().count()),
            ]
        )

    def __str__(self):
        return (
            f'Service pool {self.name}({self.id}) with {self.initial_srvs}'
            f' as initial, {self.cache_l1_srvs} as L1 cache, {self.cache_l2_srvs}'
            f' as L2 cache, {self.max_srvs} as max'
        )


# Connects a pre deletion signal to Authenticator
models.signals.pre_delete.connect(ServicePool.beforeDelete, sender=ServicePool)
