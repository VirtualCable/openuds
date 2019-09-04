# -*- coding: utf-8 -*-

#
# Copyright (c) 2018-2019 Virtual Cable S.L.
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
# -*- coding: utf-8 -*-
"""
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
"""

import logging
import typing

from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib import cm
# This must be imported to allow 3d projections
from mpl_toolkits.mplot3d import Axes3D  # pylint: disable=unused-import

import numpy as np

logger = logging.getLogger(__name__)


def barChart(size: typing.Tuple[int, int, int], data: typing.Dict, output: typing.BinaryIO):
    d = data['x']
    ind = np.arange(len(d))
    ys = data['y']

    width = 0.60
    fig = Figure(figsize=(size[0], size[1]), dpi=size[2])
    FigureCanvas(fig)  # Stores canvas on fig.canvas

    axis = fig.add_subplot(111)
    axis.grid(color='r', linestyle='dotted', linewidth=0.1, alpha=0.5)

    bottom = np.zeros(len(ys[0]['data']))
    for y in ys:
        axis.bar(ind, y['data'], width, bottom=bottom, label=y.get('label'))
        bottom += np.array(y['data'])

    axis.set_title(data.get('title', ''))
    axis.set_xlabel(data['xlabel'])
    axis.set_ylabel(data['ylabel'])

    if data.get('allTicks', True) is True:
        axis.set_xticks(ind)

    if 'xtickFnc' in data:
        axis.set_xticklabels([data['xtickFnc'](v) for v in axis.get_xticks()])

    axis.legend()

    fig.savefig(output, format='png', transparent=True)


def lineChart(size: typing.Tuple[int, int, int], data: typing.Dict, output: typing.BinaryIO):
    x = data['x']
    y = data['y']

    fig = Figure(figsize=(size[0], size[1]), dpi=size[2])
    FigureCanvas(fig)  # Stores canvas on fig.canvas

    axis = fig.add_subplot(111)
    axis.grid(color='r', linestyle='dotted', linewidth=0.1, alpha=0.5)

    for i in y:
        yy = i['data']
        axis.plot(x, yy, label=i.get('label'), marker='.', color='orange')
        axis.fill_between(x, yy, 0)

    axis.set_title(data.get('title', ''))
    axis.set_xlabel(data['xlabel'])
    axis.set_ylabel(data['ylabel'])

    if data.get('allTicks', True) is True:
        axis.set_xticks(x)

    if 'xtickFnc' in data:
        axis.set_xticklabels([data['xtickFnc'](v) for v in axis.get_xticks()])

    axis.legend()

    fig.savefig(output, format='png', transparent=True)


def surfaceChart(size: typing.Tuple[int, int, int], data: typing.Dict, output: typing.BinaryIO):
    x = data['x']
    y = data['y']
    z = data['z']

    logger.debug('X: %s', x)
    logger.debug('Y: %s', y)
    logger.debug('Z: %s', z)

    x, y = np.meshgrid(x, y)
    z = np.array(z)

    logger.debug('X\': %s', x)
    logger.debug('Y\': %s', y)
    logger.debug('Z\': %s', z)

    fig = Figure(figsize=(size[0], size[1]), dpi=size[2])
    FigureCanvas(fig)  # Stores canvas on fig.canvas

    axis = fig.add_subplot(111, projection='3d')
    # axis.grid(color='r', linestyle='dotted', linewidth=0.1, alpha=0.5)

    if data.get('wireframe', False) is True:
        axis.plot_wireframe(x, y, z, rstride=1, cstride=1, cmap=cm.coolwarm)  # @UndefinedVariable
    else:
        axis.plot_surface(x, y, z, rstride=1, cstride=1, cmap=cm.coolwarm)  # @UndefinedVariable

    axis.set_title(data.get('title', ''))
    axis.set_xlabel(data['xlabel'])
    axis.set_ylabel(data['ylabel'])
    axis.set_zlabel(data['zlabel'])

    if data.get('allTicks', True) is True:
        axis.set_xticks(data['x'])
        axis.set_yticks(data['y'])

    if 'xtickFnc' in data:
        axis.set_xticklabels([data['xtickFnc'](v) for v in axis.get_xticks()])
    if 'ytickFnc' in data:
        axis.set_yticklabels([data['ytickFnc'](v) for v in axis.get_yticks()])

    fig.savefig(output, format='png', transparent=True)
