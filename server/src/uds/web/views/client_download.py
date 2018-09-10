# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2016 Virtual Cable S.L.
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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
from __future__ import unicode_literals

from django.http import HttpResponse
from django.utils.translation import ugettext_noop

from django.shortcuts import render
from django.template import RequestContext

from uds.core.managers.UserPrefsManager import UserPrefsManager, CommonPrefs
from uds.core.auths.auth import webLoginRequired
from uds.core.ui import theme
from uds.core.util.OsDetector import desktopOss

import logging

logger = logging.getLogger(__name__)

__updated__ = '2018-09-10'

UserPrefsManager.manager().registerPrefs(
    '_uds',
    ugettext_noop('UDS Plugin preferences'),
    [
        CommonPrefs.bypassPluginDetectionPref
    ]
)


def client_downloads(request, os=None):
    """
    Download page for UDS plugins
    """
    if os not in desktopOss:
        os = request.os['OS']
    logger.debug('User: {}'.format(request.user))
    os = os.lower()
    return render(
        request,
        theme.template('download_client.html'),
        {'os': os, 'user': request.user}
    )


@webLoginRequired(admin=False)
def plugin_detection(request, detection):
    if detection != '0':
        detection = '1'
    UserPrefsManager.manager().setPreferenceForUser(request.user, '_uds', CommonPrefs.BYPASS_PREF, detection)
    return HttpResponse(content='', content_type='text/plain')
