# -*- coding: utf-8 -*-

#
# Copyright (c) 2022 Virtual Cable S.L.U.
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
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import random
import string
import dataclasses
import typing


from django.utils.translation import gettext_noop as _
from uds.core import services
from uds.core import module
from .service import ServiceTestNoCache, ServiceTestCache

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.environment import Environment

logger = logging.getLogger(__name__)

class TestProvider(services.ServiceProvider):
    """
    This class represents the simple Test provider.

    This is only intended for testing purposes, and is not a good example of
    a provider.

    """
    # : What kind of services we offer, this are classes inherited from Service
    offers = [ServiceTestNoCache, ServiceTestCache]
    # : Name to show the administrator. This string will be translated BEFORE
    # : sending it to administration interface, so don't forget to
    # : mark it as _ (using gettext_noop)
    typeName = _('Testing Provider')
    # : Type used internally to identify this provider
    typeType = 'TestProvider'
    # : Description shown at administration interface for this provider
    typeDescription = _('Test (and dummy) service provider')
    # : Icon file used as icon for this provider. This string will be translated
    # : BEFORE sending it to administration interface, so don't forget to
    # : mark it as _ (using gettext_noop)
    iconFile = 'provider.png'

    # Max preparing concurrent services
    maxPreparingServices = 1000 # a lot, this in fact will not make anything

    # Mas removing concurrent services
    maxRemovingServices = 1000 # a lot, this in fact will not make anything

    # Simple data for testing pourposes
    @dataclasses.dataclass
    class Data:
        """
        This is the data we will store in the storage
        """
        name: str = ''
        integer: int = 0

    data: Data

    def initialize(self, values: 'module.Module.ValuesType') -> None:
        self.data = TestProvider.Data()
        if values:
            self.data.name = ''.join(random.SystemRandom().choices(string.ascii_letters, k=10))
            self.data.integer = random.randint(0, 100)
            return super().initialize(values)

    @staticmethod
    def test(
        env: 'Environment', data: typing.Dict[str, str]
    ) -> typing.List[typing.Any]:
        return [True, _('Nothing tested, but all went fine..')]

    def getName(self) -> str:
        """
        returns a random name for testing pourposes
        """
        return self.data.name
    