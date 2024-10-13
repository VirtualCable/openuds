# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2023 Virtual Cable S.L.U.
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
'''
Author: Adolfo Gómez, dkmaster at dkmon dot com
'''
import datetime
import pickle  # nosec: Tickets are generated by us, so we know they are safe
import logging
import pickletools
import typing
import collections.abc

from django.db import models

from uds.core.managers.crypto import CryptoManager

from .uuid_model import UUIDModel
from uds.core.util.model import sql_now
from uds.core import consts

from .user import User
from .user_service import UserService

logger = logging.getLogger(__name__)


class TicketStore(UUIDModel):
    """
    Tickets storing on DB
    """

    # Cleanup will purge all elements that have been created MAX_VALIDITY ago

    owner = models.CharField(null=True, blank=True, default=None, max_length=8)
    stamp = models.DateTimeField()  # Date creation or validation of this entry
    validity = models.IntegerField(default=60)  # Duration allowed for this ticket to be valid, in seconds

    data = models.BinaryField()  # Associated ticket data

    # "fake" declarations for type checking
    # objects: 'models.manager.Manager[TicketStore]'

    class InvalidTicket(Exception):
        pass

    class Meta:  # pyright: ignore
        """
        Meta class to declare the name of the table at database
        """

        db_table = 'uds_tickets'
        app_label = 'uds'

    @staticmethod
    def generate_uuid() -> str:
        """In fact, generates a random string of TICKET_LENGTH chars, that will be used as uuid for the ticket (but is not an uuid compliant string)"""
        return (
            CryptoManager().random_string(consts.ticket.TICKET_LENGTH).lower()
        )  # Temporary fix lower() for compat with 3.0

    @staticmethod
    def create(
        data: typing.Any,
        validity: int = consts.ticket.DEFAULT_TICKET_VALIDITY_TIME,
        owner: typing.Optional[str] = None,
        secure: bool = False,
    ) -> str:
        """Creates a ticket (used to store data that can be retrieved later using REST API, for example)

        Args:
            data: Data to store on ticket
            validity: Validity of the ticket, in seconds
            owner: Optional owner of the ticket. If present, only the owner can retrieve the ticket
            secure: If true, the data will be encrypted using the owner as key. If owner is not present, an exception will be raised

        Returns:
            The ticket id
        """
        data = pickletools.optimize(
            pickle.dumps(data, protocol=-1)
        )  # nosec: Tickets are generated by us, so we know they are safe

        if secure:
            if not owner:
                raise ValueError('Tried to use a secure ticket without owner')
            data = CryptoManager().aes_crypt(data, owner.encode())
            owner = (
                consts.ticket.TICKET_SECURED_ONWER
            )  # So data is REALLY encrypted, because key used to encrypt is sustituted by SECURED on DB

        return TicketStore.objects.create(
            uuid=TicketStore.generate_uuid(),
            stamp=sql_now(),
            data=data,
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
            key = b''
            if secure:
                if not owner:
                    raise ValueError('Tried to use a secure ticket without owner')
                # db Owner is the value stored on the DB
                # So, if this is a secure ticket, we must use the SECURED value
                # And use the real "owner" as key to encrypt/decrypt
                key = owner.encode()
                owner = consts.ticket.TICKET_SECURED_ONWER  # Generic "secured" owner for secure tickets

            t = TicketStore.objects.get(uuid=uuid, owner=owner)
            validity = datetime.timedelta(seconds=t.validity)
            now = sql_now()

            logger.debug('Ticket validity: %s %s', t.stamp + validity, now)
            if t.stamp + validity < now:
                raise TicketStore.InvalidTicket('Not valid anymore')

            data: bytes = t.data

            if secure:  # If secure, we must decrypt the data
                data = CryptoManager().aes_decrypt(data, key)

            data = pickle.loads(data)  # nosec: Tickets are generated by us, so we know they are safe

            if invalidate is True:
                t.stamp = now - validity - datetime.timedelta(seconds=1)
                t.save(update_fields=['stamp'])

            return data
        except TicketStore.DoesNotExist:
            raise TicketStore.InvalidTicket('Does not exists') from None

    @staticmethod
    def update(
        uuid: str,
        secure: bool = False,
        owner: typing.Optional[str] = None,
        checking_fnc: collections.abc.Callable[[typing.Any], bool] = lambda x: True,
        **kwargs: typing.Any,
    ) -> None:
        try:
            key = b''
            if secure:
                if not owner:
                    raise ValueError('Tried to use a secure ticket without owner')
                key = owner.encode()

            t = TicketStore.objects.get(uuid=uuid)

            data: bytes = t.data

            if secure:  # Owner has already been tested and it's not emtpy
                if not owner:
                    raise ValueError('Tried to use a secure ticket without owner')
                data = CryptoManager().aes_decrypt(data, key)

            saved_data = pickle.loads(data)  # nosec: Tickets are ONLY generated by us, so we know they are safe

            # invoke check function
            if checking_fnc(saved_data) is False:
                raise TicketStore.InvalidTicket('Validation failed')

            for k, v in kwargs.items():
                if v is not None:
                    saved_data[k] = v

            # Reserialize
            data = pickletools.optimize(
                pickle.dumps(saved_data, protocol=-1)
            )  # nosec: Tickets are generated by us, so we know they are safe
            if secure:
                data = CryptoManager().aes_crypt(data, key)
            t.data = data
            t.save(update_fields=['data'])
        except TicketStore.DoesNotExist:
            pass

    @staticmethod
    def revalidate(
        uuid: str,
        validity: typing.Optional[int] = None,
        owner: typing.Optional[str] = None,
    ) -> None:
        try:
            t = TicketStore.objects.get(uuid=uuid, owner=owner)
            t.stamp = sql_now()
            if validity:
                t.validity = validity
            t.save(update_fields=['validity', 'stamp'])
        except TicketStore.DoesNotExist:
            raise TicketStore.InvalidTicket('Does not exists') from None

    # Especific methods for tunnel
    @staticmethod
    def create_for_tunnel(
        userservice: 'UserService',
        port: int,
        host: typing.Optional[str] = None,
        extra: typing.Optional[collections.abc.Mapping[str, typing.Any]] = None,
        key: typing.Optional[str] = None,
        validity: int = 60 * 60 * 24,  # 24 Hours default validity for tunnel tickets
    ) -> str:
        owner = CryptoManager().random_string(length=8)
        if not userservice.user:
            raise ValueError('User is not set in userservice')
        data = {
            'u': userservice.user.uuid if userservice.user else '',
            's': userservice.uuid,
            'h': host,
            'p': port,
            'e': extra,
            'k': key or '',
        }
        return (
            # Note that the ticket is the uuid + owner, so we can encrypt data without keeping the key
            # Create will not store owner on DB, so unless the ticket is available, we can't decrypt it
            # This ensures that data is not available unless the ticket is available, so it can be considered secure
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
    ) -> tuple[
        'User',
        'UserService',
        typing.Optional[str],
        int,
        typing.Optional[collections.abc.Mapping[str, typing.Any]],
        str,
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

            # Now, ensure elements exists, onwership is fine
            # if not found any, will raise an execption
            user = User.objects.get(uuid=data['u'])
            userservice = UserService.objects.get(uuid=data['s'], user=user)

            host = data['h']

            if not host:
                host = userservice.get_instance().get_ip()

            return (user, userservice, host, data['p'], data['e'], data.get('k', ''))
        except Exception as e:
            raise TicketStore.InvalidTicket(str(e))

    @staticmethod
    def cleanup() -> None:
        now = sql_now()
        for v in TicketStore.objects.all():
            if now > v.stamp + datetime.timedelta(
                seconds=v.validity + 600
            ):  # Delete only really old tickets. Avoid "revalidate" issues
                v.delete()
        clean_since = now - datetime.timedelta(seconds=consts.ticket.MAX_TICKET_VALIDITY_TIME)
        # Also remove too long tickets, even if they are not  (12 hours is the default)
        TicketStore.objects.filter(stamp__lt=clean_since).delete()

    def __str__(self) -> str:
        # Tickets are generated by us, so we know they are safe
        data = (
            pickle.loads(self.data) if self.owner != consts.ticket.TICKET_SECURED_ONWER else '{Secure Ticket}'
        )  # nosec

        return (
            f'Ticket id: {self.uuid}, Owner: {self.owner}, Stamp: {self.stamp}, '
            f'Validity: {self.validity}, Data: {data}'
        )
