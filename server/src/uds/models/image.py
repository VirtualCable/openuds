# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2023 Virtual Cable S.L.U.
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
import io
import codecs
import logging
import typing


import PIL.Image

from django.db import models
from django.http import HttpResponse


from .uuid_model import UUIDModel
from ..core.util.model import getSqlDatetime


logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from uds.models import ServicePool, MetaPool, ServicePoolGroup


class Image(UUIDModel):
    """
    Image storing on DB model
    This is intended for small images (i will limit them to 128x128), so storing at db is fine
    """

    MAX_IMAGE_SIZE = (
        256,
        256,
    )  # Previouslt mas image size was 128x128, but now we are going to limit it to 256x256
    THUMBNAIL_SIZE = (48, 48)

    name = models.CharField(max_length=128, unique=True, db_index=True)
    # Datetime creation or validation of this entry. Set at write time
    stamp = models.DateTimeField()
    data = models.BinaryField()  # Image storage
    thumb = models.BinaryField()  # Thumbnail, very small
    width = models.IntegerField(default=0)
    height = models.IntegerField(default=0)

    # "fake" declarations for type checking
    # objects: 'models.manager.RelatedManager["Image"]'

    deployedServices: 'models.manager.RelatedManager[ServicePool]'
    metaPools: 'models.manager.RelatedManager[MetaPool]'
    servicesPoolsGroup: 'models.manager.RelatedManager[ServicePoolGroup]'

    class Meta:  # pylint: disable=too-few-public-methods
        """
        Meta class to declare the name of the table at database
        """

        db_table = 'uds_images'
        app_label = 'uds'

    @staticmethod
    def encode64(data: bytes) -> str:
        return codecs.encode(data, 'base64').decode().replace('\n', '')

    @staticmethod
    def decode64(data64: str) -> bytes:
        return codecs.decode(data64.encode(), 'base64')

    @staticmethod
    def resizeAndConvert(
        image: PIL.Image.Image, size: typing.Tuple[int, int]
    ) -> typing.Tuple[int, int, bytes]:
        """
        Resizes an image to the given size
        """
        image.thumbnail(size=size, resample=PIL.Image.LANCZOS, reducing_gap=3.0)
        output = io.BytesIO()
        image.save(output, 'png')
        return (image.width, image.height, output.getvalue())

    @staticmethod
    def prepareForDb(data: bytes) -> typing.Tuple[int, int, bytes]:
        try:
            stream = io.BytesIO(data)
            image = PIL.Image.open(stream)
        except (
            Exception
        ):  # Image data is incorrect, replace as a simple transparent image
            image = PIL.Image.new('RGBA', (128, 128))

        # Max image size, keeping aspect and using antialias
        return Image.resizeAndConvert(image, Image.MAX_IMAGE_SIZE)

    @property
    def data64(self) -> str:
        """
        Returns the value of the image (data) as a base 64 encoded string
        """
        return Image.encode64(self.data)

    @data64.setter
    def data64(self, value: str) -> None:
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
    def thumb64(self, value: str) -> None:
        """
        Sets the value of image (data) from a base 64 encoded string
        """
        self.thumb = Image.decode64(value)

    @property
    def image(self) -> PIL.Image.Image:
        """
        Returns an image (PIL Image)
        """
        try:
            data = io.BytesIO(self.data)
            return PIL.Image.open(data)
        except Exception:  # Image data is incorrect, fix as a simple transparent image
            return PIL.Image.new('RGBA', Image.MAX_IMAGE_SIZE)

    @property
    def size(self) -> typing.Tuple[int, int]:
        """
        Returns the image size
        """
        return self.width, self.height

    def updateThumbnail(self) -> None:
        img = self.image
        _, _, self.thumb = Image.resizeAndConvert(img, Image.THUMBNAIL_SIZE)

    def _processImageStore(self) -> None:
        self.width, self.height, self.data = Image.prepareForDb(self.data)
        self.updateThumbnail()

    def storeImageFromBinary(self, data: bytes) -> None:
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

    def save(self, *args, **kwargs):
        self.stamp = getSqlDatetime()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'Image Id: {self.id}, Name: {self.name}, Size: {self.size}, Length: {len(self.data)} bytes, Thumb length: {len(self.thumb)} bytes'
