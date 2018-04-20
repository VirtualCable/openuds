# -*- coding: utf-8 -*-

#
# Copyright (c) 2018 Virtual Cable S.L.
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

from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
import io


def barChart(size, data, output):
    data = {
        'x': [1, 2, 3, 4, 5, 6],
        'xticks': ['uno', 'dos', 'tres', 'cuatro', 'cinco', 'seis'],
        'xlabel': 'Data X',
        'y': [
            {
             'label': 'First',
             'data': [1, 2, 4, 8, 16, 32],
            },
            {
             'label': 'Second',
             'data': [31, 15, 7, 3, 1, 0],
            }
        ],
        'ylabel': 'Data YYYYY'
    }

    width = 0.35
    fig = Figure(figsize=(size[0], size[1]), dpi=size[2])

    axis = fig.add_subplot(1, 1, 1)

    xs = data['x']  # x axis
    xticks = [''] + [l for l in data['xticks']] + ['']  # Iterables
    ys = data['y']  # List of dictionaries

    bottom = [0] * len(ys[0]['data'])
    plts = []
    for y in ys:
        plts.append(axis.bar(xs, y['data'], width, bottom=bottom, label=y.get('label')))
        bottom = y['data']

    axis.set_xlabel(data['xlabel'])
    axis.set_ylabel(data['ylabel'])
    axis.set_xticklabels(xticks)
    axis.legend()

    canvas = FigureCanvas(fig)
    canvas.print_png(output)
