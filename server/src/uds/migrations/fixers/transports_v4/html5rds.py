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

from uds.core import consts, transports
from uds.core.ui import gui

from . import _migrator

logger = logging.getLogger(__name__)


# Copy for migration
class HTML5RDSTransport(transports.Transport):
    """
    Provides access via RDP to service.
    This transport can use an domain. If username processed by authenticator contains '@', it will split it and left-@-part will be username, and right password
    """

    type_name = 'RDS'
    type_type = 'HTML5RDSTransport'

    guacamoleServer = gui.TextField(label='',default='https://')
    useGlyptodonTunnel = gui.CheckBoxField(label='')
    useEmptyCreds = gui.CheckBoxField(label='')
    withoutDomain = gui.CheckBoxField(label='')
    fixedDomain = gui.TextField(label='')
    wallpaper = gui.CheckBoxField(label='')
    desktopComp = gui.CheckBoxField(label='')
    smooth = gui.CheckBoxField(label='')
    enableAudio = gui.CheckBoxField(label='',default=True)
    enableAudioInput = gui.CheckBoxField(label='')
    enablePrinting = gui.CheckBoxField(label='')
    enableFileSharing = gui.ChoiceField(label='',default='false')
    enableClipboard = gui.ChoiceField(label='',default='enabled')
    serverLayout = gui.ChoiceField(label='',default='-')
    ticketValidity = gui.NumericField(label='',default=60)

    forceNewWindow = gui.ChoiceField(label='',default='false')
    security = gui.ChoiceField(label='',default='any')
    rdpPort = gui.NumericField(label='',default=3389)

    customGEPath = gui.TextField(label='',default='/')

    # Load balancing info
    loadBalancingInfo = gui.TextField(label='',default='')

    gatewayHostname = gui.TextField(label='',default='')
    gatewayPort = gui.NumericField(label='',default=443)
    gatewayUsername = gui.TextField(label='',default='')
    gatewayPassword = gui.PasswordField(label='',default='')
    gatewayDomain = gui.TextField(label='',default='')

    # This value is the new "tunnel server"
    # Old guacamoleserver value will be stored also on database, but will be ignored
    tunnel = gui.ChoiceField(label='')


def migrate(apps, schema_editor) -> None:
    _migrator.tunnel_transport(apps, HTML5RDSTransport, 'guacamoleServer', is_html_server=True)


def rollback(apps, schema_editor) -> None:
    _migrator.tunnel_transport_back(apps, HTML5RDSTransport, 'guacamoleServer', is_html_server=True)
