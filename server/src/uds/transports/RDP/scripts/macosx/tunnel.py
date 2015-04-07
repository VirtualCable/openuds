# This is a template
# Saved as .py for easier editing
from __future__ import unicode_literals

# pylint: disable=import-error, no-name-in-module, too-many-format-args, undefined-variable, invalid-sequence-index
from PyQt4 import QtCore, QtGui
import subprocess
import os
import urllib
from uds.forward import forward  # @UnresolvedImport

from uds import tools  # @UnresolvedImport

import six

# First, try to locate  Remote Desktop Connection (version 2, from Microsoft website, not the app store one)
msrdc = '/Applications/Remote Desktop Connection.app/Contents/MacOS/Remote Desktop Connection'
cord = "/Applications/CoRD.app/Contents/MacOS/CoRD"

if os.path.isfile(msrdc):
    executable = msrdc
elif os.path.isfile(cord):
    executable = cord
else:
    executable = None


def onExit():
    import subprocess  # @Reimport
    subprocess.call(
        [
            'security',
             'delete-generic-password',
             '-a', '{username}',
             '-s', 'Remote Desktop Connection 2 Password for 127.0.0.1',
        ]
    )

if executable is None:
    QtGui.QMessageBox.critical(parent, 'Notice',  # @UndefinedVariable
                               '''<p><b>Microsoft Remote Desktop Connection not found</b></p>
<p>In order to connect to UDS RDP Sessions, you need to have at least one of the following:<p>
<ul>
    <li>
        <p><b>Microsoft Remote Desktop Connection version 2.</b> (Recommended)</p>
        <p>You can get it from <a href="http://www.microsoft.com/es-es/download/details.aspx?id=18140">this link</a></p>
        <p>Remember that you need to use the One from the Microsoft site (the link provided), not the one from the AppStore</p>
    </li>
    <li>
        <p><b>CoRD</b> (A bit unstable from 10.7 onwards)</p>
        <p>You can get it from <a href="{this_server}static/other/CoRD.pkg">this link</a></p>
    </li>
</ul>
<p>If both apps are installed, Remote Desktop Connection will be used as first option</p>

''', QtGui.QMessageBox.Ok)


forwardThread, port = forward('{tunHost}', '{tunPort}', '{tunUser}', '{tunPass}', '{server}', '{port}')

if forwardThread.status == 2:
    QtGui.QMessageBox.critical(parent, 'Error', 'Unable to open tunnel', QtGui.QMessageBox.Ok)  # @UndefinedVariable

else:
    theFile = '''{file}'''.format(
        address='127.0.0.1:{{}}'.format(port)
    )
    filename = tools.saveTempFile(theFile)
    tools.addFileToUnlink(filename)

    if executable == msrdc:
        try:
            if '{username}' != '' and '{password}' != '':
                subprocess.call(
                    [
                        'security',
                        'add-generic-password',
                        '-w', '{password}',
                        '-U',
                        '-a', '{username}',
                        '-s', 'Remote Desktop Connection 2 Password for 127.0.0.1'.format(port),
                        '-T', '/Applications/Remote Desktop Connection.app',
                    ]
                )
            # Call but do not wait for exit
            tools.addTaskToWait(subprocess.Popen([executable, filename]))
            tools.addExecBeforeExit(onExit)

            tools.addFileToUnlink(filename)
        except Exception as e:
            QtGui.QMessageBox.critical(parent, 'Notice', six.text_type(e), QtGui.QMessageBox.Ok)  # @UndefinedVariable
    else:  # CoRD
        url = 'rdp://'
        if '\\' in '{username}':
            username, domain = '{username}'.split('\\')
        else:
            username, domain = '{username}', ''

        if username != '':
            url += username
            if '{password}' != '':
                url += ':' + urllib.quote('{password}')
            url += '@'
        url += '127.0.0.1:3389/'
        if domain != '':
            url += domain

        url += '?screenDepth={r.bpp}'

        if {r.fullScreen}:  # @UndefinedVariable
            url += '&fullscreen=true'
        else:
            url += 'screenWidth={r.width}&screenHeight={r.height}'

        url += '&forwardAudio=' + '01'[{r.redirectAudio}]  # @UndefinedVariable

        if {r.redirectDrives}:  # @UndefinedVariable
            url += '&forwardDisks=true'

        if {r.redirectPrinters}:  # @UndefinedVariable
            url += '&forwardPrinters=true'

        tools.addTaskToWait(subprocess.Popen(['open', url]))
