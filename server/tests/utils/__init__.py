# -*- coding: utf-8 -*-
#
# Copyright (c) 2022 Virtual Cable S.L.
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
import logging
import typing
import collections.abc
from unittest import mock

from django.db import models
from uds.core import ui

logger = logging.getLogger(__name__)


T = typing.TypeVar('T')


def compare_dicts(
    expected: collections.abc.Mapping[str, typing.Any],
    actual: collections.abc.Mapping[str, typing.Any],
    ignore_keys: typing.Optional[list[str]] = None,
    ignore_values: typing.Optional[list[str]] = None,
    ignore_keys_startswith: typing.Optional[list[str]] = None,
    ignore_values_startswith: typing.Optional[list[str]] = None,
) -> list[tuple[str, str]]:
    """
    Compares two dictionaries, returning a list of differences
    """
    ignore_keys = ignore_keys or []
    ignore_values = ignore_values or []
    ignore_keys_startswith = ignore_keys_startswith or []
    ignore_values_startswith = ignore_values_startswith or []

    errors:list[tuple[str, str]] = []

    for k, v in expected.items():
        if k in ignore_keys:
            continue

        if any(k.startswith(ik) for ik in ignore_keys_startswith):
            continue

        if k not in actual:
            errors.append((k, f'Key "{k}" not found in actual'))
            continue

        if actual[k] in ignore_values:
            continue

        if any(actual[k].startswith(iv) for iv in ignore_values_startswith):
            continue

        if v != actual[k]:
            errors.append((k, f'Value for key "{k}" is "{actual[k]}" instead of "{v}"'))

    return errors


def ensure_data(
    item: models.Model,
    dct: collections.abc.Mapping[str, typing.Any],
    ignore_keys: typing.Optional[list[str]] = None,
    ignore_values: typing.Optional[list[str]] = None,
) -> bool:
    """
    Reads model as dict, fix some fields if needed and compares to dct
    """
    db_data = item.__class__.objects.filter(pk=item.pk).values()[0]
    # Remove if id and uuid in db_data, store uuid in id and remove uuid
    if 'id' in db_data and 'uuid' in db_data:
        db_data['id'] = db_data['uuid']
        del db_data['uuid']

    errors = compare_dicts(dct, db_data, ignore_keys=ignore_keys, ignore_values=ignore_values)
    if errors:
        logger.info('Errors found: %s', errors)
        return False

    return True


def random_ip_v4() -> str:
    """
    Returns a random ip v4 address
    """
    import random

    return '.'.join(str(random.randint(0, 255)) for _ in range(4))  # nosec


def random_ip_v6() -> str:
    """
    Returns a random ip v6 address
    """
    import random

    return ':'.join('{:04x}'.format(random.randint(0, 65535)) for _ in range(8))  # nosec


def random_mac() -> str:
    """
    Returns a random mac address
    """
    import random

    return ':'.join('{:02x}'.format(random.randint(0, 255)) for _ in range(6))  # nosec


def random_hostname() -> str:
    """
    Returns a random hostname
    """
    import random
    import string

    return ''.join(random.choice(string.ascii_lowercase) for _ in range(15))  # nosec


# Just compare types
# This is a simple class that returns true if the types of the two objects are the same
class MustBeOfType:
    _kind: type[typing.Any]
    
    def __init__(self, kind: type) -> None:
        self._kind = kind
    
    def __eq__(self, other: typing.Any) -> bool:
        return isinstance(other, self._kind)

    def __ne__(self, other: typing.Any) -> bool:
        return not self.__eq__(other)

    def __str__(self) -> str:
        return f'{self.__class__.__name__}({self._kind.__name__})'

    def __repr__(self) -> str:
        return self.__str__()

def search_item_by_attr(lst: list[T], attribute: str, value: typing.Any) -> T:
    """
    Returns an item from a list of items
    """
    for item in lst:
        if getattr(item, attribute) == value:
            return item
    raise ValueError(f'Item with {attribute}=="{value}" not found in list {str(lst)[:100]}')

def filter_list_by_attr(lst: list[T], attribute: str, value: typing.Any) -> list[T]:
    """
    Returns a list of items from a list of items
    """
    return [item for item in lst if getattr(item, attribute) == value or value is None]

def check_userinterface_values(obj: ui.UserInterface, values: ui.gui.ValuesDictType) -> None:
    """
    Checks that a user interface object has the values specified
    """
    for k, v in values.items():
        if isinstance(v, MustBeOfType):
            assert isinstance(getattr(obj, k), v._kind)
        elif v == mock.ANY:
            pass
        else:
            assert getattr(obj, k) == v
