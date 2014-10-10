# -*- coding: utf-8 -*-
#
# Copyright (c) 2014 Virtual Cable S.L.
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
from __future__ import unicode_literals


from win32com.shell import shell
import _winreg as wreg
import win32security
import cPickle

# Can be changed to whatever we want, but registry key is protected by permissions
def encoder(data):
    return data.encode('bz2')

def decoder(data):
    return data.decode('bz2')

DEBUG = True

path = 'Software\\UDSEnterpriseActor'
baseKey = wreg.HKEY_CURRENT_USER if DEBUG is True else wreg.HKEY_LOCAL_MACHINE

def checkPermissions():
    return True if DEBUG else shell.IsUserAnAdmin()

def fixRegistryPermissions(handle):
    if DEBUG:
        return
    # Fix permissions so users can't read this key
    v = win32security.GetSecurityInfo(handle, win32security.SE_REGISTRY_KEY, win32security.DACL_SECURITY_INFORMATION)
    dacl = v.GetSecurityDescriptorDacl()
    n = 0
    # Remove all normal users access permissions to the registry key
    while n < dacl.GetAceCount():
        if unicode(dacl.GetAce(n)[2]) == u'PySID:S-1-5-32-545':  # Whell known Users SID
            dacl.DeleteAce(n)
        else:
            n += 1
    win32security.SetSecurityInfo(handle, win32security.SE_REGISTRY_KEY,
                                  win32security.DACL_SECURITY_INFORMATION | win32security.PROTECTED_DACL_SECURITY_INFORMATION,
                                  None, None, dacl, None)

def readConfig():
    try:
        key = wreg.OpenKey(baseKey, path, 0, wreg.KEY_QUERY_VALUE)
        data, dataType = wreg.QueryValueEx(key, '')
        wreg.CloseKey(key)
        return cPickle.loads(decoder(data))
    except Exception as e:
        return None

def writeConfig(data):
    try:
        key = wreg.OpenKey(base, path, 0, wreg.KEY_ALL_ACCESS)
    except:
        key = wreg.CreateKeyEx(baseKey, path, 0, wreg.KEY_ALL_ACCESS)
        fixRegistryPermissions(key.handle)

    wreg.SetValueEx(key, "", 0, wreg.REG_BINARY, encoder(cPickle.dumps(data)))
    wreg.CloseKey(key)
