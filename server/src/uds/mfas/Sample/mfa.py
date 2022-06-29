from re import T
import typing
import logging

from django.utils.translation import gettext_noop as _

from uds.core import mfas
from uds.core.ui import gui

if typing.TYPE_CHECKING:
    from uds.core.module import Module

logger = logging.getLogger(__name__)

class SampleMFA(mfas.MFA):
    typeName = _('Sample Multi Factor')
    typeType = 'sampleMFA'
    typeDescription = _('Sample Multi Factor Authenticator')
    iconFile = 'sample.png'

    useless = gui.CheckBoxField(
        label=_('Sample useless field'),
        order=90,
        tooltip=_(
            'This is a useless field, for sample and testing pourposes'
        ),
        tab=gui.ADVANCED_TAB,
        defvalue=gui.TRUE,
    )

    def initialize(self, values: 'Module.ValuesType') -> None:
        return super().initialize(values)

    def label(self) -> str:
        return 'Code is in log'
    
    def sendCode(self, userId: str, username: str, identifier: str, code: str) -> mfas.MFA.RESULT:
        logger.debug('Sending code: %s', code)
        return mfas.MFA.RESULT.OK

