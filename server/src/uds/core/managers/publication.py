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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import typing
import collections.abc
import logging
import datetime

from django.utils.translation import gettext as _
from django.db import transaction

from uds.core.util.serializer import serialize
from uds.core.jobs.delayed_task import DelayedTask
from uds.core.jobs.delayed_task_runner import DelayedTaskRunner
from uds.core.util.config import GlobalConfig
from uds.core.services.exceptions import PublishException
from uds.core.util.state import State
from uds.core.util import log

from uds.models import ServicePoolPublication, ServicePool
from uds.core.util.model import sql_datetime

from uds.core.util import singleton

if typing.TYPE_CHECKING:
    from uds.core import services

logger = logging.getLogger(__name__)

PUBTAG = 'pm-'


class PublicationOldMachinesCleaner(DelayedTask):
    """
    This delayed task is for removing a pending "removable" publication
    """

    def __init__(self, publicationId: int):
        super().__init__()
        self._id = publicationId

    def run(self) -> None:
        try:
            servicePoolPub: ServicePoolPublication = ServicePoolPublication.objects.get(
                pk=self._id
            )
            if servicePoolPub.state != State.REMOVABLE:
                logger.info('Already removed')

            now = sql_datetime()
            activePub: typing.Optional[
                ServicePoolPublication
            ] = servicePoolPub.deployed_service.activePublication()
            servicePoolPub.deployed_service.userServices.filter(in_use=True).update(
                in_use=False, state_date=now
            )
            servicePoolPub.deployed_service.mark_old_userservices_as_removable(activePub)
        except (
            Exception
        ):  #  nosec: Removed publication, no problem at all, just continue
            pass


class PublicationLauncher(DelayedTask):
    """
    This delayed task if for launching a new publication
    """

    def __init__(self, publication: ServicePoolPublication):
        super().__init__()
        self._publicationId = publication.id

    def run(self) -> None:
        logger.debug('Publishing')
        servicePoolPub: typing.Optional[ServicePoolPublication] = None
        try:
            now = sql_datetime()
            with transaction.atomic():
                servicePoolPub = ServicePoolPublication.objects.select_for_update().get(
                    pk=self._publicationId
                )
                if not servicePoolPub:
                    raise ServicePool.DoesNotExist()
                if (
                    servicePoolPub.state != State.LAUNCHING
                ):  # If not preparing (may has been canceled by user) just return
                    return
                servicePoolPub.state = State.PREPARING
                servicePoolPub.save()
            pi = servicePoolPub.get_intance()
            state = pi.publish()
            servicePool: ServicePool = servicePoolPub.deployed_service
            servicePool.current_pub_revision += 1
            servicePool.set_value(
                'toBeReplacedIn',
                serialize(
                    now
                    + datetime.timedelta(
                        hours=GlobalConfig.SESSION_EXPIRE_TIME.getInt(True)
                    )
                ),
            )
            servicePool.save()
            PublicationFinishChecker.state_updater(servicePoolPub, pi, state)
        except (
            ServicePoolPublication.DoesNotExist
        ):  # Deployed service publication has been removed from database, this is ok, just ignore it
            pass
        except Exception:
            logger.exception("Exception launching publication")
            try:
                if servicePoolPub:
                    servicePoolPub.state = State.ERROR
                    servicePoolPub.save()
            except Exception:
                logger.error('Error saving ERROR state for pool %s', servicePoolPub)


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
        publicationInstance: 'services.Publication',
        state: str,
    ) -> None:
        """
        Checks the value returned from invocation to publish or checkPublishingState, updating the servicePoolPub database object
        Return True if it has to continue checking, False if finished
        """
        try:
            prevState: str = publication.state
            checkLater: bool = False
            if State.is_finished(state):
                # Now we mark, if it exists, the previous usable publication as "Removable"
                if State.is_preparing(prevState):
                    old: ServicePoolPublication
                    for old in publication.deployed_service.publications.filter(
                        state=State.USABLE
                    ):
                        old.set_state(State.REMOVABLE)

                        osm = publication.deployed_service.osmanager
                        # If os manager says "machine is persistent", do not tray to delete "previous version" assigned machines
                        doPublicationCleanup = (
                            True
                            if osm is None
                            else not osm.get_instance().is_persistent()
                        )

                        if doPublicationCleanup:
                            pc = PublicationOldMachinesCleaner(old.id)
                            pc.register(
                                GlobalConfig.SESSION_EXPIRE_TIME.getInt(True) * 3600,
                                'pclean-' + str(old.id),
                                True,
                            )
                            publication.deployed_service.mark_old_userservices_as_removable(
                                publication
                            )
                        else:  # Remove only cache services, not assigned
                            publication.deployed_service.mark_old_userservices_as_removable(
                                publication, True
                            )

                    publication.set_state(State.USABLE)
                elif State.is_removing(prevState):
                    publication.set_state(State.REMOVED)
                else:  # State is canceling
                    publication.set_state(State.CANCELED)
                # Mark all previous publications deployed services as removables
                # and make this usable
                publicationInstance.finish()
                publication.updateData(publicationInstance)
            elif State.is_errored(state):
                publication.updateData(publicationInstance)
                publication.set_state(State.ERROR)
            else:
                checkLater = True  # The task is running
                publication.updateData(publicationInstance)

            if checkLater:
                PublicationFinishChecker.check_later(publication, publicationInstance)
        except Exception:
            logger.exception('At checkAndUpdate for publication')
            PublicationFinishChecker.check_later(publication, publicationInstance)

    @staticmethod
    def check_later(
        publication: ServicePoolPublication, publicationInstance: 'services.Publication'
    ) -> None:
        """
        Inserts a task in the delayedTaskRunner so we can check the state of this publication
        @param dps: Database object for ServicePoolPublication
        @param pi: Instance of Publication manager for the object
        """
        DelayedTaskRunner.runner().insert(
            PublicationFinishChecker(publication),
            publicationInstance.suggested_delay,
            PUBTAG + str(publication.id),
        )

    def run(self) -> None:
        logger.debug('Checking publication finished %s', self._publishId)
        try:
            publication: ServicePoolPublication = ServicePoolPublication.objects.get(
                pk=self._publishId
            )
            if publication.state != self._state:
                logger.debug('Task overrided by another task (state of item changed)')
            else:
                publicationInstance = publication.get_intance()
                logger.debug(
                    "publication instance class: %s", publicationInstance.__class__
                )
                try:
                    state = publicationInstance.check_state()
                except Exception:
                    state = State.ERROR
                PublicationFinishChecker.state_updater(
                    publication, publicationInstance, state
                )
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

    def __init__(self):
        pass

    @staticmethod
    def manager() -> 'PublicationManager':
        """
        Returns the singleton to this manager
        """
        return (
            PublicationManager()
        )  # Singleton pattern will return always the same instance

    def publish(
        self, servicePool: ServicePool, changeLog: typing.Optional[str] = None
    ):  # pylint: disable=no-self-use
        """
        Initiates the publication of a service pool, or raises an exception if this cannot be done
        :param servicePool: Service pool object (db object)
        :param changeLog: if not None, store change log string on "change log" table
        """
        if servicePool.publications.filter(state__in=State.PUBLISH_STATES).count() > 0:
            raise PublishException(
                _(
                    'Already publishing. Wait for previous publication to finish and try again'
                )
            )

        if servicePool.is_in_maintenance():
            raise PublishException(
                _('Service is in maintenance mode and new publications are not allowed')
            )

        publication: typing.Optional[ServicePoolPublication] = None
        try:
            now = sql_datetime()
            publication = servicePool.publications.create(
                state=State.LAUNCHING,
                state_date=now,
                publish_date=now,
                revision=servicePool.current_pub_revision,
            )
            if changeLog:
                servicePool.changelog.create(
                    revision=servicePool.current_pub_revision, log=changeLog, stamp=now
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

    def cancel(
        self, publication: ServicePoolPublication
    ):  # pylint: disable=no-self-use
        """
        Invoked to cancel a publication.
        Double invokation (i.e. invokation over a "cancelling" item) will lead to a "forced" cancellation (unclean)
        :param servicePoolPub: Service pool publication (db object for a publication)
        """
        publication = ServicePoolPublication.objects.get(
            pk=publication.id
        )  # Reloads publication from db
        if publication.state not in State.PUBLISH_STATES:
            if publication.state == State.CANCELING:  # Double cancel
                logger.info('Double cancel invoked for a publication')
                log.log(
                    publication.deployed_service,
                    log.LogLevel.WARNING,
                    'Forced cancel on publication, you must check uncleaned resources manually',
                    log.LogSource.ADMIN,
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
            pubInstance = publication.get_intance()
            state = pubInstance.cancel()
            publication.set_state(State.CANCELING)
            PublicationFinishChecker.state_updater(
                publication, pubInstance, state
            )
            return publication
        except Exception as e:
            raise PublishException(str(e)) from e

    def unpublish(
        self, servicePoolPub: ServicePoolPublication
    ):  # pylint: disable=no-self-use
        """
        Unpublishes an active (usable) or removable publication
        :param servicePoolPub: Publication to unpublish
        """
        if (
            State.is_usable(servicePoolPub.state) is False
            and State.is_removable(servicePoolPub.state) is False
        ):
            raise PublishException(_('Can\'t unpublish non usable publication'))
        if servicePoolPub.userServices.exclude(state__in=State.INFO_STATES).count() > 0:
            raise PublishException(
                _('Can\'t unpublish publications with services in process')
            )
        try:
            pubInstance = servicePoolPub.get_intance()
            state = pubInstance.destroy()
            servicePoolPub.set_state(State.REMOVING)
            PublicationFinishChecker.state_updater(
                servicePoolPub, pubInstance, state
            )
        except Exception as e:
            raise PublishException(str(e)) from e
