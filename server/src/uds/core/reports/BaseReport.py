# -*- coding: utf-8 -*-

#
# Copyright (c) 2015 Virtual Cable S.L.
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
from __future__ import unicode_literals

from django.utils.translation import ugettext, ugettext_noop as _
from django.template import loader

from uds.core.ui.UserInterface import UserInterface
from uds.core.util import encoders
from . import stock

from weasyprint import HTML, CSS, default_url_fetcher
from datetime import datetime

import logging
import six

logger = logging.getLogger(__name__)

__updated__ = '2018-02-08'


class Report(UserInterface):
    mime_type = 'application/pdf'  # Report returns pdfs by default, but could be anything else
    name = _('Base Report')  # Report name
    description = _('Base report')  # Report description
    filename = 'file.pdf'  # Filename that will be returned as 'hint' on rest report request
    group = ''  # So we can "group" reports by kind?
    encoded = True  # If the report is mean to be encoded (binary reports as PDFs == True, text reports must be False so utf-8 is correctly threated
    uuid = None

    @classmethod
    def translated_name(cls):
        """
        Helper to return translated report name
        """
        return ugettext(cls.name)

    @classmethod
    def translated_description(cls):
        """
        Helper to return translated report description
        """
        return ugettext(cls.description)

    @classmethod
    def translated_group(cls):
        """
        Helper to return translated report description
        """
        return ugettext(cls.group)

    @classmethod
    def getUuid(cls):
        if cls.uuid is None:
            raise Exception('Class does not includes an uuid!!!: {}'.format(cls))
        return cls.uuid

    @staticmethod
    def asPDF(html, header=None, water=None, images=None):
        """
        Renders an html as PDF.
        Uses the "report.css" as stylesheet
        """

        # url fetcher for weasyprint
        def report_fetcher(url):
            logger.debug('Getting url for weasyprint {}'.format(url))
            if url.startswith('stock://'):
                imagePath = stock.getStockImagePath(url[8:])
                with open(imagePath, 'rb') as f:
                    image = f.read()
                return dict(string=image,
                            mime_type='image/png')
            elif url.startswith('image://'):
                img = ''  # Empty image
                if isinstance(images, dict):
                    img = images.get(url[8:], None)
                    logger.debug('Getting image {}? {}'.format(url[8:], img is not None))
                return dict(string=img,
                            mime_type='image/png')
            else:
                return default_url_fetcher(url)

        with open(stock.getStockCssPath('report.css'), 'r') as f:
            css = f.read()

        css = (
            css.replace("{header}", _('Report') if  header is None else header)
                .replace('{page}', _('Page'))
                .replace('{of}', _('of'))
                .replace('{water}', 'UDS Report' if water is None else water)
                .replace('{printed}', _('Printed in {now:%Y, %b %d} at {now:%H:%M}').format(now=datetime.now()))
        )

        h = HTML(string=html, url_fetcher=report_fetcher)
        c = CSS(string=css)

        return h.write_pdf(stylesheets=[c])

    @staticmethod
    def templateAsPDF(templateName, dct, header=None, water=None, images=None):
        """
        Renders a template as PDF
        """
        t = loader.get_template(templateName)

        return Report.asPDF(t.render(dct), header=header, water=water, images=images)

    def __init__(self, values=None):
        """
        Do not forget to invoke this in your derived class using
        "super(self.__class__, self).__init__(values)".

        The values parameter is passed directly to UserInterface base.

        Values are passed to __initialize__ method. It this is not None,
        the values contains a dictionary of values received from administration gui,
        that contains the form data requested from user.

        If you override marshal, unmarshal and inherited UserInterface method
        valuesDict, you must also take account of values (dict) provided at the
        __init__ method of your class.
        """
        #
        UserInterface.__init__(self, values)
        self.initialize(values)

    def initialize(self, values):
        """
        Invoked just right after initializing report, so we avoid rewriting __init__
        if values is None, we are initializing an "new" element, if values is a dict, is the values
        that self has received on constructuon

        This can be or can be not overriden
        """
        pass

    def generate(self):
        """
        Generates the reports

        An string representing the report is to be expected to be returned

        this MUST be overriden
        """
        raise NotImplementedError()

    def generateEncoded(self):
        """
        Generated base 64 encoded report.
        Basically calls generate and encodes resuslt as base64
        """
        data = self.generate()
        if self.encoded:
            data = encoders.encode(data, 'base64', asText=True).replace('\n', '')

        return data

    def __str__(self):
        return 'Report {} with uuid {}'.format(self.name, self.uuid)
