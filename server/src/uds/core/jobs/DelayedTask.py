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

from uds.core.Environment import Environmentable
import logging

__updated__ = '2014-02-19'

logger = logging.getLogger(__name__)


class DelayedTask(Environmentable):
    def __init__(self):
        '''
        Remember to invoke parent init in derived clases using super(myClass,self).__init__() to let this initialize its own variables
        '''
        Environmentable.__init__(self, None)

    def execute(self):
        try:
            self.run()
        except Exception, e:
            logger.error('Job {0} raised an exception: {1}'.format(self.__class__, e))

    def run(self):
        '''
        You must provide your own "run" method to do whatever you need
        '''
        logging.debug("Base run of job called for class")

    def register(self, suggestedTime, tag='', check=True):
        '''
        Utility method that allows to register a Delayedtask
        '''
        from DelayedTaskRunner import DelayedTaskRunner

        if check is True and DelayedTaskRunner.runner().checkExists(tag):
            return

        DelayedTaskRunner.runner().insert(self, suggestedTime, tag)
