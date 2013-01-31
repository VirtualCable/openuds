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
from xmlrpclib import Fault

AUTH_CLASS = 0x1000
DATA_CLASS = 0x2000
ACTION_CLASS = 0x3000

FAIL = 0x0100

AUTH_FAILED = AUTH_CLASS | FAIL | 0x0001
DUPLICATE_FAIL = DATA_CLASS | FAIL | 0x0001
INSERT_FAIL = DATA_CLASS | FAIL | 0x0002
DELETE_FAIL = DATA_CLASS | FAIL | 0x0003
FIND_FAIL = DATA_CLASS | FAIL | 0x0004
VALIDATION_FAIL = DATA_CLASS | FAIL | 0x0005
PARAMETERS_FAIL = DATA_CLASS | FAIL | 0x0006
MODIFY_FAIL = DATA_CLASS | FAIL | 0x0007

PUBLISH_FAIL = ACTION_CLASS | FAIL | 0x0001

CANCEL_FAIL = ACTION_CLASS | FAIL | 0x0001

def AuthException(msg):
    return Fault(AUTH_FAILED, msg)

def DuplicateEntryException(msg):
    return Fault(DUPLICATE_FAIL, msg)

def InsertException(msg):
    return Fault(FIND_FAIL, msg)

def FindException(msg):
    return Fault()

def DeleteException(msg):
    return Fault(DELETE_FAIL, msg)

def ModifyException(msg):
    return Fault(MODIFY_FAIL, msg)

def PublicationException(msg):
    return Fault(PUBLISH_FAIL, msg)

def CancelationException(msg):
    return Fault(CANCEL_FAIL, msg)

def ValidationException(msg):
    return Fault(VALIDATION_FAIL, msg)

def ParametersException(msg):
    return Fault(PARAMETERS_FAIL, msg)