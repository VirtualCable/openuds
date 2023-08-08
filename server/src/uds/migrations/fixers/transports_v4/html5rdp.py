# -*- coding: utf-8 -*-
#
# Copyright (c) 2023 Virtual Cable S.L.U.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification
# are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright notice
#      this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright notice
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
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging

from uds.core.ui import gui
from uds.core import transports

from . import _migrator

logger = logging.getLogger(__name__)


# Copy for migration
class HTML5RDPTransport(transports.Transport):
    """
    Provides access via RDP to service.
    This transport can use an domain. If username processed by authenticator contains '@', it will split it and left-@-part will be username, and right password
    """

    typeName = 'HTML5 RDP'  # Not important here, just for migrations
    typeType = 'HTML5RDPTransport'

    guacamoleServer = gui.TextField()

    useGlyptodonTunnel = gui.CheckBoxField()

    useEmptyCreds = gui.CheckBoxField()
    fixedName = gui.TextField()
    fixedPassword = gui.PasswordField()
    withoutDomain = gui.CheckBoxField()
    fixedDomain = gui.TextField()
    wallpaper = gui.CheckBoxField()
    desktopComp = gui.CheckBoxField()
    smooth = gui.CheckBoxField()
    enableAudio = gui.CheckBoxField(defvalue=gui.TRUE)
    enableAudioInput = gui.CheckBoxField()
    enablePrinting = gui.CheckBoxField()
    enableFileSharing = gui.ChoiceField(defvalue='false')
    enableClipboard = gui.ChoiceField(defvalue='enabled')

    serverLayout = gui.ChoiceField(defvalue='-')

    ticketValidity = gui.NumericField(defvalue='60')

    forceNewWindow = gui.ChoiceField(defvalue=gui.FALSE)
    security = gui.ChoiceField(defvalue='any')

    rdpPort = gui.NumericField(defvalue='3389')

    customGEPath = gui.TextField(defvalue='/')

    # This value is the new "tunnel server"
    # Old guacamoleserver value will be stored also on database, but will be ignored
    tunnel = gui.ChoiceField()


def migrate(apps, schema_editor) -> None:
    _migrator.tunnel_transport(apps, HTML5RDPTransport, 'guacamoleServer', is_html_server=True)


def rollback(apps, schema_editor) -> None:
    _migrator.tunnel_transport_back(apps, HTML5RDPTransport, 'guacamoleServer', is_html_server=True)
