# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2019 Virtual Cable S.L.
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
import io
import logging
import typing


from django.db import models
from django.db.models import signals
from django.http import HttpResponse

from PIL import Image as PILImage

from uds.models.uuid_model import UUIDModel
from uds.models.util import getSqlDatetime

from uds.core.util import encoders


logger = logging.getLogger(__name__)


class Image(UUIDModel):
    """
    Image storing on DB model
    This is intended for small images (i will limit them to 128x128), so storing at db is fine

    """
    MAX_IMAGE_SIZE = (128, 128)
    THUMBNAIL_SIZE = (48, 48)

    name = models.CharField(max_length=128, unique=True, db_index=True)
    stamp = models.DateTimeField()  # Date creation or validation of this entry. Set at write time
    data = models.BinaryField()  # Image storage
    thumb = models.BinaryField()  # Thumbnail, very small
    width = models.IntegerField(default=0)
    height = models.IntegerField(default=0)

    class Meta:
        """
        Meta class to declare the name of the table at database
        """
        db_table = 'uds_images'
        app_label = 'uds'

    @staticmethod
    def encode64(data: bytes) -> str:
        return typing.cast(str, encoders.encode(data, 'base64', asText=True)).replace('\n', '')  # Removes \n

    @staticmethod
    def decode64(data64: str) -> bytes:
        return typing.cast(bytes, encoders.decode(data64, 'base64'))

    @staticmethod
    def prepareForDb(data: bytes) -> bytes:
        try:
            stream = io.BytesIO(data)
            image = PILImage.open(stream)
        except Exception:  # Image data is incorrect, fix as a simple transparent image
            image = PILImage.new('RGBA', (128, 128))

        # Max image size, keeping aspect and using antialias
        image.thumbnail(Image.MAX_IMAGE_SIZE, PILImage.ANTIALIAS)
        output = io.BytesIO()
        image.save(output, 'png')
        return output.getvalue()

    @property
    def data64(self) -> str:
        """
        Returns the value of the image (data) as a base 64 encoded string
        """
        return Image.encode64(self.data)

    @data64.setter
    def data64(self, value: str):
        """
        Sets the value of image (data) from a base 64 encoded string
        """
        self.data = Image.decode64(value)

    @property
    def thumb64(self) -> str:
        """
        Returns the value of the image (data) as a base 64 encoded string
        """
        return Image.encode64(self.thumb)

    @thumb64.setter
    def thumb64(self, value: str):
        """
        Sets the value of image (data) from a base 64 encoded string
        """
        self.thumb = Image.decode64(value)

    @property
    def image(self) -> PILImage:
        """
        Returns an image (PIL Image)
        """
        try:
            data = io.BytesIO(self.data)
            return PILImage.open(data)
        except Exception:  # Image data is incorrect, fix as a simple transparent image
            return PILImage.new('RGBA', Image.MAX_IMAGE_SIZE)

    @property
    def size(self) -> typing.Tuple[int, int]:
        """
        Returns the image size
        """
        return self.width, self.height

    def updateThumbnail(self) -> None:
        thumb = self.image
        self.width, self.height = thumb.size
        thumb.thumbnail(Image.THUMBNAIL_SIZE, PILImage.ANTIALIAS)
        output = io.BytesIO()
        thumb.save(output, 'png')
        self.thumb = output.getvalue()

    def _processImageStore(self) -> None:
        self.data = Image.prepareForDb(self.data)
        self.updateThumbnail()

    def storeImageFromBinary(self, data) -> None:
        self.data = data
        self._processImageStore()

    def storeImageFromBase64(self, data64: str):
        """
        Stores an image, passed as base64 string, resizing it as necessary
        """
        self.data64 = data64
        self._processImageStore()

    def imageResponse(self) -> HttpResponse:
        return HttpResponse(self.data, content_type='image/png')

    def thumbnailResponse(self) -> HttpResponse:
        return HttpResponse(self.thumb, content_type='image/png')

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        self.stamp = getSqlDatetime()
        return super().save(force_insert, force_update, using, update_fields)

    def __str__(self):
        return 'Image id {}, name {}, {} bytes, {} bytes thumb'.format(self.id, self.name, len(self.data), len(self.thumb))

    @staticmethod
    def beforeDelete(sender, **kwargs):
        """
        Used to invoke the Service class "Destroy" before deleting it from database.

        In this case, this is a dummy method, waiting for something useful to do :-)

        :note: If destroy raises an exception, the deletion is not taken.
        """
        toDelete = kwargs['instance']

        logger.debug('Deleted image %s', toDelete)


signals.pre_delete.connect(Image.beforeDelete, sender=Image)
