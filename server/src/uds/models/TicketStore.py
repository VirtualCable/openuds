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

from uds.models.UUIDModel import UUIDModel
from uds.models.Util import getSqlDatetime

import datetime
import pickle
import string
import random
import logging

logger = logging.getLogger(__name__)

__updated__ = '2015-04-27'


class TicketStore(UUIDModel):
    '''
    Image storing on DB model
    This is intended for small images (i will limit them to 128x128), so storing at db is fine
    '''
    DEFAULT_VALIDITY = 60
    MAX_VALIDITY = 60 * 60 * 12
    # Cleanup will purge all elements that have been created MAX_VALIDITY ago

    stamp = models.DateTimeField()  # Date creation or validation of this entry
    validity = models.IntegerField(default=60)  # Duration allowed for this ticket to be valid, in seconds

    data = models.BinaryField()  # Associated ticket data
    validator = models.BinaryField(null=True, blank=True, default=None)  # Associated validator for this ticket

    class InvalidTicket(Exception):
        pass

    class Meta:
        '''
        Meta class to declare the name of the table at database
        '''
        db_table = 'uds_tickets'
        app_label = 'uds'

    def genUuid(self):
        return TicketStore.generateUuid()

    @staticmethod
    def generateUuid():
        # more secure is this:
        # ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(40))
        return ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(40))

    @staticmethod
    def create(data, validator=None, validity=DEFAULT_VALIDITY):
        if validator is not None:
            validator = pickle.dumps(validator)
        return TicketStore.objects.create(stamp=getSqlDatetime(), data=pickle.dumps(data), validator=validator, validity=validity).uuid

    @staticmethod
    def store(uuid, data, validator=None, validity=DEFAULT_VALIDITY):
        if validator is not None:
            validator = pickle.dumps(validator)
        try:
            t = TicketStore.objects.get(uuid=uuid)
            t.data = pickle.dumps(data)
            t.stamp = getSqlDatetime()
            t.validity = validity
            t.save()
        except TicketStore.DoesNotExist:
            t = TicketStore.objects.create(uuid=uuid, stamp=getSqlDatetime(), data=pickle.dumps(data), validator=validator, validity=validity)

    @staticmethod
    def get(uuid, invalidate=True):
        try:
            t = TicketStore.objects.get(uuid=uuid)
            validity = datetime.timedelta(seconds=t.validity)
            now = getSqlDatetime()

            logger.debug('Ticket validity: {} {}'.format(t.stamp + validity, now))
            if t.stamp + validity < now:
                raise TicketStore.InvalidTicket('Not valid anymore')

            data = pickle.loads(t.data)

            # If has validator, execute it
            if t.validator is not None:
                validator = pickle.loads(t.validator)

                if validator(data) is False:
                    raise TicketStore.InvalidTicket('Validation failed')

            if invalidate is True:
                t.stamp = now - validity - datetime.timedelta(seconds=1)
                t.save()

            return data
        except TicketStore.DoesNotExist:
            raise TicketStore.InvalidTicket('Does not exists')

    @staticmethod
    def revalidate(uuid, validity=None):
        try:
            t = TicketStore.objects.get(uuid=uuid)
            t.stamp = getSqlDatetime()
            if validity is not None:
                t.validity = validity
            t.save()
        except TicketStore.DoesNotExist:
            raise Exception('Does not exists')

    @staticmethod
    def cleanup():
        now = getSqlDatetime()
        cleanSince = now - datetime.timedelta(seconds=TicketStore.MAX_VALIDITY)
        number = TicketStore.objects.filter(stamp__lt=cleanSince).delete()
        logger.debug('Cleaned {} tickets'.format(number))

    def __unicode__(self):
        if self.validator is not None:
            validator = pickle.loads(self.validator)
        else:
            validator = None

        return 'Ticket id: {}, Stamp: {}, Validity: {}, Validator: {}, Data: {}'.format(self.uuid, self.stamp, self.validity, validator, pickle.loads(self.data))
