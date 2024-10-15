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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import collections.abc
import logging
import operator
import typing
from datetime import datetime, timedelta

from django.db import models, transaction

from uds.core import consts, exceptions, types
from uds.core.environment import Environment
from uds.core.services.exceptions import InvalidServiceException
from uds.core.util import calendar, log, serializer
from uds.core.util.model import sql_now

from .account import Account
from .group import Group
from .image import Image
from .osmanager import OSManager
from .service import Service
from .service_pool_group import ServicePoolGroup
from .tag import TaggingMixin
from .transport import Transport
from .uuid_model import UUIDModel

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.models import (
        CalendarAccess,
        CalendarAction,
        Group,
        MetaPoolMember,
        ServicePoolPublication,
        ServicePoolPublicationChangelog,
        User,
        UserService,
    )

logger = logging.getLogger(__name__)


# pylint: disable=too-many-public-methods
class ServicePool(UUIDModel, TaggingMixin):
    """
    A deployed service is the Service produced element that is assigned finally to an user (i.e. a Virtual Machine, etc..)
    """

    name = models.CharField(max_length=192, default='')  # Give enouth space for "macros"
    short_name = models.CharField(max_length=96, default='')  # Give enouth space for "macros"
    comments = models.CharField(max_length=256, default='')
    service = models.ForeignKey(
        Service,
        related_name='deployedServices',
        on_delete=models.CASCADE,
    )
    osmanager = models.ForeignKey(
        OSManager,
        null=True,
        blank=True,
        related_name='deployedServices',
        on_delete=models.CASCADE,
    )
    transports: 'models.ManyToManyField[Transport, ServicePool]' = models.ManyToManyField(
        Transport, related_name='deployedServices', db_table='uds__ds_trans'
    )
    assignedGroups: 'models.ManyToManyField[Group, ServicePool]' = models.ManyToManyField(
        Group, related_name='deployedServices', db_table='uds__ds_grps'
    )
    state = models.CharField(max_length=1, default=types.states.State.ACTIVE, db_index=True)
    state_date = models.DateTimeField(default=consts.NEVER)
    show_transports = models.BooleanField(default=True)
    visible = models.BooleanField(default=True)
    allow_users_remove = models.BooleanField(default=False)
    allow_users_reset = models.BooleanField(default=False)

    ignores_unused = models.BooleanField(default=False)

    image = models.ForeignKey(
        Image,
        null=True,
        blank=True,
        related_name='deployedServices',
        on_delete=models.SET_NULL,
    )

    servicesPoolGroup = models.ForeignKey(
        ServicePoolGroup,
        null=True,
        blank=True,
        related_name='servicesPools',
        on_delete=models.SET_NULL,
    )

    # Message if access denied
    calendar_message = models.CharField(default='', max_length=256)
    custom_message = models.CharField(default='', max_length=1024)
    display_custom_message = models.BooleanField(default=False)

    # Default fallback action for access
    fallbackAccess = models.CharField(default=types.states.State.ALLOW, max_length=8)

    # Usage accounting
    account = models.ForeignKey(
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
    # objects: 'models.manager.Manager["ServicePool"]'
    publications: 'models.manager.RelatedManager[ServicePoolPublication]'
    memberOfMeta: 'models.manager.RelatedManager[MetaPoolMember]'
    userServices: 'models.manager.RelatedManager[UserService]'
    calendarAccess: 'models.manager.RelatedManager[CalendarAccess]'
    calendaraction_set: 'models.manager.RelatedManager[CalendarAction]'
    changelog: 'models.manager.RelatedManager[ServicePoolPublicationChangelog]'

    # New nomenclature, but keeping old ones for compatibility
    @property
    def userservices(self) -> 'models.manager.RelatedManager[UserService]':
        return self.userServices

    @property
    def member_of_meta(self) -> 'models.manager.RelatedManager[MetaPoolMember]':
        return self.memberOfMeta

    @property
    def calendar_access(self) -> 'models.manager.RelatedManager[CalendarAccess]':
        return self.calendarAccess

    class Meta(UUIDModel.Meta):  # pyright: ignore
        """
        Meta class to declare the name of the table at database
        """

        db_table = 'uds__deployed_service'
        app_label = 'uds'

    def get_environment(self) -> Environment:
        """
        Returns an environment valid for the record this object represents
        """
        return Environment.environment_for_table_record(self._meta.verbose_name or self._meta.db_table, self.id)

    def active_publication(self) -> typing.Optional['ServicePoolPublication']:
        """
        Returns the current valid publication for this deployed service.

        Returns:
            Publication db record if this deployed service has an valid active publication.

            None if there is no valid publication for this deployed service.
        """
        try:
            return self.publications.filter(state=types.states.State.USABLE)[0]
        except Exception:
            return None

    def transforms_user_or_password_for_service(self) -> bool:
        if self.osmanager:
            return self.osmanager.get_type().is_credentials_modified_for_service()
        return False

    def process_user_password(self, username: str, password: str) -> tuple[str, str]:
        """
        This method is provided for consistency between UserService and ServicePool
        There is no posibility to check the username and password that a user will use to
        connect to a service at this level, because here there is no relation between both.

        The only function of this method is allow Transport to transform username/password in
        getConnectionInfo without knowing if it is requested by a ServicePool or an UserService
        """
        return username, password

    @staticmethod
    def restraineds_queryset() -> 'models.QuerySet[ServicePool]':
        from django.db.models import Count  # pylint: disable=import-outside-toplevel

        from uds.core.util.config import GlobalConfig  # pylint: disable=import-outside-toplevel
        from uds.models.user_service import UserService  # pylint: disable=import-outside-toplevel

        if GlobalConfig.RESTRAINT_TIME.as_int() <= 0:
            return (
                ServicePool.objects.none()
            )  # Do not perform any restraint check if we set the globalconfig to 0 (or less)

        date = sql_now() - timedelta(seconds=GlobalConfig.RESTRAINT_TIME.as_int())
        min_ = GlobalConfig.RESTRAINT_COUNT.as_int()

        res: list[dict[str, typing.Any]] = []
        for v in typing.cast(
            list[dict[str, typing.Any]],
            UserService.objects.filter(state=types.states.State.ERROR, state_date__gt=date)
            .values('deployed_service')
            .annotate(how_many=Count('deployed_service'))
            .order_by('deployed_service'),
        ):
            if v['how_many'] >= min_:
                res.append(v['deployed_service'])
        return ServicePool.objects.filter(pk__in=res)

    @staticmethod
    def restrained_pools() -> typing.Iterator['ServicePool']:
        return ServicePool.restraineds_queryset().iterator()

    @property
    def owned_by_meta(self) -> bool:
        return self.memberOfMeta.count() > 0
    
    @property
    def uses_cache(self) -> bool:
        return self.cache_l1_srvs > 0 or self.cache_l2_srvs > 0

    @property
    def visual_name(self) -> str:
        logger.debug("SHORT: %s %s %s", self.short_name, self.short_name != '', self.name)
        if self.short_name and str(self.short_name).strip():
            return str(self.short_name.strip())
        return str(self.name)

    def is_restrained(self) -> bool:
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
        from uds.core.util.config import GlobalConfig  # pylint: disable=import-outside-toplevel

        if GlobalConfig.RESTRAINT_TIME.as_int() <= 0:
            return False  # Do not perform any restraint check if we set the globalconfig to 0 (or less)

        date = sql_now() - timedelta(seconds=GlobalConfig.RESTRAINT_TIME.as_int())
        if (
            self.userServices.filter(state=types.states.State.ERROR, state_date__gt=date).count()
            >= GlobalConfig.RESTRAINT_COUNT.as_int()
        ):
            return True

        return False

    def remaining_restraint_time(self) -> int:
        from uds.core.util.config import GlobalConfig

        if GlobalConfig.RESTRAINT_TIME.as_int() <= 0:
            return 0

        date = sql_now() - timedelta(seconds=GlobalConfig.RESTRAINT_TIME.as_int())
        count = self.userServices.filter(state=types.states.State.ERROR, state_date__gt=date).count()
        if count < GlobalConfig.RESTRAINT_COUNT.as_int():
            return 0

        return GlobalConfig.RESTRAINT_TIME.as_int() - int(
            (
                sql_now()
                - self.userServices.filter(state=types.states.State.ERROR, state_date__gt=date)
                .latest('state_date')
                .state_date
            ).total_seconds()
        )

    def is_in_maintenance(self) -> bool:
        return self.service.is_in_maintenance() if self.service else True

    def is_visible(self) -> bool:
        return self.visible

    def is_usable(self) -> bool:
        return (
            self.state == types.states.State.ACTIVE
            and not self.is_in_maintenance()
            and not self.is_restrained()
        )

    def when_will_be_replaced(self, for_user: 'User') -> typing.Optional[datetime]:
        active_publication: typing.Optional['ServicePoolPublication'] = self.active_publication()
        # If no publication or current revision, it's not going to be replaced
        if active_publication is None:
            return None

        # If has os manager, check if it is persistent
        if self.osmanager and self.osmanager.get_instance().is_persistent():
            return None

        # Return the date
        try:
            found = self.assigned_user_services().filter(
                user=for_user, state__in=types.states.State.VALID_STATES
            )[
                0
            ]  # Raises exception if at least one is not found
            if active_publication and found.publication and active_publication.id != found.publication.id:
                ret = self.get_value('toBeReplacedIn')
                if ret:
                    return serializer.deserialize(ret)

        except Exception:  # nosec: We don't want to fail if there is any exception
            # logger.exception('Recovering publication death line')
            pass

        return None

    def is_access_allowed(self, check_datetime: typing.Optional[datetime] = None) -> bool:
        """
        Checks if the access for a service pool is allowed or not (based esclusively on associated calendars)
        """
        if check_datetime is None:
            check_datetime = sql_now()

        access = self.fallbackAccess
        # Let's see if we can access by current datetime
        for ac in sorted(self.calendarAccess.all(), key=operator.attrgetter('priority')):
            if calendar.CalendarChecker(ac.calendar).check(check_datetime):
                access = ac.access
                break  # Stops on first rule match found

        return access == types.states.State.ALLOW

    def get_deadline(self, check_datetime: typing.Optional[datetime] = None) -> typing.Optional[int]:
        """Gets the deadline for an access on check_datetime in seconds

        Args:
            check_datetime {typing.Optional[datetime]} -- [Gets the deadline for this date instead of current] (default: {None})

        Returns:
            typing.Optional[int] -- [Returns deadline in secods. If no deadline (forever), will return None]
        """
        if check_datetime is None:
            check_datetime = sql_now()

        if self.is_access_allowed(check_datetime) is False:
            return -1

        deadline = None

        for ac in self.calendarAccess.all():
            if ac.access == types.states.State.ALLOW and self.fallbackAccess == types.states.State.DENY:
                nextE = calendar.CalendarChecker(ac.calendar).next_event(check_datetime, False)
                if not deadline or (nextE and deadline > nextE):
                    deadline = nextE
            elif ac.access == types.states.State.DENY:  # DENY
                nextE = calendar.CalendarChecker(ac.calendar).next_event(check_datetime, True)
                if not deadline or (nextE and deadline > nextE):
                    deadline = nextE

        if deadline is None:
            if self.fallbackAccess == types.states.State.ALLOW:
                return None
            return -1

        return int((deadline - check_datetime).total_seconds())

    def set_value(self, name: str, value: typing.Any) -> None:
        """
        Stores a value inside custom storage

        Args:
            name: Name of the value to store
            value: Value of the value to store
        """
        self.get_environment().storage.put(name, value)

    def get_value(self, name: str) -> typing.Any:
        """
        Recovers a value from custom storage

        Args:
            name: Name of values to recover

        Returns:
            Stored value, None if no value was stored
        """
        return typing.cast(str, self.get_environment().storage.read(name))

    def set_state(self, state: str, save: bool = True) -> None:
        """
        Updates the state of this object and, optionally, saves it

        Args:
            state: new State to store at record

            save: Defaults to true. If false, record will not be saved to db, just modified

        """
        self.state = state
        self.state_date = sql_now()
        if save:
            self.save()

    def remove(self) -> None:
        """
        Marks the deployed service for removing.

        The background worker will be the responsible for removing the deployed service
        """
        self.set_state(types.states.State.REMOVABLE)

    def removed(self) -> None:
        """
        Mark the deployed service as removed.
        Basically, deletes the user service
        """
        # self.transports.clear()
        # self.assignedGroups.clear()
        # self.osmanager = None
        # self.service = None
        # self.set_state(State.REMOVED)
        self.delete()

    def mark_old_userservices_as_removable(
        self,
        active_publication: typing.Optional['ServicePoolPublication'],
        skip_assigned: bool = False,
    ) -> None:
        """
        Used when a new publication is finished.

        Marks all user deployed services that belongs to this deployed service, that do not belongs
        to "activePub" and are not in use as removable.

        Also cancels all preparing user services

        Better see the code, it's easier to understand :-)

        Args:
            active_publication: Active publication used as "current" publication to make checks
            skip_assigned: If true, assigned services will not be marked as removable
            
        """
        now = sql_now()
        non_active_publication: 'ServicePoolPublication'
        userservice: 'UserService'

        if active_publication is None:
            logger.error('No active publication, don\'t know what to erase!!! (ds = %s)', self)
            return
        for non_active_publication in self.publications.exclude(id=active_publication.id):
            for userservice in non_active_publication.userServices.filter(state=types.states.State.PREPARING):
                userservice.cancel()
            with transaction.atomic():
                non_active_publication.userServices.exclude(cache_level=0).filter(state=types.states.State.USABLE).update(
                    state=types.states.State.REMOVABLE, state_date=now
                )
                if not skip_assigned:
                    non_active_publication.userServices.filter(
                        cache_level=0, state=types.states.State.USABLE, in_use=False
                    ).update(state=types.states.State.REMOVABLE, state_date=now)

    def validate_groups(self, groups: collections.abc.Iterable['Group']) -> None:
        """
        Ensures that at least a group of groups (database groups) has access to this Service Pool
        raise an InvalidUserException if fails check
        """
        if not set(groups) & set(
            self.assignedGroups.all()  # pylint: disable=no-member
        ):  # pylint: disable=no-member
            raise exceptions.auth.InvalidUserException()

    def validate_publication(self) -> None:
        """
        Ensures that, if this service has publications, that a publication is active
        raises an IvalidServiceException if check fails
        """
        if (
            self.active_publication() is None
            and self.service
            and self.service.get_type().publication_type is not None
        ):
            raise InvalidServiceException()

    def validate_transport(self, transport: 'Transport') -> None:
        if (
            self.transports.filter(id=transport.id).count()  # pylint: disable=no-member
            == 0  # pylint: disable=no-member
        ):  # pylint: disable=no-member
            raise InvalidServiceException()

    def validate_user(self, user: 'User') -> None:
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
        self.validate_groups(user.get_groups())
        self.validate_publication()

    @staticmethod
    def get_pools_for_groups(
        groups: collections.abc.Iterable['Group'], user: typing.Optional['User'] = None
    ) -> collections.abc.Iterable['ServicePool']:
        """
        Return deployed services with publications for the groups requested.

        Args:
            groups: List of groups to check

        Returns:
            List of accesible deployed services
        """
        from uds.core import services  # pylint: disable=import-outside-toplevel

        services_not_needing_publication = [t.mod_type() for t in services.factory().services_not_needing_publication()]
        # Get services that HAS publications
        query = (
            ServicePool.objects.filter(
                assignedGroups__in=groups,
                assignedGroups__state=types.states.State.ACTIVE,
                state=types.states.State.ACTIVE,
                visible=True,
            )
            .annotate(
                pubs_active=models.Count(
                    'publications',
                    filter=models.Q(publications__state=types.states.State.USABLE),
                    distinct=True,
                )
            )
            .annotate(
                usage_count=models.Count(
                    'userServices',
                    filter=models.Q(
                        userServices__state__in=types.states.State.VALID_STATES,
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
                        userServices__state__in=types.states.State.USABLE,
                    ),
                )
            )
        servicepool: 'ServicePool'
        for servicepool in query:
            if typing.cast(typing.Any, servicepool).pubs_active or (
                servicepool.service and servicepool.service.data_type in services_not_needing_publication
            ):
                yield servicepool

    def publish(self, changelog: typing.Optional[str] = None) -> None:
        """
        Launches the publication of this deployed service.

        No check is done, it simply redirects the request to PublicationManager, where checks are done.
        """
        from uds.core.managers import publication_manager  # pylint: disable=import-outside-toplevel

        publication_manager().publish(self, changelog)

    def unpublish(self) -> None:
        """
        Unpublish (removes) current active publcation.

        It checks that there is an active publication, and then redirects the request to the publication itself
        """
        pub = self.active_publication()
        if pub:
            pub.unpublish()

    def cached_users_services(self) -> 'models.QuerySet[UserService]':
        """
        ':rtype uds.models.user_service.UserService'
        Utility method to access the cached user services (level 1 and 2)

        Returns:
            A list of db records (userService) with cached user services
        """
        return self.userServices.exclude(cache_level=types.services.CacheLevel.NONE)

    def assigned_user_services(self) -> 'models.QuerySet[UserService]':
        """
        Utility method to access the assigned user services

        Returns:
            A list of db records (userService) with assinged user services
        """
        return self.userServices.filter(cache_level=types.services.CacheLevel.NONE)

    def usage(self, cached_value: int = -1) -> types.pools.UsageInfo:
        """
        Returns the % used services, then count and the max related to "maximum" user services
        If no "maximum" number of services, will return 0% ofc
        cached_value is used to optimize (if known the number of assigned services, we can avoid to query the db)
        """
        maxs = self.max_srvs
        if maxs == 0:
            maxs = self.service.get_instance().userservices_limit

        if cached_value == -1:
            cached_value = (
                self.assigned_user_services().filter(state__in=types.states.State.VALID_STATES).count()
            )

        if maxs == 0 or maxs == consts.UNLIMITED:
            return types.pools.UsageInfo(cached_value, consts.UNLIMITED)

        return types.pools.UsageInfo(cached_value, maxs)

    def test_connectivity(self, host: str, port: typing.Union[str, int], timeout: float = 4) -> bool:
        return bool(self.service) and self.service.test_connectivity(host, port, timeout)

    # Utility for logging
    def log(self, message: str, level: types.log.LogLevel = types.log.LogLevel.INFO) -> None:
        log.log(self, level, message, types.log.LogSource.INTERNAL)

    @staticmethod
    def pre_delete(sender: typing.Any, **kwargs: typing.Any) -> None:  # pylint: disable=unused-argument
        """
        Used to invoke the Service class "Destroy" before deleting it from database.

        The main purpuse of this hook is to call the "destroy" method of the object to delete and
        to clear related data of the object (environment data such as own storage, cache, etc...

        :note: If destroy raises an exception, the deletion is not taken.
        """
        from uds.core.util.permissions import clean  # pylint: disable=import-outside-toplevel

        to_delete: 'ServicePool' = kwargs['instance']

        logger.debug('Deleting Service Pool %s', to_delete)
        to_delete.get_environment().clean_related_data()

        # Clears related logs
        log.clear_logs(to_delete)

        # Clears related permissions
        clean(to_delete)

    # returns CSV header
    @staticmethod
    def get_cvs_header(sep: str = ',') -> str:
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
    def as_cvs(self, sep: str = ',') -> str:
        return sep.join(
            [
                self.name,
                str(self.initial_srvs),
                str(self.cache_l1_srvs),
                str(self.cache_l2_srvs),
                str(self.max_srvs),
                str(self.assigned_user_services().count()),
                str(self.cached_users_services().count()),
            ]
        )

    def __str__(self) -> str:
        return (
            f'Service pool {self.name}({self.id}) with {self.initial_srvs}'
            f' as initial, {self.cache_l1_srvs} as L1 cache, {self.cache_l2_srvs}'
            f' as L2 cache, {self.max_srvs} as max'
        )


# Connects a pre deletion signal to Authenticator
models.signals.pre_delete.connect(ServicePool.pre_delete, sender=ServicePool)
