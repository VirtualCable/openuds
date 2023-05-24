#!/bin/bash


function process {
    for a in *.ui; do
        pyuic5 $a -o uds/ui/qt5/`basename $a .ui`.py --import-from=uds.ui.qt5
        pyuic6 $a -o uds/ui/qt6/`basename $a .ui`.py
    done
}    

pyrcc5 UDSResources.qrc -o uds/ui/qt5/UDSResources_rc.py
pyside6-rcc UDSResources.qrc -o uds/ui/qt6/UDSResources_rc.py

echo "Note: Qt6 does not include pyrcc6, so pyside6-rcc is used instead"
echo "Must modify uds/ui/qt6/UDSResources_rc.py to use PyQT6 instead of PySide6, and ensure it is loaded

# process current directory ui's
process

