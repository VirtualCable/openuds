#!/bin/bash


function process {
    for a in *.ui; do
        pyuic4 $a -o `basename $a .ui`.py -x
    done
}    

pyrcc4 -py3 UDSResources.qrc -o UDSResources_rc.py


# process current directory ui's
process

