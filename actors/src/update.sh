#!/bin/bash


function process {
    pyuic4 about-dialog.ui -o about_dialog_ui.py -x
    pyuic4 message-dialog.ui -o message_dialog_ui.py -x
    pyuic4 setup-dialog.ui -o setup_dialog_ui.py -x
}    

pyrcc4 -py3 UDSActor.qrc -o UDSActor_rc.py


# process current directory ui's
process

