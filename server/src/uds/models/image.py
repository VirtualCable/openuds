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
# pyright: reportUnknownMemberType=false, reportAttributeAccessIssue=false,reportUnknownArgumentType=false
# mypy: disable-error-code="attr-defined, no-untyped-call"
import io
import base64
import logging
import typing


import PIL.Image

from django.db import models
from django.http import HttpResponse


from .uuid_model import UUIDModel
from uds.core.util.model import sql_now
from uds.core import consts

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

    class Meta:  # pyright: ignore
        """
        Meta class to declare the name of the table at database
        """

        db_table = 'uds_images'
        app_label = 'uds'

    @staticmethod
    def to_resized_png(image: PIL.Image.Image, size: tuple[int, int]) -> tuple[int, int, bytes]:
        """
        Resizes an image to the given size
        """
        image.thumbnail(size=size, resample=PIL.Image.Resampling.LANCZOS, reducing_gap=3.0)
        output = io.BytesIO()
        image.save(output, 'png')
        return (image.width, image.height, output.getvalue())

    @staticmethod
    def prepare_for_db(data: bytes) -> tuple[int, int, bytes]:
        try:
            stream = io.BytesIO(data)
            image = PIL.Image.open(stream)
        except Exception:  # Image data is incorrect, replace as a simple transparent image
            image = PIL.Image.new('RGBA', Image.MAX_IMAGE_SIZE)

        # Max image size, keeping aspect and using antialias
        return Image.to_resized_png(image, Image.MAX_IMAGE_SIZE)

    @property
    def data64(self) -> str:
        """
        Returns the value of the image (data) as a base 64 encoded string
        """
        return base64.b64encode(self.data).decode()

    @property
    def thumb64(self) -> str:
        """
        Returns the value of the image (data) as a base 64 encoded string
        """
        return base64.b64encode(self.thumb).decode()

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

    @image.setter
    def image(self, value: typing.Union[bytes, str, PIL.Image.Image]) -> None:
        """Set image from bytes, base64 string or PIL Image
        Bytes: raw data
        String: base64 encoded data
        Image: PIL Image

        Args:
            value (typing.Union[bytes, str, Image.Image]): Image data

        Raises:
            ValueError: Invalid image type

        Note:
            This method also creates the thumbnail
            Not saved to database until save() is called
        """
        data: bytes = b''
        if value:
            if isinstance(value, bytes):
                data = value
            elif isinstance(value, str):
                data = base64.b64decode(value)
            else:
                with io.BytesIO() as output:
                    value.save(output, format='PNG')
                    data = output.getvalue()

            self.width, self.height, self.data = Image.prepare_for_db(data)

            # Setup thumbnail
            with io.BytesIO(data) as input:
                with PIL.Image.open(input) as img:
                    img.thumbnail(Image.THUMBNAIL_SIZE, PIL.Image.LANCZOS)
                    with io.BytesIO() as output:
                        img.save(output, format='PNG')
                        self.thumb = output.getvalue()
        else:
            self.data = consts.images.DEFAULT_IMAGE
            self.thumb = consts.images.DEFAULT_THUMB

    @property
    def size(self) -> tuple[int, int]:
        """
        Returns the image size
        """
        return self.width, self.height

    @property
    def length(self) -> int:
        """
        Returns the image size
        """
        return len(self.data)

    def image_as_response(self) -> HttpResponse:
        return HttpResponse(self.data, content_type='image/png')

    def thumbnail_as_response(self) -> HttpResponse:
        return HttpResponse(self.thumb, content_type='image/png')

    def save(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        self.stamp = sql_now()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f'Image Id: {self.id}, Name: {self.name}, Size: {self.size}, Length: {len(self.data)} bytes, Thumb length: {len(self.thumb)} bytes'
