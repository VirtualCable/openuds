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
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
'''

from __future__ import unicode_literals

__updated__ = '2014-11-04'

from django.db import models
from uds.models.UUIDModel import UUIDModel
from uds.models.Util import getSqlDatetime
from PIL import Image as PILImage  # @UnresolvedImport
import io


import base64
import logging

logger = logging.getLogger(__name__)


class Image(UUIDModel):
    '''
    Image storing on DB model
    This is intended for small images (i will limit them to 128x128), so storing at db is fine

    '''
    MAX_IMAGE_SIZE = (128, 128)

    name = models.CharField(max_length=128, unique=True, db_index=True)
    stamp = models.DateTimeField()  # Date creation or validation of this entry. Set at write time
    data = models.BinaryField()  # Image storage

    class Meta:
        '''
        Meta class to declare the name of the table at database
        '''
        db_table = 'uds_images'
        app_label = 'uds'

    def _storePILImage(self, image):
        '''
        Internal method
        Stores an image inside data field
        '''
        output = io.BytesIO()
        image.save(output, b'png')
        self.data = output.getvalue()

    @property
    def data64(self):
        '''
        Returns the value of the image (data) as a base 64 encoded string
        '''
        return base64.encodestring(self.data)[:-1]  # Removes trailing \n

    @data64.setter
    def data64(self, value):
        '''
        Sets the value of image (data) from a base 64 encoded string
        '''
        self.data = base64.decodestring(value)

    @property
    def image(self):
        '''
        Returns an image (PIL Image)
        '''
        try:
            data = io.BytesIO(self.data)
            return PILImage.open(data)
        except Exception:  # Image data is incorrect, fix as a simple transparent image
            return PILImage.new('RGBA', (128, 128))

    @property
    def size(self):
        '''
        Returns the image size
        '''
        return self.image.size

    def storeImageFromBase64(self, data64):
        '''
        Stores an image, passed as base64 string, resizing it as necessary
        '''
        self.data64 = data64
        image = self.image
        # Max image size, keeping aspect and using antialias
        image.thumbnail(Image.MAX_IMAGE_SIZE, PILImage.ANTIALIAS)
        self._storePILImage(image)

    def save(self, *args, **kwargs):
        self.stamp = getSqlDatetime()
        return UUIDModel.save(self, *args, **kwargs)

    def __unicode__(self):
        return 'Image "{}", {} bytes'.format(self.name, len(self.data))
