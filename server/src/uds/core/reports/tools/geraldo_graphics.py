from geraldo.base import BAND_WIDTH, BAND_HEIGHT, Element
from geraldo.utils import cm, black
from geraldo import Image

import logging

logger = logging.getLogger(__name__)


class UDSImage(Image):
    def _get_height(self):
        ret = self._height or (self.image and (self.image.size[1] * cm / 118) or 0)
        return ret

    def _set_height(self, value):
        self._height = value

    height = property(_get_height, _set_height)

    def _get_width(self):
        ret = self._width or (self.image and (self.image.size[0] * cm / 118) or 0)
        return ret

    def _set_width(self, value):
        self._width = value

    width = property(_get_width, _set_width)
