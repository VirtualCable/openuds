# -*- coding: utf-8 -*-

#
# Copyright (c) 2018-2021 Virtual Cable S.L.U.
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
# -*- coding: utf-8 -*-
"""
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""

import logging
import io
import typing
import collections.abc

from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib import cm

# This must be imported to allow 3d projections
from mpl_toolkits.mplot3d.axes3d import Axes3D  # pylint: disable=unused-import

import numpy as np

logger = logging.getLogger(__name__)


def barChart(
    size: typing.Tuple[float, float, int],
    data: typing.Mapping[str, typing.Any],
    output: io.BytesIO,
) -> None:
    """
    Generates a bar chart and stores it on output

    Args:
        size: Size of the chart (width, height, dpi) in inches
        data: Data to be used to generate the chart
        output: Output stream to store the chart

    Notes:
        Data must be a dict with the following keys:
            - x: List of x values
            - y: List of dicts with the following keys:
                - data: List of y values
                - label: Label for the bar
            - title: Title of the chart
            - xlabel: Label for x axis
            - ylabel: Label for y axis
            - allTicks: If True, all x values will be shown as ticks
            - xtickFnc: Function to be used to format x ticks labels

    Returns:
        None, writes the chart on output as png
    """
    d = data['x']
    ind = np.arange(len(d))
    ys = data['y']

    width = 0.60
    fig: Figure = Figure(figsize=(size[0], size[1]), dpi=size[2])  # type: ignore
    FigureCanvas(fig)  # Stores canvas on fig.canvas

    axis = fig.add_subplot(1, 1, 1)  # type: ignore
    axis.grid(color='r', linestyle='dotted', linewidth=0.1, alpha=0.5)

    bottom = np.zeros(len(ys[0]['data']))
    for y in ys:
        axis.bar(ind, y['data'], width, bottom=bottom, label=y.get('label'))
        bottom += np.array(y['data'])

    axis.set_title(data.get('title', ''))
    axis.set_xlabel(data['xlabel'])
    axis.set_ylabel(data['ylabel'])

    if data.get('allTicks', True):
        axis.set_xticks(ind)

    if 'xtickFnc' in data and data['xtickFnc']:
        axis.set_xticklabels([data['xtickFnc'](v) for v in axis.get_xticks()])

    axis.legend()

    fig.savefig(output, format='png', transparent=True)


def lineChart(
    size: typing.Tuple[float, float, int],
    data: typing.Mapping[str, typing.Any],
    output: io.BytesIO,
) -> None:
    """
    Generates a line chart and stores it on output

    Args:
        size: Size of the chart (width, height, dpi) in inches
        data: Data to be used to generate the chart
        output: Output stream to store the chart

    Notes:
        Data must be a dict with the following keys:
            - x: List of x valuesç
            - y: List of dicts with the following keys:
                - data: List of y values
                - label: Label for the line
            - title: Title of the chart
            - xlabel: Label for x axis
            - ylabel: Label for y axis
            - allTicks: If True, all x values will be shown as ticks
            - xtickFnc: Function to be used to format x ticks labels

    Returns:
        None, writes the chart on output as png
    """
    x = data['x']
    y = data['y']

    fig: Figure = Figure(figsize=(size[0], size[1]), dpi=size[2])  # type: ignore
    FigureCanvas(fig)  # Stores canvas on fig.canvas

    axis = fig.add_subplot(111)  # type: ignore
    axis.grid(color='r', linestyle='dotted', linewidth=0.1, alpha=0.5)

    for i in y:
        yy = i['data']
        axis.plot(x, yy, label=i.get('label'), marker='.', color='orange')
        axis.fill_between(x, yy, 0)

    axis.set_title(data.get('title', ''))
    axis.set_xlabel(data['xlabel'])
    axis.set_ylabel(data['ylabel'])

    if data.get('allTicks', True):
        axis.set_xticks(x)

    if 'xtickFnc' in data and data['xtickFnc']:
        axis.set_xticklabels([data['xtickFnc'](v) for v in axis.get_xticks()])

    axis.legend()

    fig.savefig(output, format='png', transparent=True)


def surfaceChart(
    size: typing.Tuple[float, float, int],
    data: typing.Mapping[str, typing.Any],
    output: io.BytesIO,
) -> None:
    """
    Generates a surface chart and stores it on output

    Args:
        size: Size of the chart (width, height, dpi) in inches
        data: Data to be used to generate the chart
        output: Output stream to store the chart

    Notes:
        Data must be a dict with the following keys:
            - x: List of x values
            - y: List of y values
            - z: List of z values, must be a bidimensional list
            - wireframe: If True, a wireframe will be shown
            - title: Title of the chart
            - xlabel: Label for x axis
            - ylabel: Label for y axis
            - zlabel: Label for z axis
            - allTicks: If True, all x values will be shown as ticks
            - xtickFnc: Function to be used to format x ticks labels from x ticks
            - ytickFnc: Function to be used to format y ticks labels form y ticks

    Returns:
        None, writes the chart on output as png
    """
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

    fig: Figure = Figure(figsize=(size[0], size[1]), dpi=size[2])  # type: ignore
    FigureCanvas(fig)  # Stores canvas on fig.canvas

    axis: typing.Any = fig.add_subplot(1, 1, 1, projection='3d')  # type: ignore
    # axis.grid(color='r', linestyle='dotted', linewidth=0.1, alpha=0.5)

    if data.get('wireframe', False):
        axis.plot_wireframe(
            x,
            y,
            z,
            rstride=1,
            cstride=1,
            cmap=cm.coolwarm,  # pylint: disable=no-member  # type: ignore
        )
    else:
        axis.plot_surface(
            x, y, z, rstride=1, cstride=1, cmap=cm.coolwarm  # type: ignore  # pylint: disable=no-member
        )

    axis.set_title(data.get('title', ''))
    axis.set_xlabel(data['xlabel'])
    axis.set_ylabel(data['ylabel'])
    axis.set_zlabel(data['zlabel'])

    if data.get('allTicks', True):
        axis.set_xticks(data['x'])
        axis.set_yticks(data['y'])

    if 'xtickFnc' in data and data['xtickFnc']:
        axis.set_xticklabels([data['xtickFnc'](v) for v in axis.get_xticks()])
    if 'xtickFnc' in data and data['ytickFnc']:
        axis.set_yticklabels([data['ytickFnc'](v) for v in axis.get_yticks()])

    fig.savefig(output, format='png', transparent=True)
