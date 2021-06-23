# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2020 Virtual Cable S.L.U.
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

"""
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging

from django.db import models

from .user_service import UserService


logger = logging.getLogger(__name__)


class UserServiceProperty(models.Model):  # pylint: disable=too-many-public-methods
    """
    Properties for User Service.
    The value field is a Text field, so we can put whatever we want in it
    """

    name = models.CharField(max_length=128, db_index=True)
    value = models.TextField(default='')
    user_service = models.ForeignKey(
        UserService, on_delete=models.CASCADE, related_name='properties'
    )

    # "fake" declarations for type checking
    objects: 'models.BaseManager[UserServiceProperty]'

    class Meta:
        """
        Meta class to declare default order and unique multiple field index
        """

        db_table = 'uds__user_service_property'
        app_label = 'uds'
        constraints = [
            models.UniqueConstraint(fields=['name', 'user_service'], name='u_uprop_name_userservice')
        ]

    def __str__(self) -> str:
        return "Property of {}. {}={}".format(
            self.user_service.pk, self.name, self.value
        )
