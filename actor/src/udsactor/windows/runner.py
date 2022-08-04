# -*- coding: utf-8 -*-
#
# Copyright (c) 2019-2022 Virtual Cable S.L.U.
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
'''
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''
# pylint: disable=invalid-name
import sys
import win32service
import win32serviceutil
import servicemanager

import win32timezone  # pylint: disable=unused-import

from .service import UDSActorSvc

def setupRecoverService():
    svc_name = UDSActorSvc._svc_name_  # pylint: disable=protected-access

    hs = None
    hscm = None
    try:
        hscm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_ALL_ACCESS)

        try:
            hs = win32serviceutil.SmartOpenService(hscm, svc_name, win32service.SERVICE_ALL_ACCESS)
            service_failure_actions = {
                'ResetPeriod': 864000,  # Time in ms after which to reset the failure count to zero.
                'RebootMsg': u'',  # Not using reboot option
                'Command': u'',  # Not using run-command option
                'Actions': [
                    (win32service.SC_ACTION_RESTART, 5000),  # action, delay in ms
                    (win32service.SC_ACTION_RESTART, 5000)
                ]
            }
            win32service.ChangeServiceConfig2(hs, win32service.SERVICE_CONFIG_FAILURE_ACTIONS, service_failure_actions)
        finally:
            if hs:
                win32service.CloseServiceHandle(hs)
    finally:
        if hscm:
            win32service.CloseServiceHandle(hscm)


def run() -> None:
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(UDSActorSvc)
        servicemanager.StartServiceCtrlDispatcher()
    elif sys.argv[1] == '--setup-recovery':
        setupRecoverService()
    else:
        win32serviceutil.HandleCommandLine(UDSActorSvc)
