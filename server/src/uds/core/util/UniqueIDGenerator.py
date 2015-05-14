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
from __future__ import unicode_literals

from uds.models.UniqueId import UniqueId
from uds.models import getSqlDatetime
import logging

logger = logging.getLogger(__name__)

MAX_SEQ = 1000000000000000


class UniqueIDGenerator(object):

    def __init__(self, typeName, owner, baseName='uds'):
        self._owner = owner + typeName
        self._baseName = baseName

    def setBaseName(self, newBaseName):
        self._baseName = newBaseName

    def __filter(self, rangeStart, rangeEnd=MAX_SEQ):
        return UniqueId.objects.filter(basename=self._baseName, seq__gte=rangeStart, seq__lte=rangeEnd)  # @UndefinedVariable

    def get(self, rangeStart=0, rangeEnd=MAX_SEQ):
        '''
        Tries to generate a new unique id in the range provided. This unique id
        is global to "unique ids' database
        '''
        # First look for a name in the range defined
        stamp = getSqlDatetime(True)
        logger.debug(UniqueId)
        try:
            UniqueId.objects.lock()  # @UndefinedVariable
            flt = self.__filter(rangeStart, rangeEnd)
            try:
                item = flt.filter(assigned=False).order_by('seq')[0]
                UniqueId.objects.filter(id=item.id).update(owner=self._owner, assigned=True, stamp=stamp)  # @UndefinedVariable
                seq = item.seq
            except Exception:  # No free element found
                try:
                    last = flt.filter(assigned=True)[0]  # DB Returns correct order so the 0 item is the last
                    seq = last.seq + 1
                except Exception:  # If there is no assigned at database
                    seq = rangeStart
                logger.debug('Found seq {0}'.format(seq))
                if seq > rangeEnd:
                    return -1  # No ids free in range
                UniqueId.objects.create(owner=self._owner, basename=self._baseName, seq=seq, assigned=True, stamp=stamp)  # @UndefinedVariable
            logger.debug('Seq: {}'.format(seq))
            return seq
        except Exception:
            logger.exception('Generating unique id sequence')
            return None
        finally:
            UniqueId.objects.unlock()  # @UndefinedVariable

    def transfer(self, seq, toUidGen):
        try:
            UniqueId.objects.lock()  # @UndefinedVariable

            obj = UniqueId.objects.get(owner=self._owner, seq=seq)  # @UndefinedVariable
            obj.owner = toUidGen._owner
            obj.basename = toUidGen._baseName
            obj.stamp = getSqlDatetime(True)
            obj.save()

            return True
        except Exception:
            logger.exception('EXCEPTION AT transfer')
            return False
        finally:
            UniqueId.objects.unlock()  # @UndefinedVariable

    def free(self, seq):
        try:
            logger.debug('Freeing seq {0} from {1}  ({2})'.format(seq, self._owner, self._baseName))
            UniqueId.objects.lock()  # @UndefinedVariable
            flt = self.__filter(0).filter(owner=self._owner, seq=seq).update(owner='', assigned=False, stamp=getSqlDatetime(True))
            if flt > 0:
                self.__purge()
        finally:
            UniqueId.objects.unlock()  # @UndefinedVariable

    def __purge(self):
        try:
            last = self.__filter(0).filter(assigned=True)[0]
            seq = last.seq + 1
        except:
            seq = 0
        self.__filter(seq).delete()  # Clean ups all unassigned after last assigned in this range

    def release(self):
        try:
            UniqueId.objects.lock()  # @UndefinedVariable
            UniqueId.objects.filter(owner=self._owner).update(assigned=False, owner='', stamp=getSqlDatetime(True))  # @UndefinedVariable
            self.__purge()
        finally:
            UniqueId.objects.unlock()  # @UndefinedVariable

    def releaseOlderThan(self, stamp):
        stamp = getSqlDatetime(True)
        try:
            UniqueId.objects.lock()  # @UndefinedVariable
            UniqueId.objects.filter(owner=self._owner, stamp__lt=stamp).update(assigned=False, owner='', stamp=stamp)  # @UndefinedVariable
            self.__purge()
        finally:
            UniqueId.objects.unlock()  # @UndefinedVariable
