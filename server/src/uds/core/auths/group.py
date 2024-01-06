# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2019 Virtual Cable S.L.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification,are permitted provided that the following conditions are
# met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions and the following disclaimer in the documentation
#     and/or other materials provided with the distribution.
#   * Neither the name of Virtual Cable S.L.U. nor the names of its contributors
#     may be used to endorse or promote products derived from this software
#     without specific prior written permission.
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
import logging
import typing
import collections.abc

# Imports for type checking
if typing.TYPE_CHECKING:
    from .authenticator import Authenticator as AuthenticatorInstance
    from uds.models.group import Group as DBGroup


logger = logging.getLogger(__name__)


class Group:
    """
    A group is simply a database group associated with its authenticator instance

    It's only constructor expect a database group as parameter.
    """
    _db_group: 'DBGroup'

    def __init__(self, db_group: 'DBGroup'):
        """
        Initializes internal data
        """
        self._manager = db_group.getManager()
        self._db_group = db_group

    def manager(self) -> 'AuthenticatorInstance':
        """
        Returns the database authenticator associated with this group
        """
        return self._manager

    def db_obj(self) -> 'DBGroup':
        """
        Returns the database group associated with this
        """
        return self._db_group
