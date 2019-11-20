# -*- coding: utf-8 -*-

#
# Copyright (c) 2014-2019 Virtual Cable S.L.
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

"""
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing

from django.utils.translation import ugettext as _

from uds.models.util import getSqlDatetimeAsUnix
from uds.core import VERSION
from ..handlers import Handler

logger = logging.getLogger(__name__)

def actorResult(result: typing.Any = None, error: typing.Optional[str] = None) -> typing.MutableMapping[str, typing.Any]:
    result = result or ''
    res = {'result': result, 'stamp': getSqlDatetimeAsUnix()}
    if error:
        res['error'] = error
    return res

# Enclosed methods under /actor path
class ActorV2(Handler):
    """
    Processes actor requests
    """
    authenticated = False  # Actor requests are not authenticated by REST api (except register)
    path = 'actor'
    name = 'v2'

    def get(self):
        """
        Processes get requests
        """
        logger.debug('Actor args for GET: %s', self._args)

        return actorResult({'version': VERSION, 'required': '3.0.0'})

class ActorV2Action(Handler):
    authenticated = False  # Actor requests are not authenticated normally
    path = 'actor/v2'

    def get(self):
        return actorResult('')



class ActorV2Register(ActorV2Action):
    """
    Registers an actor
    """
    authenticated = True
    name = 'register'

    def post(self):
        logger.debug('Args: %s,  Params: %s', self._args, self._params)
        return actorResult('ok')

class ActorV2Initiialize(ActorV2Action):
    """
    Information about machine action.
    Also returns the id used for the rest of the actions. (Only this one will use actor key)
    """
    name = 'initiaize'

    def post(self):
        logger.debug('Args: %s,  Params: %s', self._args, self._params)
        return actorResult('ok')

class ActorV2Login(ActorV2Action):
    """
    Information about machine
    """
    name = 'login'

    def post(self):
        logger.debug('Args: %s,  Params: %s', self._args, self._params)
        return actorResult('ok')

class ActorV2Logout(ActorV2Action):
    """
    Information about machine
    """
    name = 'logout'

    def post(self):
        logger.debug('Args: %s,  Params: %s', self._args, self._params)
        return actorResult('ok')

class ActorV2Log(ActorV2Action):
    """
    Information about machine
    """
    name = 'log'

    def post(self):
        logger.debug('Args: %s,  Params: %s', self._args, self._params)
        return actorResult('ok')

class ActorV2IpChange(ActorV2Action):
    """
    Information about machine
    """
    name = 'ipchange'

    def post(self):
        logger.debug('Args: %s,  Params: %s', self._args, self._params)
        return actorResult('ok')

class ActorV2Ready(ActorV2Action):
    """
    Information about machine
    """
    name = 'ready'

    def post(self):
        logger.debug('Args: %s,  Params: %s', self._args, self._params)
        return actorResult('ok')
