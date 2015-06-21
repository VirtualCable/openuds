from geraldo.base import BAND_WIDTH, BAND_HEIGHT, Element
from geraldo.utils import cm, black
from geraldo import Image

import logging

logger = logging.getLogger(__name__)


class UDSImage(Image):
    def _get_height(self):
        logger.debug('get height called')
        ret = self._height or (self.image and self.image.size[1] or 0)
        return ret * cm / 118

    def _set_height(self, value):
        logger.debug('set height called')
        self._height = value / cm * 118

    height = property(_get_height, _set_height)

    def _get_width(self):
        logger.debug('get width called')
        ret = self._width or (self.image and self.image.size[0] or 0)
        return ret * cm / 118

    def _set_width(self, value):
        logger.debug('set width called')
        self._width = value / cm * 118

    width = property(_get_width, _set_width)
