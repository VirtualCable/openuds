from uds.core.util import config as cfg

# Globals for messagging
DO_NOT_REPEAT = cfg.Config.section('Messaging').value('Not Repeat Minutes', '10')

# Ensure that we have a default value for this on startup
DO_NOT_REPEAT.getInt()
