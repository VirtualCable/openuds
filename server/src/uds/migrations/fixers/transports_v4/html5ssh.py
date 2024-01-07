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
from uds.core.ui import gui

from . import _migrator

logger = logging.getLogger(__name__)


class HTML5SSHTransport(transports.Transport):
    """
    Provides access via SSH to service.
    """

    type_type = 'HTML5SSHTransport'

    guacamoleServer = gui.TextField(label='',default='https://')
    username = gui.TextField(label='')
    sshCommand = gui.TextField(label='')
    enableFileSharing = gui.ChoiceField(label='',default='false')
    fileSharingRoot = gui.TextField(label='')
    sshPort = gui.NumericField(label='',default=22)
    sshHostKey = gui.TextField(label='')
    serverKeepAlive = gui.NumericField(label='',default=30)
    ticketValidity = gui.NumericField(label='',default=60)
    forceNewWindow = gui.ChoiceField(label='',default='false')

    # This value is the new "tunnel server"
    # Old guacamoleserver value will be stored also on database, but will be ignored
    tunnel = gui.ChoiceField(label='')


def migrate(apps, schema_editor) -> None:
    _migrator.tunnel_transport(apps, HTML5SSHTransport, 'guacamoleServer', is_html_server=True)


def rollback(apps, schema_editor) -> None:
    _migrator.tunnel_transport_back(apps, HTML5SSHTransport, 'guacamoleServer', is_html_server=True)
