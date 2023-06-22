# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2023 Virtual Cable S.L.U.
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
#    * Neither the name of Virtual Cable S.L.U. nor the names of its contributors
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
Author: Adolfo Gómez, dkmaster at dkmon dot com
'''
from django.db import models

from .consts import MAX_IPV6_LENGTH, MAX_DNS_NAME_LENGTH


class ActorToken(models.Model):
    """
    UDS Actors tokens on DB
    """

    username = models.CharField(max_length=128)
    ip_from = models.CharField(max_length=MAX_IPV6_LENGTH)
    ip = models.CharField(max_length=MAX_IPV6_LENGTH)
    ip_version = models.IntegerField(default=4)  # Version of ip fields

    hostname = models.CharField(max_length=MAX_DNS_NAME_LENGTH)
    mac = models.CharField(max_length=128, db_index=True, unique=True)
    pre_command = models.CharField(max_length=255, blank=True, default='')
    post_command = models.CharField(max_length=255, blank=True, default='')
    runonce_command = models.CharField(max_length=255, blank=True, default='')
    log_level = models.IntegerField()

    token = models.CharField(max_length=48, db_index=True, unique=True)
    stamp = models.DateTimeField()  # Date creation or validation of this entry

    # New fields for 4.0, optional "custom" data, to be interpreted by specific code
    custom = models.TextField(blank=True, default='')

    class Meta:  # pylint: disable=too-few-public-methods
        app_label = 'uds'

    def __str__(self):
        return f'<ActorToken {self.token} created on {self.stamp} by {self.username} from {self.hostname}/{self.ip_from}>'
