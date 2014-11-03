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
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
'''
from __future__ import unicode_literals

from uds.core.util.Cache import Cache
from uds.core.managers import cryptoManager

TICKET_OWNER = 'e6242ba4-62fa-11e4-b7ec-10feed05884b'


class Ticket(object):
    '''
    Manages tickets & ticketing save/loading
    Right now, uses cache as backend
    '''

    def __init__(self, key=None):
        self.uuidGenerator = cryptoManager().uuid
        self.cache = Cache(TICKET_OWNER)
        self.data = None
        self.key = key
        if key is not None:
            self.load()
        else:
            self.key = self.uuidGenerator()

    def save(self, data, validity):
        '''
        Stores data inside ticket, and make data persistent (store in db)
        '''
        self.data = data
        self.cache.put(self.key, self.data, validity)
        return self.key

    def load(self):
        '''
        Load data (if still valid) for a ticket
        '''
        self.data = self.cache.get(self.key, None)
        return self.data

    def delete(self):
        '''
        Removes a ticket from storage (db)
        '''
        self.cache.remove(self.key)
