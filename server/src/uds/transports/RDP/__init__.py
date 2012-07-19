# -*- coding: utf-8 -*-

#
# Copyright (c) 2012 Virtual Cable S.L.
# All rights reserved.
#

'''
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''

from uds.core.transports.TransportsFactory import TransportsFactory
from uds.core.managers.UserPrefsManager import UserPrefsManager, CommonPrefs
from uds.transports.RDP.RDPTransport import RDPTransport
from uds.transports.RDP.TSRDPTransport import TSRDPTransport
from django.utils.translation import ugettext_noop as _

TransportsFactory.factory().insert(RDPTransport)
TransportsFactory.factory().insert(TSRDPTransport)
UserPrefsManager.manager().registerPrefs('rdp', _('Remote Desktop Protocol'), 
                                          [ 
                                           CommonPrefs.screenSizePref,
                                           CommonPrefs.depthPref
                                        ])