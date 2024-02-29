# -*- coding: utf-8 -*-

#
# Copyright (c) 2016-2022 Virtual Cable S.L.U.
# All rights reservem.
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

from django.utils.translation import gettext_noop as _
from .x2go_base import BaseX2GOTransport
from . import x2go_file

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models
    from uds.core import types
    from uds.core.types.requests import ExtendedHttpRequestWithUser

logger = logging.getLogger(__name__)


class X2GOTransport(BaseX2GOTransport):
    """
    Provides access via X2GO to service.
    This transport can use an domain. If username processed by authenticator contains '@', it will split it and left-@-part will be username, and right password
    """

    is_base = False

    type_name = _('X2Go')
    type_type = 'X2GOTransport'
    type_description = _('X2Go access (Experimental). Direct connection.')

    fixed_name = BaseX2GOTransport.fixed_name
    screen_size = BaseX2GOTransport.screen_size
    desktop_type = BaseX2GOTransport.desktop_type
    custom_cmd = BaseX2GOTransport.custom_cmd
    sound = BaseX2GOTransport.sound
    exports = BaseX2GOTransport.exports
    speed = BaseX2GOTransport.speed

    sound_type = BaseX2GOTransport.sound_type
    keyboard_layout = BaseX2GOTransport.keyboard_layout
    pack = BaseX2GOTransport.pack
    quality = BaseX2GOTransport.quality

    def get_transport_script(  # pylint: disable=too-many-locals
        self,
        userservice: 'models.UserService',
        transport: 'models.Transport',
        ip: str,
        os: 'types.os.DetectedOsInfo',
        user: 'models.User',
        password: str,
        request: 'ExtendedHttpRequestWithUser',
    ) -> 'types.transports.TransportScript':
        ci = self.get_connection_info(userservice, user, password)

        priv, _pub = self.getAndPushKey(ci.username, userservice)

        width, height = self.get_screen_size()
        rootless = False
        desktop = self.desktop_type.value
        if desktop == "UDSVAPP":
            desktop = "/usr/bin/udsvapp " + self.custom_cmd.value
            rootless = True

        xf = x2go_file.getTemplate(
            speed=self.speed.value,
            pack=self.pack.value,
            quality=self.quality.value,
            sound=self.sound.as_bool(),
            soundSystem=self.sound.value,
            windowManager=desktop,
            exports=self.exports.as_bool(),
            rootless=rootless,
            width=width,
            height=height,
            user=ci.username,
        )

        sp = {'ip': ip, 'port': '22', 'key': priv, 'xf': xf}

        try:
            return self.get_script(os.os.os_name(), 'direct', sp)
        except Exception:
            return super().get_transport_script(
                userservice, transport, ip, os, user, password, request
            )
