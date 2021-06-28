# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2021 Virtual Cable S.L.U.
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
from django.db import models


class TunnelToken(models.Model):
    """
    UDS Tunnel tokens on DB
    """

    username = models.CharField(max_length=128)
    ip_from = models.CharField(max_length=16)
    ip = models.CharField(max_length=16)
    hostname = models.CharField(max_length=128)

    token = models.CharField(max_length=48, db_index=True, unique=True)
    stamp = models.DateTimeField()  # Date creation or validation of this entry

    # "fake" declarations for type checking
    objects: 'models.BaseManager[TunnelToken]'

    class Meta:
        app_label = 'uds'
        constraints = [
            models.UniqueConstraint(fields=['ip', 'hostname'], name='tt_ip_hostname')
        ]
        

    def __str__(self):
        return '<TunnelToken {} created on {} by {} from {}/{}>'.format(
            self.token, self.stamp, self.username, self.ip, self.hostname
        )
