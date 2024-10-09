# -*- coding: utf-8 -*-
#
# Copyright (c) 2022 Virtual Cable S.L.U.
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
"""
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import typing

from uds import models

# Counters so we can reinvoke the same method and generate new data
glob = {'user_id': 0, 'group_id': 0}


def createEmailNotifier(
    host: typing.Optional[str] = None,
    port: int = 0,
    username: typing.Optional[str] = None,
    password: typing.Optional[str] = None,
    fromEmail: typing.Optional[str] = None,
    toEmail: typing.Optional[str] = None,
    enableHtml: bool = False,
    security: typing.Optional[str] = None,
) -> models.Notifier:
    from uds.notifiers.email.notifier import EmailNotifier

    notifier = models.Notifier()
    notifier.name = 'Testing email notifier'
    notifier.comments = 'Testing email notifier'
    notifier.data_type = EmailNotifier.type_type
    instance: EmailNotifier = typing.cast(EmailNotifier, notifier.get_instance())
    # Fill up fields
    instance.hostname.value = (host or 'localhost') + (
        '' if port == 0 else ':' + str(port)
    )
    instance.username.value = username or ''
    instance.password.value = password or ''
    instance.from_email.value = fromEmail or 'from@email.com'
    instance.to_email.value = toEmail or 'to@email.com'
    instance.enable_html.value = enableHtml
    instance.security.value = security or 'none'
    # Save
    notifier.data = instance.serialize()
    notifier.save()

    return notifier
