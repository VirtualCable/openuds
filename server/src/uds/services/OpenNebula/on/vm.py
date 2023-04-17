# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2019 Virtual Cable S.L.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright notice,
#      this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright notice,
#      this list of conditions and the following disclaimer in the documentation
#      and/or other materials provided with the distribution.
#    * Neither the name of Virtual Cable S.L. nor the names of its contributors
#      may be used to endorse or promote products derived from this software
#      without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

'''
Author: Adolfo Gómez, dkmaster at dkmon dot com
'''
import logging
import typing

from defusedxml import minidom

from . import types

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from . import client

logger = logging.getLogger(__name__)


def getMachineState(api: 'client.OpenNebulaClient', machineId: str) -> types.VmState:
    '''
    Returns the state of the machine
    This method do not uses cache at all (it always tries to get machine state from OpenNebula server)

    Args:
        machineId: Id of the machine to get state

    Returns:
        one of the on.VmState Values
    '''
    try:
        return api.getVMState(machineId)
    except Exception as e:
        logger.error(
            'Error obtaining machine state for %s on OpenNebula: %s', machineId, e
        )

    return types.VmState.UNKNOWN


def getMachineSubstate(api: 'client.OpenNebulaClient', machineId: str) -> int:
    '''
    Returns the lcm_state
    '''
    try:
        return api.getVMSubstate(machineId)
    except Exception as e:
        logger.error(
            'Error obtaining machine substate for %s on OpenNebula: %s', machineId, e
        )

    return types.VmState.UNKNOWN.value


def startMachine(api: 'client.OpenNebulaClient', machineId: str) -> None:
    '''
    Tries to start a machine. No check is done, it is simply requested to OpenNebula.

    This start also "resume" suspended/paused machines

    Args:
        machineId: Id of the machine

    Returns:
    '''
    try:
        api.VMAction(machineId, 'resume')
    except Exception:
        # MAybe the machine is already running. If we get error here, simply ignore it for now...
        pass


def stopMachine(api: 'client.OpenNebulaClient', machineId: str) -> None:
    '''
    Tries to start a machine. No check is done, it is simply requested to OpenNebula

    Args:
        machineId: Id of the machine

    Returns:
    '''
    try:
        api.VMAction(machineId, 'poweroff-hard')
    except Exception as e:
        logger.error('Error powering off %s on OpenNebula: %s', machineId, e)


def suspendMachine(api: 'client.OpenNebulaClient', machineId: str) -> None:
    '''
    Tries to suspend a machine. No check is done, it is simply requested to OpenNebula

    Args:
        machineId: Id of the machine

    Returns:
    '''
    try:
        api.VMAction(machineId, 'suspend')
    except Exception as e:
        logger.error('Error suspending %s on OpenNebula: %s', machineId, e)


def shutdownMachine(api: 'client.OpenNebulaClient', machineId: str) -> None:
    '''
    Tries to "gracefully" shutdown a machine. No check is done, it is simply requested to OpenNebula

    Args:
        machineId: Id of the machine

    Returns:
    '''
    try:
        api.VMAction(machineId, 'poweroff')
    except Exception as e:
        logger.error('Error shutting down %s on OpenNebula: %s', machineId, e)


def resetMachine(api: 'client.OpenNebulaClient', machineId: str) -> None:
    '''
    Tries to suspend a machine. No check is done, it is simply requested to OpenNebula

    Args:
        machineId: Id of the machine

    Returns:
    '''
    try:
        api.VMAction(machineId, 'reboot-hard')
    except Exception as e:
        logger.error('Error reseting %s on OpenNebula: %s', machineId, e)


def removeMachine(api: 'client.OpenNebulaClient', machineId: str) -> None:
    '''
    Tries to delete a machine. No check is done, it is simply requested to OpenNebula

    Args:
        machineId: Id of the machine

    Returns:
    '''
    try:
        # vm = oca.VirtualMachine.new_with_id(api, int(machineId))
        # vm.delete()
        api.deleteVM(machineId)
    except Exception as e:
        err = 'Error removing machine {} on OpenNebula: {}'.format(machineId, e)
        logger.exception(err)
        raise Exception(err)


def enumerateMachines(
    api: 'client.OpenNebulaClient',
) -> typing.Iterable[types.VirtualMachineType]:
    '''
    Obtains the list of machines inside OpenNebula.
    Machines starting with UDS are filtered out

    Args:
        force: If true, force to update the cache, if false, tries to first
        get data from cache and, if valid, return this.

    Returns
        An array of dictionaries, containing:
            'name'
            'id'
            'cluster_id'
    '''
    yield from api.enumVMs()


def getNetInfo(
    api: 'client.OpenNebulaClient',
    machineId: str,
    networkId: typing.Optional[str] = None,
) -> typing.Tuple[str, str]:
    '''
    Get the MAC and the IP for the network and machine. If network is None, for the first network
    '''
    # md = minidom.parseString(api.call('vm.info', int(machineId)))
    md = minidom.parseString(api.VMInfo(machineId).xml)
    node = md

    try:
        for nic in md.getElementsByTagName('NIC'):
            netId = nic.getElementsByTagName('NETWORK_ID')[0].childNodes[0].data
            if networkId is None or int(netId) == int(networkId):
                node = nic
                break
    except Exception:
        raise Exception(
            'No network interface found on template. Please, add a network and republish.'
        )

    logger.debug(node.toxml())

    # Default, returns first MAC found (or raise an exception if there is no MAC)
    try:
        try:
            ip = node.getElementsByTagName('IP')[0].childNodes[0].data
        except Exception:
            ip = ''

        return (node.getElementsByTagName('MAC')[0].childNodes[0].data, ip)
    except Exception:
        raise Exception(
            'No network interface found on template. Please, add a network and republish.'
        )


def getDisplayConnection(
    api: 'client.OpenNebulaClient', machineId: str
) -> typing.Optional[typing.Dict[str, typing.Any]]:
    '''
    If machine is not running or there is not a display, will return NONE
    SPICE connections should check that 'type' is 'SPICE'
    '''
    md = minidom.parseString(api.VMInfo(machineId).xml)
    try:
        graphics = md.getElementsByTagName('GRAPHICS')[0]

        type_ = graphics.getElementsByTagName('TYPE')[0].childNodes[0].data
        port = graphics.getElementsByTagName('PORT')[0].childNodes[0].data
        try:
            passwd = graphics.getElementsByTagName('PASSWD')[0].childNodes[0].data
        except Exception:
            passwd = ''

        host = (
            md.getElementsByTagName('HISTORY_RECORDS')[0]
            .lastChild.getElementsByTagName('HOSTNAME')[0]
            .childNodes[0]
            .data
        )
        return {'type': type_, 'host': host, 'port': int(port), 'passwd': passwd}

    except Exception:
        return None  # No SPICE connection


# Sample NIC Content (there will be as much as nics)
#         <NIC>
#             <BRIDGE><![CDATA[br0]]></BRIDGE>
#             <CLUSTER_ID><![CDATA[100]]></CLUSTER_ID>
#             <IP><![CDATA[172.27.0.49]]></IP>
#             <IP6_LINK><![CDATA[fe80::400:acff:fe1b:31]]></IP6_LINK>
#             <MAC><![CDATA[02:00:ac:1b:00:31]]></MAC>
#             <NETWORK><![CDATA[private]]></NETWORK>
#             <NETWORK_ID><![CDATA[1]]></NETWORK_ID>
#             <NETWORK_UNAME><![CDATA[oneadmin]]></NETWORK_UNAME>
#             <NIC_ID><![CDATA[2]]></NIC_ID>
#             <VLAN><![CDATA[NO]]></VLAN>
#         </NIC>
