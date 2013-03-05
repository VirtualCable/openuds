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

from uds.models import UniqueId as dbUniqueId
import logging

logger = logging.getLogger(__name__)

MAX_SEQ = 1000000000000000

class UniqueIDGenerator(object):
    
    def __init__(self, typeName, owner, baseName = 'uds'):
        self._owner = owner + typeName
        self._baseName = baseName
        
    def setBaseName(self, newBaseName):
        self._baseName = newBaseName
        
    def __filter(self, rangeStart, rangeEnd=MAX_SEQ):
        return dbUniqueId.objects.filter( basename = self._baseName, seq__gte=rangeStart, seq__lte=rangeEnd )
        
    def get(self, rangeStart=0, rangeEnd=MAX_SEQ):
        '''
        Tries to generate a new unique id in the range provided. This unique id
        is global to "unique ids' database
        '''
        # First look for a name in the range defined
        try:
            dbUniqueId.objects.lock()
            flt = self.__filter(rangeStart, rangeEnd)
            try:
                item = flt.filter(assigned=False).order_by('seq')[0]
                dbUniqueId.objects.filter(id=item.id).update( owner = self._owner, assigned = True )
                seq = item.seq
            except Exception, e: # No free element found
                try:
                    last = flt.filter(assigned = True)[0] # DB Returns correct order so the 0 item is the last
                    seq = last.seq + 1
                except Exception: # If there is no assigned at database
                    seq = rangeStart
                logger.debug('Found seq {0}'.format(seq))
                if seq > rangeEnd:
                    return -1 # No ids free in range
                dbUniqueId.objects.create( owner = self._owner, basename = self._baseName, seq = seq, assigned = True)
            return seq
        except Exception:
            logger.exception('Generating unique id sequence')
            return None
        finally:
            dbUniqueId.objects.unlock()

    def free(self, seq):
        try:
            logger.debug('Freeing seq {0} from {1}  ({2})'.format(seq, self._owner, self._baseName))
            dbUniqueId.objects.lock()
            flt = self.__filter(0).filter(owner = self._owner, seq=seq).update(owner='', assigned=False)
            if flt > 0:
                self.__purge()
        finally:
            dbUniqueId.objects.unlock()
        
            
    def __purge(self):
        try:
            last = self.__filter(0).filter(assigned=True)[0]
            seq = last.seq+1
        except:
            seq = 0
        self.__filter(seq).delete() # Clean ups all unassigned after last assigned in this range
        
    
    def release(self):
        try:
            dbUniqueId.objects.lock()
            dbUniqueId.objects.filter(owner=self._owner).update(assigned=False, owner='')
            self.__purge()
        finally:
            dbUniqueId.objects.unlock()
    