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

from uds.core.ui import gui
from uds.core import transports

from . import _migrator

logger = logging.getLogger(__name__)


# Copy for migration
class TSPICETransport(transports.Transport):
    """
    Provides access via SPICE to service.
    """

    typeType = 'TSSPICETransport'

    tunnelServer = gui.TextField()
    tunnelWait = gui.NumericField(defvalue='30')
    verifyCertificate = gui.CheckBoxField()
    serverCertificate = gui.TextField()
    fullScreen = gui.CheckBoxField()
    smartCardRedirect = gui.CheckBoxField(defvalue=gui.FALSE)
    usbShare = gui.CheckBoxField(defvalue=gui.FALSE)
    autoNewUsbShare = gui.CheckBoxField(defvalue=gui.FALSE)
    SSLConnection = gui.CheckBoxField(defvalue=gui.TRUE)

    overridedProxy = gui.TextField()

    # This value is the new "tunnel server"
    # Old guacamoleserver value will be stored also on database, but will be ignored
    tunnel = gui.ChoiceField()


def migrate(apps, schema_editor) -> None:
    _migrator.tunnel_transport(apps, TSPICETransport, 'tunnelServer', is_html_server=False)


def rollback(apps, schema_editor) -> None:
    _migrator.tunnel_transport_back(apps, TSPICETransport, 'tunnelServer', is_html_server=False)