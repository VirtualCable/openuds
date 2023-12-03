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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import io
import typing
import collections.abc
import logging

from unittest.mock import Mock

from uds.core.reports import graphs

from ...utils.test import UDSTestCase

logger = logging.getLogger(__name__)


class GraphsTest(UDSTestCase):
    data1: dict[str, typing.Any]
    data2: dict[str, typing.Any]

    def setUp(self):
        # Data must be a dict with the following keys:
        #     - x: List of x values
        #     - y: List of dicts with the following keys:
        #         - data: List of y values
        #         - label: Label for the bar
        #     - title: Title of the chart
        #     - xlabel: Label for x axis
        #     - ylabel: Label for y axis
        #     - allTicks: If True, all x values will be shown as ticks
        #     - xtickFnc: Function to be used to format x ticks labels
        self.data1 = {
            'x': [1, 2, 3],
            'y': [
                {
                    'data': [1, 2, 3],
                    'label': 'Test',
                },
                {
                    'data': [1, 2, 3],
                    'label': 'Test2',
                },
                {
                    'data': [1, 2, 3],
                    'label': 'Test3',
                }
            ],
            'title': 'Test',
            'xlabel': 'X',
            'ylabel': 'Y',
            'allTicks': True,
            'xtickFnc': Mock()
        }
        # Data must be a dict with the following keys:
        #     - x: List of x values
        #     - y: List of y values
        #     - z: List of z values (must be a list of lists)
        #     - title: Title of the chart
        #     - xlabel: Label for x axis
        #     - ylabel: Label for y axis
        #     - zlabel: Label for z axis
        #     - allTicks: If True, all x values will be shown as ticks
        #     - xtickFnc: Function to be used to format x ticks labels from x ticks
        #     - ytickFnc: Function to be used to format y ticks labels form y ticks
        self.data2 = {
            'x': [1, 2, 3],
            'y': [1, 2, 3],
            'z': [
                [1, 2, 3],
                [1, 2, 3],
                [1, 2, 3]
            ],
            'title': 'Test',
            'xlabel': 'X',
            'ylabel': 'Y',
            'zlabel': 'Z',
            'allTicks': True,
            'xtickFnc': Mock(),
            'ytickFnc': Mock()
        }
        

    def test_bar_chart(self):
        output = io.BytesIO()
        graphs.barChart((10, 8, 96), data=self.data1, output=output)
        value = output.getvalue()
        self.assertGreater(len(value), 0)
        self.assertEqual(self.data1['xtickFnc'].call_count, 3)
        # Save to /tmp so we can check it
        with open('/tmp/bar.png', 'wb') as f:  # nosec: this is a test, we are not using a real file
            f.write(value)


    def test_line_chart(self):
        output = io.BytesIO()
        graphs.lineChart((10, 8, 96), data=self.data1, output=output)
        value = output.getvalue()
        self.assertGreater(len(value), 0)
        self.assertEqual(self.data1['xtickFnc'].call_count, 3)
        # Save to /tmp so we can check it
        with open('/tmp/line.png', 'wb') as f:  # nosec: this is a test, we are not using a real file
            f.write(value)


    def test_surface_chart(self):
        output = io.BytesIO()
        graphs.surfaceChart((10, 8, 96), data=self.data2, output=output)
        value = output.getvalue()
        self.assertGreater(len(value), 0)
        self.assertEqual(self.data2['xtickFnc'].call_count, 3)
        self.assertEqual(self.data2['ytickFnc'].call_count, 3)
        # Save to /tmp so we can check it
        with open('/tmp/surface.png', 'wb') as f:  # nosec: this is a test, we are not using a real file
            f.write(value)


    def test_surface_chart_wireframe(self):
        self.data2['wireframe'] = True
        output = io.BytesIO()
        graphs.surfaceChart((10, 8, 96), data=self.data2, output=output)
        value = output.getvalue()
        self.assertGreater(len(value), 0)
        self.assertEqual(self.data2['xtickFnc'].call_count, 3)
        self.assertEqual(self.data2['ytickFnc'].call_count, 3)
        # Save to /tmp so we can check it
        with open('/tmp/surface-wireframe.png', 'wb') as f:  # nosec: this is a test, we are not using a real file
            f.write(value)
