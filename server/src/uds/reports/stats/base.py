# -*- coding: utf-8 -*-

#
# Copyright (c) 2015-2019 Virtual Cable S.L.
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
from django.utils.translation import gettext_noop as _
from uds.core import reports, ui
from uds.core.util import dateutils
from ..auto import ReportAuto


class StatsReport(reports.Report):
    group = _('Statistics')  # So we can make submenus with reports

    # basic fields for most stats reports
    pool = ui.gui.MultiChoiceField(
        order=1,
        label=_('Pool'),
        tooltip=_('Pool for report'),
        required=True,
    )

    # pool or pools may be used, but not both
    pools = ui.gui.MultiChoiceField(
        order=1, label=_('Pools'), tooltip=_('Pools for report'), required=True
    )
    
    start_date = ui.gui.DateField(
        order=2,
        label=_('Starting date'),
        tooltip=_('starting date for report'),
        default=dateutils.start_of_month,
        required=True,
        old_field_name='startDate',
    )

    end_date = ui.gui.DateField(
        order=3,
        label=_('Finish date'),
        tooltip=_('finish date for report'),
        default=dateutils.tomorrow,
        required=True,
        old_field_name='endDate',
    )

    sampling_points = ui.gui.NumericField(
        order=4,
        label=_('Number of intervals'),
        length=3,
        min_value=0,
        max_value=32,
        tooltip=_('Number of sampling points used in charts'),
        default=8,
        old_field_name='samplingPoints',
    )

    def generate(self) -> bytes:
        raise NotImplementedError('StatsReport generate invoked and not implemented')


# pylint: disable=abstract-method
class StatsReportAuto(ReportAuto, StatsReport):
    pass
