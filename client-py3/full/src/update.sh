#!/bin/bash


function process {
    for a in *.ui; do
        pyuic5 $a -o `basename $a .ui`.py -x
    done
}    

pyrcc5 UDSResources.qrc -o uds/ UDSResources_rc.py


# process current directory ui's
process

