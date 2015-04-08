# This is a template
# Saved as .py for easier editing
from __future__ import unicode_literals

# pylint: disable=import-error, no-name-in-module, too-many-format-args, undefined-variable, invalid-sequence-index
from PyQt4 import QtCore, QtGui
import subprocess
import os
import re

from uds import tools  # @UnresolvedImport

import six


def execOldXFreeRdp(parent, xfreerdp):
    QtGui.QMessageBox.critical(parent, 'Notice', 'Old xfreerdp', QtGui.QMessageBox.Ok)  # @UndefinedVariable


def execNewXFreeRdp(parent, xfreerdp):
    import subprocess
    params = [xfreerdp] + {m.r.as_new_xfreerdp_params}  # @UndefinedVariable
    tools.addTaskToWait(subprocess.Popen(params))


def execRdesktop(parent, rdesktop):
    return

# Try to locate a "valid" version of xfreerdp as first option
xfreerdp = tools.findApp('xfreerdp')
if xfreerdp is not None:
    # Check for nice version
    try:
        version = subprocess.check_output([xfreerdp, '--version'])
        version = float(re.search(r'version ([0-9]*\.[0-9]*)', version).groups()[0])
        if version < 1.0:
            raise Exception()
        if version < 1.1:
            execOldXFreeRdp(parent, xfreerdp)  # @UndefinedVariable
        else:
            execNewXFreeRdp(parent, xfreerdp)  # @UndefinedVariable

    except Exception as e:  # Valid version not found, pass to check rdesktop
        QtGui.QMessageBox.critical(parent, 'Notice', six.text_type(e), QtGui.QMessageBox.Ok)  # @UndefinedVariable
        pass
else:
    rdesktop = tools.findApp('rdesktop')
    if rdesktop is None:
        raise Exception('You need to have installed xfreerdp or rdesktop to connect to theese UDS services.\nPlease, install apropiate package for your system.')
