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
'''
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
'''
import datetime
import pickle
import logging
import typing

from django.db import models

from uds.core.managers import cryptoManager

from .uuid_model import UUIDModel
from .util import getSqlDatetime


logger = logging.getLogger(__name__)

ValidatorType = typing.Callable[[typing.Any], bool]


class TicketStore(UUIDModel):
    """
    Tickets storing on DB
    """
    DEFAULT_VALIDITY = 60
    MAX_VALIDITY = 60 * 60 * 12
    # Cleanup will purge all elements that have been created MAX_VALIDITY ago

    owner = models.CharField(null=True, blank=True, default=None, max_length=8)
    stamp = models.DateTimeField()  # Date creation or validation of this entry
    validity = models.IntegerField(default=60)  # Duration allowed for this ticket to be valid, in seconds

    data = models.BinaryField()  # Associated ticket data
    validator = models.BinaryField(null=True, blank=True, default=None)  # Associated validator for this ticket

    class InvalidTicket(Exception):
        pass

    class Meta:
        """
        Meta class to declare the name of the table at database
        """
        db_table = 'uds_tickets'
        app_label = 'uds'

    def genUuid(self) -> str:
        return TicketStore.generateUuid()

    @staticmethod
    def generateUuid() -> str:
        return cryptoManager().randomString(40)

    @staticmethod
    def create(
            data: typing.Any,
            validatorFnc: typing.Optional[ValidatorType] = None,
            validity: int = DEFAULT_VALIDITY,
            owner: typing.Optional[str]=None,
            secure: bool = False
        ) -> str:
        """
        validity is in seconds
        """
        validator = pickle.dumps(validatorFnc) if validatorFnc else None
        data = pickle.dumps(data)
        if secure:
            pass

        return TicketStore.objects.create(stamp=getSqlDatetime(), data=data, validator=validator, validity=validity, owner=owner).uuid

    @staticmethod
    def store(
            uuid: str,
            data: str,
            validatorFnc: typing.Optional[ValidatorType] = None,
            validity: int = DEFAULT_VALIDITY,
            owner: typing.Optional[str] = owner,
            secure: bool = False
        ) -> None:
        """
        Stores an ticketstore. If one with this uuid already exists, replaces it. Else, creates a new one
        validity is in seconds
        """
        validator = pickle.dumps(validatorFnc) if validatorFnc else None

        if secure:  # TODO: maybe in the future? what will mean "secure?" :)
            pass

        try:
            t = TicketStore.objects.get(uuid=uuid)
            t.data = pickle.dumps(data)
            t.stamp = getSqlDatetime()
            t.validity = validity
            t.save()
        except TicketStore.DoesNotExist:
            TicketStore.objects.create(uuid=uuid, stamp=getSqlDatetime(), data=pickle.dumps(data), validator=validator, validity=validity)

    @staticmethod
    def get(
            uuid: str,
            invalidate: bool = True,
            owner: typing.Optional[str] = None,
            secure: bool = False
        ) -> typing.Any:
        try:
            t = TicketStore.objects.get(uuid=uuid, owner=owner)
            validity = datetime.timedelta(seconds=t.validity)
            now = getSqlDatetime()

            logger.debug('Ticket validity: %s %s', t.stamp + validity, now)
            if t.stamp + validity < now:
                raise TicketStore.InvalidTicket('Not valid anymore')

            # if secure: TODO
            data = pickle.loads(t.data)

            # If has validator, execute it
            if t.validator:
                validator: ValidatorType = pickle.loads(t.validator)

                if validator(data) is False:
                    raise TicketStore.InvalidTicket('Validation failed')

            if invalidate is True:
                t.stamp = now - validity - datetime.timedelta(seconds=1)
                t.save()

            return data
        except TicketStore.DoesNotExist:
            raise TicketStore.InvalidTicket('Does not exists')

    @staticmethod
    def revalidate(uuid, validity=None, owner=None):
        try:
            t = TicketStore.objects.get(uuid=uuid, owner=owner)
            t.stamp = getSqlDatetime()
            if validity is not None:
                t.validity = validity
            t.save()
        except TicketStore.DoesNotExist:
            raise Exception('Does not exists')

    @staticmethod
    def cleanup():
        from datetime import timedelta
        now = getSqlDatetime()
        for v in TicketStore.objects.all():
            if now > v.stamp + timedelta(seconds=v.validity+600):  # Delete only really old tickets. Avoid "revalidate" issues
                v.delete()
        cleanSince = now - datetime.timedelta(seconds=TicketStore.MAX_VALIDITY)
        TicketStore.objects.filter(stamp__lt=cleanSince).delete()

    def __str__(self):
        if self.validator is not None:
            validator = pickle.loads(self.validator)
        else:
            validator = None

        return 'Ticket id: {}, Secure: {}, Stamp: {}, Validity: {}, Validator: {}, Data: {}'.format(self.uuid, self.owner, self.stamp, self.validity, validator, pickle.loads(self.data))
