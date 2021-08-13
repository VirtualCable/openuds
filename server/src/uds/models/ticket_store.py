# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2020 Virtual Cable S.L.U.
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

from .user import User
from .user_service import UserService

logger = logging.getLogger(__name__)

ValidatorType = typing.Callable[[typing.Any], bool]

SECURED = '#SECURE#'  # Just a "different" owner. If used anywhere, it's not important (will not fail), but weird enough


class TicketStore(UUIDModel):
    """
    Tickets storing on DB
    """

    DEFAULT_VALIDITY = 60
    MAX_VALIDITY = 60 * 60 * 12
    # Cleanup will purge all elements that have been created MAX_VALIDITY ago

    owner = models.CharField(null=True, blank=True, default=None, max_length=8)
    stamp = models.DateTimeField()  # Date creation or validation of this entry
    validity = models.IntegerField(
        default=60
    )  # Duration allowed for this ticket to be valid, in seconds

    data = models.BinaryField()  # Associated ticket data
    validator = models.BinaryField(
        null=True, blank=True, default=None
    )  # Associated validator for this ticket

    # "fake" declarations for type checking
    objects: 'models.BaseManager[TicketStore]'

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
        return (
            cryptoManager().randomString(40).lower()
        )  # Temporary fix lower() for compat with 3.0

    @staticmethod
    def create(
        data: typing.Any,
        validatorFnc: typing.Optional[ValidatorType] = None,  # type: ignore
        validity: int = DEFAULT_VALIDITY,
        owner: typing.Optional[str] = None,
        secure: bool = False,
    ) -> str:
        """
        validity is in seconds
        """
        validator = pickle.dumps(validatorFnc) if validatorFnc else None

        data = pickle.dumps(data)

        if secure:
            if not owner:
                raise ValueError('Tried to use a secure ticket without owner')
            data = cryptoManager().AESCrypt(data, owner.encode())
            owner = SECURED  # So data is REALLY encrypted

        return TicketStore.objects.create(
            stamp=getSqlDatetime(),
            data=data,
            validator=validator,
            validity=validity,
            owner=owner,
        ).uuid

    @staticmethod
    def get(
        uuid: str,
        invalidate: bool = True,
        owner: typing.Optional[str] = None,
        secure: bool = False,
    ) -> typing.Any:
        try:
            dbOwner = owner
            if secure:
                if not owner:
                    raise ValueError('Tried to use a secure ticket without owner')
                dbOwner = SECURED

            t = TicketStore.objects.get(uuid=uuid, owner=dbOwner)
            validity = datetime.timedelta(seconds=t.validity)
            now = getSqlDatetime()

            logger.debug('Ticket validity: %s %s', t.stamp + validity, now)
            if t.stamp + validity < now:
                raise TicketStore.InvalidTicket('Not valid anymore')

            data: bytes = t.data

            if secure:  # Owner has already been tested and it's not emtpy
                data = cryptoManager().AESDecrypt(
                    data, typing.cast(str, owner).encode()
                )

            data = pickle.loads(data)

            # If has validator, execute it
            if t.validator:
                validator: ValidatorType = pickle.loads(t.validator)

                if validator(data) is False:
                    raise TicketStore.InvalidTicket('Validation failed')

            if invalidate is True:
                t.stamp = now - validity - datetime.timedelta(seconds=1)
                t.save(update_fields=['stamp'])

            return data
        except TicketStore.DoesNotExist:
            raise TicketStore.InvalidTicket('Does not exists')

    @staticmethod
    def revalidate(
        uuid: str,
        validity: typing.Optional[int] = None,
        owner: typing.Optional[str] = None,
    ):
        try:
            t = TicketStore.objects.get(uuid=uuid, owner=owner)
            t.stamp = getSqlDatetime()
            if validity:
                t.validity = validity
            t.save(update_fields=['validity', 'stamp'])
        except TicketStore.DoesNotExist:
            raise TicketStore.InvalidTicket('Does not exists')

    # Especific methods for tunnel
    @staticmethod
    def create_for_tunnel(
        userService: 'UserService',
        port: int,
        host: typing.Optional[str] = None,
        extra: typing.Optional[typing.Mapping[str, typing.Any]] = None,
        validity: int = 60 * 60 * 24,  # 24 Hours default validity for tunnel tickets
    ) -> str:
        owner = cryptoManager().randomString(length=8)
        data = {
            'u': userService.user.uuid,
            's': userService.uuid,
            'h': host,
            'p': port,
            'e': extra,
        }
        return (
            TicketStore.create(
                data=data,
                validity=validity,
                owner=owner,
                secure=True,
            )
            + owner
        )

    @staticmethod
    def get_for_tunnel(
        ticket: str,
    ) -> typing.Tuple[
        'User',
        'UserService',
        typing.Optional[str],
        int,
        typing.Optional[typing.Mapping[str, typing.Any]],
    ]:
        """
        Returns the ticket for a tunneled connection
        The returned value is a tuple:
          (User, UserService, Host (nullable), Port, Extra Dict)
        """
        try:
            if len(ticket) != 48:
                raise Exception(f'Invalid ticket format: {ticket!r}')

            uuid, owner = ticket[:-8], ticket[-8:]
            data = TicketStore.get(uuid, invalidate=False, owner=owner, secure=True)

            # Now, ensure elements exists, onwershit is fine
            # if not found any, will raise an execption
            user = User.objects.get(uuid=data['u'])
            userService = UserService.objects.get(uuid=data['s'], user=user)
            host = data['h']

            if not host:
                host = userService.getInstance().getIp()

            return (user, userService, host, data['p'], data['e'])
        except Exception as e:
            raise TicketStore.InvalidTicket(str(e))

    @staticmethod
    def cleanup() -> None:
        now = getSqlDatetime()
        for v in TicketStore.objects.all():
            if now > v.stamp + datetime.timedelta(
                seconds=v.validity + 600
            ):  # Delete only really old tickets. Avoid "revalidate" issues
                v.delete()
        cleanSince = now - datetime.timedelta(seconds=TicketStore.MAX_VALIDITY)
        # Also remove too long tickets, even if they are not  (12 hours is the default)
        TicketStore.objects.filter(stamp__lt=cleanSince).delete()

    def __str__(self) -> str:
        data = pickle.loads(self.data) if self.owner != SECURED else '{Secure Ticket}'

        return 'Ticket id: {}, Owner: {}, Stamp: {}, Validity: {}, Data: {}'.format(
            self.uuid,
            self.owner,
            self.stamp,
            self.validity,
            data,
        )
