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
from __future__ import unicode_literals

from django.utils.translation import ugettext as _
from django.db import transaction
from uds.core.jobs.DelayedTask import DelayedTask
from uds.core.jobs.DelayedTaskRunner import DelayedTaskRunner
from uds.core.util.Config import GlobalConfig
from uds.core.services.Exceptions import PublishException
from uds.models import DeployedServicePublication, getSqlDatetime
from uds.core.util.State import State
from uds.core.util import log
import logging
import datetime
import pickle

logger = logging.getLogger(__name__)

PUBTAG = 'pm-'


class PublicationOldMachinesCleaner(DelayedTask):
    '''
    This delayed task is for removing a pending "removable" publication
    '''

    def __init__(self, publicationId):
        super(PublicationOldMachinesCleaner, self).__init__()
        self._id = publicationId

    def run(self):
        try:
            servicePoolPub = DeployedServicePublication.objects.get(pk=self._id)
            if servicePoolPub.state != State.REMOVABLE:
                logger.info('Already removed')

            now = getSqlDatetime()
            activePub = servicePoolPub.deployed_service.activePublication()
            servicePoolPub.deployed_service.userServices.filter(in_use=True).update(in_use=False, state_date=now)
            servicePoolPub.deployed_service.markOldUserServicesAsRemovables(activePub)
        except Exception:
            pass
            # logger.exception('Trace (treated exception, not fault)')
            # Removed publication, no problem at all, no update is done


class PublicationLauncher(DelayedTask):
    '''
    This delayed task if for launching a new publication
    '''

    def __init__(self, publish):
        super(PublicationLauncher, self).__init__()
        self._publishId = publish.id

    def run(self):
        logger.debug('Publishing')
        try:
            with transaction.atomic():
                servicePoolPub = DeployedServicePublication.objects.select_for_update().get(pk=self._publishId)
                if servicePoolPub.state != State.LAUNCHING:  # If not preparing (may has been canceled by user) just return
                    return
                servicePoolPub.state = State.PREPARING
                servicePoolPub.save()
            pi = servicePoolPub.getInstance()
            state = pi.publish()
            deployedService = servicePoolPub.deployed_service
            deployedService.current_pub_revision += 1
            deployedService.storeValue('toBeReplacedIn', pickle.dumps(datetime.datetime.now() + datetime.timedelta(hours=GlobalConfig.SESSION_EXPIRE_TIME.getInt(True))))
            deployedService.save()
            PublicationFinishChecker.checkAndUpdateState(servicePoolPub, pi, state)
        except Exception:
            logger.exception("Exception launching publication")
            servicePoolPub.state = State.ERROR
            servicePoolPub.save()


# Delayed Task that checks if a publication is done
class PublicationFinishChecker(DelayedTask):
    '''
    This delayed task is responsible of checking if a publication is finished
    '''

    def __init__(self, servicePoolPub):
        super(PublicationFinishChecker, self).__init__()
        self._publishId = servicePoolPub.id
        self._state = servicePoolPub.state

    @staticmethod
    def checkAndUpdateState(servicePoolPub, pi, state):
        '''
        Checks the value returned from invocation to publish or checkPublishingState, updating the servicePoolPub database object
        Return True if it has to continue checking, False if finished
        '''
        try:
            prevState = servicePoolPub.state
            checkLater = False
            if State.isFinished(state):
                # Now we mark, if it exists, the previous usable publication as "Removable"
                if State.isPreparing(prevState):
                    for old in servicePoolPub.deployed_service.publications.filter(state=State.USABLE):
                        old.state = State.REMOVABLE
                        old.save()

                        osm = servicePoolPub.deployed_service.osmanager
                        # If os manager says "machine is persistent", do not tray to delete "previous version" assigned machines
                        doPublicationCleanup = True if osm is None else not osm.getInstance().isPersistent()

                        if doPublicationCleanup:
                            pc = PublicationOldMachinesCleaner(old.id)
                            pc.register(GlobalConfig.SESSION_EXPIRE_TIME.getInt(True) * 3600, 'pclean-' + str(old.id), True)

                    servicePoolPub.setState(State.USABLE)
                    servicePoolPub.deployed_service.markOldUserServicesAsRemovables(servicePoolPub)
                elif State.isRemoving(prevState):
                    servicePoolPub.setState(State.REMOVED)
                else:  # State is canceling
                    servicePoolPub.setState(State.CANCELED)
                # Mark all previous publications deployed services as removables
                # and make this usable
                pi.finish()
                servicePoolPub.updateData(pi)
            elif State.isErrored(state):
                servicePoolPub.updateData(pi)
                servicePoolPub.state = State.ERROR
            else:
                checkLater = True  # The task is running
                servicePoolPub.updateData(pi)

            servicePoolPub.save()
            if checkLater:
                PublicationFinishChecker.checkLater(servicePoolPub, pi)
        except Exception:
            logger.exception('At checkAndUpdate for publication')
            PublicationFinishChecker.checkLater(servicePoolPub, pi)

    @staticmethod
    def checkLater(servicePoolPub, pi):
        '''
        Inserts a task in the delayedTaskRunner so we can check the state of this publication
        @param dps: Database object for DeployedServicePublication
        @param pi: Instance of Publication manager for the object
        '''
        DelayedTaskRunner.runner().insert(PublicationFinishChecker(servicePoolPub), pi.suggestedTime, PUBTAG + str(servicePoolPub.id))

    def run(self):
        logger.debug('Checking publication finished {0}'.format(self._publishId))
        try:
            servicePoolPub = DeployedServicePublication.objects.get(pk=self._publishId)
            if servicePoolPub.state != self._state:
                logger.debug('Task overrided by another task (state of item changed)')
            else:
                pi = servicePoolPub.getInstance()
                logger.debug("publication instance class: {0}".format(pi.__class__))
                state = pi.checkState()
                PublicationFinishChecker.checkAndUpdateState(servicePoolPub, pi, state)
        except Exception, e:
            logger.debug('Deployed service not found (erased from database) {0} : {1}'.format(e.__class__, e))


class PublicationManager(object):
    '''
    Manager responsible of controlling publications
    '''
    _manager = None

    def __init__(self):
        pass

    @staticmethod
    def manager():
        '''
        Returns the singleton to this manager
        '''
        if PublicationManager._manager is None:
            PublicationManager._manager = PublicationManager()
        return PublicationManager._manager

    def publish(self, servicePool, changeLog=None):  # pylint: disable=no-self-use
        '''
        Initiates the publication of a service pool, or raises an exception if this cannot be done
        :param servicePool: Service pool object (db object)
        '''
        if servicePool.publications.filter(state__in=State.PUBLISH_STATES).count() > 0:
            raise PublishException(_('Already publishing. Wait for previous publication to finish and try again'))

        if servicePool.isInMaintenance():
            raise PublishException(_('Service is in maintenance mode and new publications are not allowed'))

        try:
            now = getSqlDatetime()
            dsp = None
            dsp = servicePool.publications.create(state=State.LAUNCHING, state_date=now, publish_date=now, revision=servicePool.current_pub_revision)
            if changeLog:
                servicePool.changelog.create(revision=servicePool.current_pub_revision, log=changeLog, stamp=now)
            DelayedTaskRunner.runner().insert(PublicationLauncher(dsp), 4, PUBTAG + str(dsp.id))
        except Exception as e:
            logger.debug('Caught exception at publish: {0}'.format(e))
            if dsp is not None:
                try:
                    dsp.delete()
                except Exception:
                    logger.info('Could not delete {}'.format(dsp))
            raise PublishException(str(e))

    def cancel(self, servicePoolPub):  # pylint: disable=no-self-use
        '''
        Invoked to cancel a publication.
        Double invokation (i.e. invokation over a "cancelling" item) will lead to a "forced" cancellation (unclean)
        :param servicePoolPub: Service pool publication (db object for a publication)
        '''
        servicePoolPub = DeployedServicePublication.objects.get(pk=servicePoolPub.id)
        if servicePoolPub.state not in State.PUBLISH_STATES:
            if servicePoolPub.state == State.CANCELING:  # Double cancel
                logger.info('Double cancel invoked for a publication')
                log.doLog(servicePoolPub.deployed_service, log.WARN, 'Forced cancel on publication, you must check uncleaned resources manually', log.ADMIN)
                servicePoolPub.setState(State.CANCELED)
                servicePoolPub.save()
                return
            else:
                raise PublishException(_('Can\'t cancel non running publication'))

        if servicePoolPub.state == State.LAUNCHING:
            servicePoolPub.state = State.CANCELED
            servicePoolPub.save()
            return servicePoolPub

        try:
            pubInstance = servicePoolPub.getInstance()
            state = pubInstance.cancel()
            servicePoolPub.setState(State.CANCELING)
            PublicationFinishChecker.checkAndUpdateState(servicePoolPub, pubInstance, state)
            return servicePoolPub
        except Exception, e:
            raise PublishException(str(e))

    def unpublish(self, servicePoolPub):  # pylint: disable=no-self-use
        '''
        Unpublishes an active (usable) or removable publication
        :param servicePoolPub: Publication to unpublish
        '''
        if State.isUsable(servicePoolPub.state) is False and State.isRemovable(servicePoolPub.state) is False:
            raise PublishException(_('Can\'t unpublish non usable publication')
                                   )
        if servicePoolPub.userServices.exclude(state__in=State.INFO_STATES).count() > 0:
            raise PublishException(_('Can\'t unpublish publications with services in process'))
        try:
            pubInstance = servicePoolPub.getInstance()
            state = pubInstance.destroy()
            servicePoolPub.setState(State.REMOVING)
            PublicationFinishChecker.checkAndUpdateState(servicePoolPub, pubInstance, state)
        except Exception, e:
            raise PublishException(str(e))
