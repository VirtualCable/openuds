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
import typing
import logging
import datetime

from django.utils.translation import gettext as _
from django.db import transaction

from uds.core.util.serializer import serialize
from uds.core.jobs.delayed_task import DelayedTask
from uds.core.jobs.delayed_task_runner import DelayedTaskRunner
from uds.core.util.config import GlobalConfig
from uds.core.services.exceptions import PublishException
from uds.core import types
from uds.core.types.states import State
from uds.core.util import log

from uds.models import ServicePoolPublication, ServicePool
from uds.core.util.model import sql_now

from uds.core.util import singleton

if typing.TYPE_CHECKING:
    from uds.core import services

logger = logging.getLogger(__name__)

PUBTAG = 'pm-'


class PublicationOldMachinesCleaner(DelayedTask):
    """
    This delayed task is for removing a pending "removable" publication
    """

    def __init__(self, publication_id: int):
        super().__init__()
        self._id = publication_id

    def run(self) -> None:
        try:
            servicepool_publication: ServicePoolPublication = ServicePoolPublication.objects.get(pk=self._id)
            if servicepool_publication.state != State.REMOVABLE:
                logger.info('Already removed')

            now = sql_now()
            current_publication: typing.Optional[ServicePoolPublication] = (
                servicepool_publication.deployed_service.active_publication()
            )

            if current_publication:
                servicepool_publication.deployed_service.userServices.filter(in_use=True).exclude(
                    publication=current_publication
                ).update(in_use=False, state_date=now)
                servicepool_publication.deployed_service.mark_old_userservices_as_removable(current_publication)
        except Exception:  #  nosec: Removed publication, no problem at all, just continue
            pass


class PublicationLauncher(DelayedTask):
    """
    This delayed task if for launching a new publication
    """

    def __init__(self, publication: ServicePoolPublication):
        super().__init__()
        self._publication_id = publication.id

    def run(self) -> None:
        logger.debug('Publishing')
        servicepool_publication: typing.Optional[ServicePoolPublication] = None
        try:
            now = sql_now()
            with transaction.atomic():
                servicepool_publication = ServicePoolPublication.objects.select_for_update().get(
                    pk=self._publication_id
                )
                if not servicepool_publication:
                    raise ServicePool.DoesNotExist()
                if (
                    servicepool_publication.state != State.LAUNCHING
                ):  # If not preparing (may has been canceled by user) just return
                    return
                servicepool_publication.state = State.PREPARING
                servicepool_publication.save()
            pi = servicepool_publication.get_instance()
            state = pi.publish()
            servicepool: ServicePool = servicepool_publication.deployed_service
            servicepool.current_pub_revision += 1
            servicepool.set_value(
                'toBeReplacedIn',
                serialize(now + datetime.timedelta(hours=GlobalConfig.SESSION_EXPIRE_TIME.as_int(True))),
            )
            servicepool.save()
            PublicationFinishChecker.state_updater(servicepool_publication, pi, state)
        except (
            ServicePoolPublication.DoesNotExist
        ):  # Deployed service publication has been removed from database, this is ok, just ignore it
            pass
        except Exception:
            logger.exception("Exception launching publication")
            try:
                if servicepool_publication:
                    servicepool_publication.state = State.ERROR
                    servicepool_publication.save()
            except Exception:
                logger.error('Error saving ERROR state for pool %s', servicepool_publication)


# Delayed Task that checks if a publication is done
class PublicationFinishChecker(DelayedTask):
    """
    This delayed task is responsible of checking if a publication is finished
    """

    def __init__(self, publication: ServicePoolPublication) -> None:
        super().__init__()
        self._publishId = publication.id
        self._state = publication.state

    @staticmethod
    def state_updater(
        publication: ServicePoolPublication,
        publication_instance: 'services.Publication',
        exec_result: types.states.TaskState,
    ) -> None:
        """
        Checks the value returned from invocation to publish or check_publishing_state, updating the service_pool_pub database object
        Return True if it has to continue checking, False if finished
        """
        try:
            publication_state = types.states.State.from_str(publication.state)
            check_later: bool = False
            if exec_result.is_finished():
                # Now we mark, if it exists, the previous usable publication as "Removable"
                if publication_state.is_preparing():
                    old: ServicePoolPublication
                    for old in publication.deployed_service.publications.filter(state=State.USABLE):
                        old.set_state(State.REMOVABLE)

                        osm = publication.deployed_service.osmanager
                        # If os manager says "machine is persistent", do not tray to delete "previous version" assigned machines
                        if osm is None or osm.get_instance().is_persistent() is False:
                            pc = PublicationOldMachinesCleaner(old.id)
                            pc.register(
                                GlobalConfig.SESSION_EXPIRE_TIME.as_int(True) * 3600,
                                'pclean-' + str(old.id),
                                True,
                            )
                            publication.deployed_service.mark_old_userservices_as_removable(publication)
                        else:  # Remove only cache services, not assigned
                            publication.deployed_service.mark_old_userservices_as_removable(publication, True)

                    publication.set_state(State.USABLE)
                elif publication_state.is_removing():
                    publication.set_state(State.REMOVED)
                else:  # State is canceling
                    publication.set_state(State.CANCELED)
                # Mark all previous publications deployed services as removables
                # and make this usable
                publication_instance.finish()
                publication.update_data(publication_instance)
            elif exec_result.is_errored():
                publication.update_data(publication_instance)
                publication.set_state(State.ERROR)
            else:
                check_later = True  # The task is running
                publication.update_data(publication_instance)

            if check_later:
                PublicationFinishChecker.check_later(publication)
        except Exception:
            logger.exception('At check_and_update for publication')
            PublicationFinishChecker.check_later(publication)

    @staticmethod
    def check_later(publication: ServicePoolPublication) -> None:
        """
        Inserts a task in the delayed_task_runner so we can check the state of this publication
        @param dps: Database object for ServicePoolPublication
        @param pi: Instance of Publication manager for the object
        """
        DelayedTaskRunner.runner().insert(
            PublicationFinishChecker(publication),
            publication.get_instance().suggested_delay,
            PUBTAG + str(publication.id),
        )

    def run(self) -> None:
        logger.debug('Checking publication finished %s', self._publishId)
        try:
            publication: ServicePoolPublication = ServicePoolPublication.objects.get(pk=self._publishId)
            if publication.state != self._state:
                logger.debug('Task overrided by another task (state of item changed)')
            else:
                publication_instance = publication.get_instance()
                logger.debug("publication instance class: %s", publication_instance.__class__)
                try:
                    state = publication_instance.check_state()
                except Exception:
                    state = types.states.TaskState.ERROR
                PublicationFinishChecker.state_updater(publication, publication_instance, state)
        except Exception as e:
            logger.debug(
                'Deployed service not found (erased from database) %s : %s',
                e.__class__,
                e,
            )


class PublicationManager(metaclass=singleton.Singleton):
    """
    Manager responsible of controlling publications
    """

    def __init__(self) -> None:
        pass

    @staticmethod
    def manager() -> 'PublicationManager':
        """
        Returns the singleton to this manager
        """
        return PublicationManager()  # Singleton pattern will return always the same instance

    def publish(self, servicepool: ServicePool, changelog: typing.Optional[str] = None) -> None:
        """
        Initiates the publication of a service pool, or raises an exception if this cannot be done

        Args:
            servicepool: Service pool to publish
            changelog: Optional changelog to store
        """
        if servicepool.publications.filter(state__in=State.PUBLISH_STATES).count() > 0:
            raise PublishException(
                _('Already publishing. Wait for previous publication to finish and try again')
            )

        if servicepool.is_in_maintenance():
            raise PublishException(_('Service is in maintenance mode and new publications are not allowed'))

        publication: typing.Optional[ServicePoolPublication] = None
        try:
            now = sql_now()
            publication = servicepool.publications.create(
                state=State.LAUNCHING,
                state_date=now,
                publish_date=now,
                revision=servicepool.current_pub_revision,
            )
            if changelog:
                servicepool.changelog.create(
                    revision=servicepool.current_pub_revision, log=changelog, stamp=now
                )
            if publication:
                DelayedTaskRunner.runner().insert(
                    PublicationLauncher(publication), 4, PUBTAG + str(publication.id)
                )
        except Exception as e:
            logger.debug('Caught exception at publish: %s', e)
            if publication is not None:
                try:
                    publication.delete()
                except Exception:
                    logger.info('Could not delete %s', publication)
            raise PublishException(str(e)) from e

    def cancel(self, publication: ServicePoolPublication) -> ServicePoolPublication:
        """
        Invoked to cancel a publication.
        Double invokation (i.e. invokation over a "cancelling" item) will lead to a "forced" cancellation (unclean)

        Args:
            publication: Publication to cancel

        """
        publication = ServicePoolPublication.objects.get(pk=publication.id)  # Reloads publication from db
        if publication.state not in State.PUBLISH_STATES:
            if publication.state == State.CANCELING:  # Double cancel
                logger.info('Double cancel invoked for a publication')
                log.log(
                    publication.deployed_service,
                    types.log.LogLevel.WARNING,
                    'Forced cancel on publication, you must check uncleaned resources manually',
                    types.log.LogSource.ADMIN,
                )
                publication.set_state(State.CANCELED)
                publication.save()
                return publication
            raise PublishException(_('Can\'t cancel non running publication'))

        if publication.state == State.LAUNCHING:
            publication.state = State.CANCELED
            publication.deployed_service.set_value('toBeReplacedIn', None)
            publication.save()
            return publication

        try:
            pub_instance = publication.get_instance()
            state = pub_instance.cancel()
            publication.set_state(State.CANCELING)
            PublicationFinishChecker.state_updater(publication, pub_instance, state)
            return publication
        except Exception as e:
            raise PublishException(str(e)) from e

    def unpublish(self, servicepool_publication: ServicePoolPublication) -> None:
        """
        Unpublishes an active (usable) or removable publication

        Args:
            servicepool_publication: Publication to unpublish

        """
        if (
            State.from_str(servicepool_publication.state).is_usable() is False
            and State.from_str(servicepool_publication.state).is_removable() is False
        ):
            raise PublishException(_('Can\'t unpublish non usable publication'))
        if servicepool_publication.userServices.exclude(state__in=State.INFO_STATES).count() > 0:
            raise PublishException(_('Can\'t unpublish publications with services in process'))
        try:
            publication_instance = servicepool_publication.get_instance()
            state = publication_instance.destroy()
            servicepool_publication.set_state(State.REMOVING)
            PublicationFinishChecker.state_updater(servicepool_publication, publication_instance, state)
        except Exception as e:
            raise PublishException(str(e)) from e
