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
from uds.models import DeployedServicePublication, getSqlDatetime, State
import logging

logger = logging.getLogger(__name__)

PUBTAG = 'pm-'


class PublicationOldMachinesCleaner(DelayedTask):
    def __init__(self, publicationId):
        super(PublicationOldMachinesCleaner, self).__init__()
        self._id = publicationId

    def run(self):
        try:
            dsp = DeployedServicePublication.objects.get(pk=self._id)
            if (dsp.state != State.REMOVABLE):
                logger.info('Already removed')

            now = getSqlDatetime()
            activePub = dsp.deployed_service.activePublication()
            dsp.deployed_service.userServices.filter(in_use=True).update(in_use=False, state_date=now)
            dsp.deployed_service.markOldUserServicesAsRemovables(activePub)
        except:
            logger.info("Machine removal for {0} not executed because publication is already removed")
            # Removed provider, no problem at all, no update is done
            pass


class PublicationLauncher(DelayedTask):
    def __init__(self, publish):
        super(PublicationLauncher, self).__init__()
        self._publishId = publish.id

    def run(self):
        logger.debug('Publishing')
        try:
            with transaction.atomic():
                dsp = DeployedServicePublication.objects.select_for_update().get(pk=self._publishId)
                if dsp.state != State.LAUNCHING:  # If not preparing (may has been canceled by user) just return
                    return
                dsp.state = State.PREPARING
                dsp.save()
            pi = dsp.getInstance()
            state = pi.publish()
            deployedService = dsp.deployed_service
            deployedService.current_pub_revision += 1
            deployedService.save()
            PublicationFinishChecker.checkAndUpdateState(dsp, pi, state)
        except Exception:
            logger.exception("Exception launching publication")
            dsp.state = State.ERROR
            dsp.save()


# Delayed Task that checks if a publication is done
class PublicationFinishChecker(DelayedTask):
    def __init__(self, publish):
        super(PublicationFinishChecker, self).__init__()
        self._publishId = publish.id
        self._state = publish.state

    @staticmethod
    def checkAndUpdateState(dsp, pi, state):
        '''
        Checks the value returned from invocation to publish or checkPublishingState, updating the dsp database object
        Return True if it has to continue checking, False if finished
        '''
        try:
            prevState = dsp.state
            checkLater = False
            if  State.isFinished(state):
                # Now we mark, if it exists, the previous usable publication as "Removable"
                if State.isPreparing(prevState):
                    for old in dsp.deployed_service.publications.filter(state=State.USABLE):
                        old.state = State.REMOVABLE
                        old.save()
                        pc = PublicationOldMachinesCleaner(old.id)
                        pc.register(GlobalConfig.SESSION_EXPIRE_TIME.getInt(True) * 3600, 'pclean-' + str(old.id), True)

                    dsp.setState(State.USABLE)
                    dsp.deployed_service.markOldUserServicesAsRemovables(dsp)
                elif State.isRemoving(prevState):
                    dsp.setState(State.REMOVED)
                else:  # State is canceling
                    dsp.setState(State.CANCELED)
                # Mark all previous publications deployed services as removables
                # and make this usable
                pi.finish()
                dsp.updateData(pi)
            elif State.isErrored(state):
                dsp.updateData(pi)
                dsp.state = State.ERROR
            else:
                checkLater = True  # The task is running
                dsp.updateData(pi)

            dsp.save()
            if checkLater:
                PublicationFinishChecker.checkLater(dsp, pi)
        except:
            logger.exception('At checkAndUpdate for publication')
            PublicationFinishChecker.checkLater(dsp, pi)

    @staticmethod
    def checkLater(dsp, pi):
        '''
        Inserts a task in the delayedTaskRunner so we can check the state of this publication
        @param dps: Database object for DeployedServicePublication
        @param pi: Instance of Publication manager for the object
        '''
        DelayedTaskRunner.runner().insert(PublicationFinishChecker(dsp), pi.suggestedTime, PUBTAG + str(dsp.id))

    def run(self):
        logger.debug('Checking publication finished {0}'.format(self._publishId))
        try:
            dsp = DeployedServicePublication.objects.get(pk=self._publishId)
            if dsp.state != self._state:
                logger.debug('Task overrided by another task (state of item changed)')
            else:
                pi = dsp.getInstance()
                logger.debug("publication instance class: {0}".format(pi.__class__))
                state = pi.checkState()
                PublicationFinishChecker.checkAndUpdateState(dsp, pi, state)
        except Exception, e:
            logger.debug('Deployed service not found (erased from database) {0} : {1}'.format(e.__class__, e))


class PublicationManager(object):
    _manager = None

    def __init__(self):
        pass

    @staticmethod
    def manager():
        if PublicationManager._manager == None:
            PublicationManager._manager = PublicationManager()
        return PublicationManager._manager

    def publish(self, deployedService):
        if deployedService.publications.filter(state__in=State.PUBLISH_STATES).count() > 0:
            raise PublishException(_('Already publishing. Wait for previous publication to finish and try again'))
        try:
            now = getSqlDatetime()
            dsp = deployedService.publications.create(state=State.LAUNCHING, state_date=now, publish_date=now, revision=deployedService.current_pub_revision)
            DelayedTaskRunner.runner().insert(PublicationLauncher(dsp), 4, PUBTAG + str(dsp.id))
        except Exception as e:
            logger.debug('Caught exception at publish: {0}'.format(e))
            raise PublishException(str(e))

    def cancel(self, dsp):
        dsp = DeployedServicePublication.objects.get(pk=dsp.id)
        if dsp.state not in State.PUBLISH_STATES:
            raise PublishException(_('Can\'t cancel non running publication'))

        if dsp.state == State.LAUNCHING:
            dsp.state = State.CANCELED
            dsp.save()
            return dsp

        try:
            pi = dsp.getInstance()
            state = pi.cancel()
            dsp.setState(State.CANCELING)
            PublicationFinishChecker.checkAndUpdateState(dsp, pi, state)
            return dsp
        except Exception, e:
            raise PublishException(str(e))

    def unpublish(self, dsp):
        if State.isUsable(dsp.state) == False and State.isRemovable(dsp.state) == False:
            raise PublishException(_('Can\'t unpublish non usable publication'))
        # TODO: Call assignation manager to remove removable items
        if dsp.userServices.exclude(state__in=State.INFO_STATES).count() > 0:
            raise PublishException(_('Can\'t unpublish publications with services in process'))
        try:
            pi = dsp.getInstance()
            state = pi.destroy()
            dsp.setState(State.REMOVING)
            PublicationFinishChecker.checkAndUpdateState(dsp, pi, state)
        except Exception, e:
            raise PublishException(str(e))
