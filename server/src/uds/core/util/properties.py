# -*- coding: utf-8 -*-

#
# Copyright (c) 2023 Virtual Cable S.L.U.
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
import collections.abc
import contextlib
import logging

from django.db.models import signals
from django.db import transaction

from uds.models.properties import Properties

if typing.TYPE_CHECKING:
    from django.db import models

logger = logging.getLogger(__name__)


class PropertyAccessor:
    """
    Property accessor, used to access properties of an object
    """

    transaction: 'typing.Optional[transaction.Atomic]'
    owner_id: str
    owner_type: str

    def __init__(self, owner_id: str, owner_type: str):
        self.owner_id = owner_id
        self.owner_type = owner_type

    def _filter(self) -> 'models.QuerySet[Properties]':
        return Properties.objects.filter(owner_id=self.owner_id, owner_type=self.owner_type)

    def __getitem__(self, key: str) -> typing.Any:
        try:
            return self._filter().get(key=key).value
        except Properties.DoesNotExist:
            raise KeyError(key)

    def __setitem__(self, key: str, value: typing.Any) -> None:
        try:
            p = self._filter().get(key=key)
            p.value = value
            p.save()
        except Properties.DoesNotExist:
            Properties.objects.create(owner_id=self.owner_id, owner_type=self.owner_type, key=key, value=value)

    def __delitem__(self, key: str) -> None:
        try:
            self._filter().get(key=key).delete()
        except Properties.DoesNotExist:
            pass  # Ignore if not exists

    def __contains__(self, key: str) -> bool:
        return self._filter().filter(key=key).exists()

    def __iter__(self) -> typing.Iterator[str]:
        return iter(self._filter().values_list('key', flat=True))

    def __len__(self) -> int:
        return self._filter().count()

    def get(self, key: str, default: typing.Any = None) -> typing.Any:
        try:
            return self[key]
        except KeyError:
            return default

    def setdefault(self, key: str, default: typing.Any = None) -> typing.Any:
        try:
            return self[key]
        except KeyError:
            self[key] = default
            return default

    def keys(self) -> typing.Iterator[str]:
        return iter(self._filter().values_list('key', flat=True))

    def values(self) -> typing.Iterator[typing.Any]:
        return iter(self._filter().values_list('value', flat=True))

    def items(self) -> typing.Iterator[typing.Tuple[str, typing.Any]]:
        return iter(self._filter().values_list('key', 'value'))

    def clear(self) -> None:
        self._filter().delete()

    def pop(self, key: str, default: typing.Any = None) -> typing.Any:
        try:
            v = self[key]
            del self[key]
            return v
        except KeyError:
            return default

    def __enter__(self) -> 'PropertyAccessor':
        self.transaction = transaction.atomic()
        self.transaction.__enter__()
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self.transaction:
            self.transaction.__exit__(exc_type, exc_value, traceback)


class PropertiesMixin:
    """Mixin to add properties to a model"""

    def ownerIdAndType(self) -> typing.Tuple[str, str]:
        """Returns the owner id and type of this object
        The owner id and type is used to identify the owner in the properties table

        Returns:
            typing.Tuple[str, str]: Owner id and type
        """
        # Default implementation does not provide any owner id or type
        return '', self.__class__.__name__

    @property
    def properties(self) -> PropertyAccessor:
        owner_id, owner_type = self.ownerIdAndType()
        return PropertyAccessor(owner_id=owner_id, owner_type=owner_type)

    @staticmethod
    def _deleteSignal(sender, **kwargs) -> None:  # pylint: disable=unused-argument
        toDelete: 'PropertiesMixin' = kwargs['instance']
        # We are deleting the object, so we delete the properties too
        # Remember that properties is a generic table, does not have any cascade delete
        toDelete.properties.clear()

    @staticmethod
    def setupSignals(model: 'type[models.Model]') -> None:
        """Connects a pre deletion signal to delete properties
        Note that this method must be added to every class creation that inherits from PropertiesMixin
        Or the properties will not be deleted on deletion of the object

        Args:
            model (type[models.Model]): Model to connect the signal to
        """
        signals.pre_delete.connect(PropertiesMixin._deleteSignal, sender=model)
