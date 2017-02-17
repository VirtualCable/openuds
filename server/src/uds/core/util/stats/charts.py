# -*- coding: utf-8 -*-
#
# Copyright (c) 2013 Virtual Cable S.L.
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

import datetime
import cairo
import pycha.line
import time
import six

from uds.models import getSqlDatetime

import counters

# Chart types
CHART_TYPE_LINE, CHART_TYPE_AREA, CHART_TYPE_BAR = range(3)  # @UndefinedVariable

__typeTitles = None


def make(obj, counterType, **kwargs):

    width, height = (kwargs.get('width', 800), kwargs.get('height', 600))

    since = kwargs.get('since', None)
    to = kwargs.get('to', None)
    if since is None and to is None:
        interval = kwargs.get('interval', None)
        if interval is not None:
            to = getSqlDatetime()
            since = to - datetime.timedelta(days=interval)

    limit = width

    dataset1 = tuple((int(time.mktime(x[0].timetuple())), x[1]) for x in counters.getCounters(obj, counterType, since=since, to=to, limit=limit, use_max=kwargs.get('use_max', False)))

    if len(dataset1) == 0:
        dataset1 = ((getSqlDatetime(True) - 3600, 0), (getSqlDatetime(True), 0))

    firstLast = (dataset1[0][0], getSqlDatetime(True))

    xLabelFormat = '%y-%m-%d'
    diffInterval = firstLast[1] - firstLast[0]
    if diffInterval <= 60 * 60 * 24:  # Less than one day
        xLabelFormat = '%H:%M'
    elif diffInterval <= 60 * 60 * 24 * 7:
        xLabelFormat = '%A'

    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)

    dataset = ((counters.getCounterTitle(counterType).encode('iso-8859-1', errors='ignore'), dataset1),)

    options = {
        'axis': {
            'x': {
                'ticks': [dict(v=i, label=datetime.datetime.fromtimestamp(i).strftime(xLabelFormat)) for i in firstLast],
                'range': (firstLast[0], firstLast[1])
            },
            'y': {
                'tickCount': 4,
            }
        },
        'legend': {'hide': True},
        'background': {
            'chartColor': '#ffeeff',
            'baseColor': '#ffffff',
            'lineColor': '#444444'
        },
        'colorScheme': {
            'name': 'gradient',
            'args': {
                'initialColor': 'red',
            },
        },
        'legend': {
            'hide': True,
        },
        'padding': {
            'left': 0,
            'bottom': 0,
        },
        'title': 'Sample Chart'
    }

    chart = pycha.line.LineChart(surface, options)
    chart.addDataset(dataset)
    chart.render()

    output = six.StringIO()

    surface.write_to_png(output)

    return output.getvalue()
