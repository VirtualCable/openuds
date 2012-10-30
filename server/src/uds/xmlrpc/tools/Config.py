# -*- coding: utf-8 -*-

#
# Copyright (c) 2012 Virtual Cable S.L.
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

'''
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''

from ..auths.AdminAuth import needs_credentials
from uds.core.util.Config import Config

import logging

logger = logging.getLogger(__name__)

@needs_credentials
def getConfiguration(credentials):
    res = []
    addCrypt = credentials.isAdmin
    for cfg in Config.enumerate():
        if cfg.isCrypted() is True and addCrypt is False:
            continue
        res.append( {'section': cfg.section(), 'key' : cfg.key(), 'value' : cfg.get(), 'crypt': cfg.isCrypted(), 'longText': cfg.isLongText() } )
    logger.debug('Configuration: {0}'.format(res))
    return res
        

@needs_credentials
def updateConfiguration(credentials, configuration):
    '''
    Configuration is an array of dicts containing 'section', 'key' and 'value' (crypt is in fact ignored, used the one from database)
    '''
    for cfg in configuration:
        Config.update( cfg['section'], cfg['key'], cfg['value'] )
    return True

# Registers XML RPC Methods
def registerConfigurationFunctions(dispatcher):
    dispatcher.register_function(getConfiguration, 'getConfiguration')
    dispatcher.register_function(updateConfiguration, 'updateConfiguration')
