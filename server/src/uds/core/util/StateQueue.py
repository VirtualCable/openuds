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

class StateQueue(object):
    
    def __init__(self):        
        self.reset()
        
    def __str__(self):
        res = '<StateQueue Current: %s, Queue: (%s)>' % (self._current , ','.join( state for state in self._queue ))
        return res
    
    def clearQueue(self):
        self._queue = []
    
    def reset(self):
        self._queue = []
        self._current = None
        
    def getCurrent(self):
        return self._current
        
    def setCurrent(self, newState):
        self._current = newState
        return self._current
        
    def contains(self, state):
        #if self._queue.co
        for s in self._queue:
            if s == state:
                return True
        return False
    
    def push_back(self, state):
        self._queue.append(state)
        
    def push_front(self, state):
        self._queue.insert(0, state)
        
    def pop_front(self):
        if len(self._queue) > 0:
            return self._queue.pop(0)
        return None
    
    def remove(self, state):
        try:
            self._queue.remove(state)
        except Exception:
            pass # If state not in queue, nothing happens
