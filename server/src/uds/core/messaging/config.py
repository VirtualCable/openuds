from django.utils.translation import gettext_lazy as _

from uds.core.util import config as cfg

# Globals for messagging
DO_NOT_REPEAT = cfg.Config.section('Messaging').value(
    'Uniqueness',
    '10',
    help=_('Number of seconds to ignore repeated messages'),
    type=cfg.Config.FieldType.NUMERIC,
)

# Ensure that we have a default value for this on startup
DO_NOT_REPEAT.getInt()
