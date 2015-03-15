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

__updated__ = '2015-03-10'

from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render_to_response

from uds.core.auths.auth import webLoginRequired
from uds.core.util.decorators import denyBrowsers

import io
import six

from geraldo import Report, landscape, ReportBand, ObjectValue, SystemField, BAND_WIDTH, Label
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_RIGHT, TA_CENTER

import logging

logger = logging.getLogger(__name__)


class TestReport(Report):
    title = 'Test report'
    author = 'UDS Enterprise'

    page_size = A4
    margin_left = 2 * cm
    margin_top = 0.5 * cm
    margin_right = 0.5 * cm
    margin_bottom = 0.5 * cm

    class band_detail(ReportBand):
        height = 0.5 * cm
        elements = (
            ObjectValue(attribute_name='id', left=0.5 * cm),
            ObjectValue(attribute_name='date_creation', left=3 * cm,
                        get_value=lambda instance: six.text_type(instance)),
        )

    class band_page_header(ReportBand):
        height = 1.3 * cm
        elements = [
            SystemField(expression='%(report_title)s', top=0.1 * cm, left=0, width=BAND_WIDTH,
                        style={'fontName': 'Helvetica-Bold', 'fontSize': 14, 'alignment': TA_CENTER}),
            Label(text="ID", top=0.8 * cm, left=0.5 * cm),
            Label(text=u"Creation Date", top=0.8 * cm, left=3 * cm),
            SystemField(expression=u'Page %(page_number)d of %(page_count)d', top=0.1 * cm,
                        width=BAND_WIDTH, style={'alignment': TA_RIGHT}),
        ]
        borders = {'bottom': True}

    class band_page_footer(ReportBand):
        height = 0.5 * cm
        elements = [
            Label(text='Geraldo Reports', top=0.1 * cm),
            SystemField(expression=u'Printed in %(now:%Y, %b %d)s at %(now:%H:%M)s', top=0.1 * cm,
                        width=BAND_WIDTH, style={'alignment': TA_RIGHT}),
        ]
        borders = {'top': True}


@denyBrowsers(browsers=['ie<9'])
@webLoginRequired(admin='admin')
def usage(request):
    pass
    # return HttpResponse(pdf, content_type='application/pdf')
