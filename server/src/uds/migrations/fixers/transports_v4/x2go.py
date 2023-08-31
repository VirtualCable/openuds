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
import logging

from uds.core import consts, transports
from uds.core.types.preferences import CommonPrefs
from uds.core.ui import gui

from . import _migrator

logger = logging.getLogger(__name__)


# Copy for migration
class TX2GOTransport(transports.Transport):
    """
    Provides access via X2GO to service.
    This transport can use an domain. If username processed by authenticator contains '@', it will split it and left-@-part will be username, and right password
    """

    typeType = 'TX2GOTransport'

    tunnelServer = gui.TextField()
    tunnelWait = gui.NumericField(default='30')
    verifyCertificate = gui.CheckBoxField(default=consts.FALSE_STR)
    fixedName = gui.TextField()
    screenSize = gui.ChoiceField(default=CommonPrefs.SZ_FULLSCREEN)
    desktopType = gui.ChoiceField()
    customCmd = gui.TextField()
    sound = gui.CheckBoxField(default=consts.TRUE_STR)
    exports = gui.CheckBoxField(default=consts.FALSE_STR)
    speed = gui.ChoiceField(default='3')
    soundType = gui.ChoiceField(default='pulse')
    keyboardLayout = gui.TextField(default='')
    pack = gui.TextField(default='16m-jpeg')
    quality = gui.NumericField(default='6')

    # This value is the new "tunnel server"
    # Old guacamoleserver value will be stored also on database, but will be ignored
    tunnel = gui.ChoiceField()


def migrate(apps, schema_editor) -> None:
    _migrator.tunnel_transport(apps, TX2GOTransport, 'tunnelServer', is_html_server=False)


def rollback(apps, schema_editor) -> None:
    _migrator.tunnel_transport_back(apps, TX2GOTransport, 'tunnelServer', is_html_server=False)
