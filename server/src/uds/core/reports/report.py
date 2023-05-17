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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import codecs
import datetime
import logging
import typing

from weasyprint import HTML, CSS, default_url_fetcher

from django.utils.translation import gettext, gettext_noop as _
from django.template import loader

from uds.core.ui import UserInterface, gui
from . import stock


logger = logging.getLogger(__name__)


class Report(UserInterface):
    mime_type: typing.ClassVar[
        str
    ] = 'application/pdf'  # Report returns pdfs by default, but could be anything else
    name: typing.ClassVar[str] = _('Base Report')  # Report name
    group: typing.ClassVar[str] = ''  # So we can "group" reports by kind?
    encoded: typing.ClassVar[
        bool
    ] = True  # If the report is mean to be encoded (binary reports as PDFs == True, text reports must be False so utf-8 is correctly threated
    uuid: typing.ClassVar[str] = ''

    description: str = _('Base report')  # Report description
    filename: str = (
        'file.pdf'  # Filename that will be returned as 'hint' on rest report request
    )

    @classmethod
    def translated_name(cls):
        """
        Helper to return translated report name
        """
        return gettext(cls.name)

    @classmethod
    def translated_description(cls):
        """
        Helper to return translated report description
        """
        return gettext(cls.description)

    @classmethod
    def translated_group(cls):
        """
        Helper to return translated report description
        """
        return gettext(cls.group)

    @classmethod
    def getUuid(cls):
        if cls.uuid is None:
            raise Exception(f'Class does not includes an uuid!!!: {cls}')
        return cls.uuid

    @staticmethod
    def asPDF(
        html: str,
        header: typing.Optional[str] = None,
        water: typing.Optional[str] = None,
        images: typing.Optional[typing.Dict[str, bytes]] = None,
    ) -> bytes:
        """
        Renders an html as PDF.
        Uses the "report.css" as stylesheet
        """

        # url fetcher for weasyprint
        def report_fetcher(
            url: str, timeout=10, ssl_context=None  # pylint: disable=unused-argument
        ) -> typing.Dict:
            logger.debug('Getting url for weasyprint %s', url)
            if url.startswith('stock://'):
                imagePath = stock.getStockImagePath(url[8:])
                with open(imagePath, 'rb') as f:
                    image = f.read()
                return {'string': image, 'mime_type': 'image/png'}

            if url.startswith('image://'):
                img: typing.Optional[bytes] = b''  # Empty image
                if images:
                    img = images.get(url[8:])
                    logger.debug('Getting image %s? %s', url[8:], img is not None)
                return {'string': img, 'mime_type': 'image/png'}

            return default_url_fetcher(url)

        with open(stock.getStockCssPath('report.css'), 'r', encoding='utf-8') as f:
            css = f.read()

        css = (
            css.replace("{header}", header or _('Report'))
            .replace('{page}', _('Page'))
            .replace('{of}', _('of'))
            .replace('{water}', water or 'UDS Report')
            .replace(
                '{printed}',
                _('Printed in {now:%Y, %b %d} at {now:%H:%M}').format(
                    now=datetime.datetime.now()
                ),
            )
        )

        h = HTML(string=html, url_fetcher=report_fetcher)
        c = CSS(string=css)

        return typing.cast(
            bytes, h.write_pdf(stylesheets=[c])
        )  # Return a new bytes object

    @staticmethod
    def templateAsPDF(templateName, dct, header=None, water=None, images=None) -> bytes:
        """
        Renders a template as PDF
        """
        t = loader.get_template(templateName)

        return Report.asPDF(t.render(dct), header=header, water=water, images=images)

    def __init__(self, values: gui.ValuesType = None):
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
        super().__init__(values)
        self.initialize(values)

    def initialize(self, values: typing.Optional[gui.ValuesType]):
        """
        Invoked just right after initializing report, so we avoid rewriting __init__
        if values is None, we are initializing an "new" element, if values is a dict, is the values
        that self has received on constructuon

        This can be or can be not overriden
        """

    def generate(self) -> bytes:
        """
        Generates the reports

        An string representing the report is to be expected to be returned

        this MUST be overriden
        """
        raise NotImplementedError()

    def generateEncoded(self) -> str:
        """
        Generated base 64 encoded report.
        Basically calls generate and encodes resuslt as base64
        """
        data = self.generate()
        if self.encoded:
            return codecs.encode(data, 'base64').decode().replace('\n', '')

        return typing.cast(str, data)

    def __str__(self):
        return f'Report {self.name} with uuid {self.uuid}'
