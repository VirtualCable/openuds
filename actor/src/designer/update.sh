#!/bin/bash


function process {
#    pyuic4 about-dialog.ui -o about_dialog_ui.py -x
#    pyuic4 message-dialog.ui -o message_dialog_ui.py
    pyuic5 setup-dialog.ui -o ../ui/setup_dialog_ui.py --import-from=ui
    pyuic5 setup-dialog-unmanaged.ui -o ../ui/setup_dialog_unmanaged_ui.py --import-from=ui
}    

pyrcc5 uds.qrc -o ../ui/uds_rc.py


# process current directory ui's
process

