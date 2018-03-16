# -*- coding: utf-8 -*-

#
# Copyright (c) 2014 Virtual Cable S.L.
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
from __future__ import unicode_literals

import six
import XenAPI
import xmlrpclib
import ssl

import logging

logger = logging.getLogger(__name__)

TAG_TEMPLATE = "uds-template"
TAG_MACHINE = "uds-machine"


class XenFault(Exception):
    pass


class XenFailure(XenAPI.Failure, XenFault):
    exBadVmPowerState = 'VM_BAD_POWER_STATE'
    exVmMissingPVDrivers = 'VM_MISSING_PV_DRIVERS'
    exHandleInvalid = 'HANDLE_INVALID'
    exHostIsSlave = 'HOST_IS_SLAVE'
    exSRError = 'SR_BACKEND_FAILURE_44'
    exHandleInvalid = 'HANDLE_INVALID'

    def __init__(self, details=None):
        details = [] if details is None else details
        super(XenFailure, self).__init__(details)

    def isHandleInvalid(self):
        return self.details[0] == XenFailure.exHandleInvalid

    def needsXenTools(self):
        return self.details[0] == XenFailure.exVmMissingPVDrivers

    def badPowerState(self):
        return self.details[0] == XenFailure.exBadVmPowerState

    def isSlave(self):
        return self.details[0] == XenFailure.exHostIsSlave

    def asHumanReadable(self):
        try:
            errList = {
                XenFailure.exBadVmPowerState: 'Machine state is invalid for requested operation (needs {2} and state is {3})',
                XenFailure.exVmMissingPVDrivers: 'Machine needs Xen Server Tools to allow requested operation',
                XenFailure.exHandleInvalid: 'Invalid handler',
                XenFailure.exHostIsSlave: 'The connected host is an slave, try to connect to {1}',
                XenFailure.exSRError: 'Error on SR: {2}',
                XenFailure.exHandleInvalid: 'Invalid reference to {1}',
            }
            err = errList.get(self.details[0], 'Error {0}')

            return err.format(*self.details)
        except Exception:
            return 'Unknown exception: {0}'.format(self.details)

    def __unicode__(self):
        return self.asHumanReadable()


class XenException(XenFault):

    def __init__(self, message):
        XenFault.__init__(self, message)
        logger.debug('Exception create: {0}'.format(message))


class XenPowerState(object):
    halted = 'Halted'
    running = 'Running'
    suspended = 'Suspended'
    paused = 'Paused'


class XenServer(object):

    def __init__(self, host, port, username, password, useSSL=False, verifySSL=False):
        self._originalHost = self._host = host
        self._port = unicode(port)
        self._useSSL = useSSL and True or False
        self._verifySSL = verifySSL and True or False
        self._protocol = 'http' + (self._useSSL and 's' or '') + '://'
        self._url = None
        self._loggedIn = False
        self._username = username
        self._password = password
        self._session = None
        self._poolName = self._apiVersion = ''

    @staticmethod
    def toMb(number):
        return int(number) / (1024 * 1024)

    def checkLogin(self):
        if self._loggedIn is False:
            self.login()
        return self._loggedIn

    def getXenapiProperty(self, prop):
        if self.checkLogin() is False:
            raise Exception("Can't log in")
        return getattr(self._session.xenapi, prop)

    # Properties to fast access XenApi classes
    Async = property(lambda self: self.getXenapiProperty('Async'))
    task = property(lambda self: self.getXenapiProperty('task'))
    VM = property(lambda self: self.getXenapiProperty('VM'))
    SR = property(lambda self: self.getXenapiProperty('SR'))
    pool = property(lambda self: self.getXenapiProperty('pool'))
    host = property(lambda self: self.getXenapiProperty('host'))
    network = property(lambda self: self.getXenapiProperty('network'))
    VIF = property(lambda self: self.getXenapiProperty('VIF'))  # Virtual Interface
    VDI = property(lambda self: self.getXenapiProperty('VDI'))  # Virtual Disk Image
    VBD = property(lambda self: self.getXenapiProperty('VBD'))  # Virtual Block Device

    # Properties to access private vars
    poolName = property(lambda self: self.checkLogin() and self._poolName)
    hasPool = property(lambda self: self.checkLogin() and self._poolName != '')

    def getPoolName(self):
        pool = self.pool.get_all()[0]
        return self.pool.get_name_label(pool)

    # Login/Logout

    def login(self, switchToMaster=False):
        try:
            self._url = self._protocol + self._host + ':' + self._port
            # On python 2.7.9, HTTPS is verified by default,
            if self._useSSL and self._verifySSL is False:
                context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)  # @UndefinedVariable
                context.verify_mode = ssl.CERT_NONE
                transport = xmlrpclib.SafeTransport(context=context)
            else:
                transport = None

            self._session = XenAPI.Session(self._url, transport=transport)
            self._session.xenapi.login_with_password(self._username, self._password)
            self._loggedIn = True
            self._apiVersion = self._session.API_version
            self._poolName = unicode(self.getPoolName())
        except XenAPI.Failure as e:  # XenAPI.Failure: ['HOST_IS_SLAVE', '172.27.0.29'] indicates that this host is an slave of 172.27.0.29, connect to it...
            if switchToMaster and e.details[0] == 'HOST_IS_SLAVE':
                logger.info('{0} is an Slave, connecting to master at {1} cause switchToMaster is True'.format(self._host, e.details[1]))
                self._host = e.details[1]
                self.login()
            else:
                raise XenFailure(e.details)

    def test(self):
        self.login(False)

    def logout(self):
        self._session.logout()
        self._loggedIn = False
        self._session = None
        self._poolName = self._apiVersion = ''

    def getHost(self):
        return self._host

    def setHost(self, host):
        self._host = host

    def getTaskInfo(self, task):
        progress = 0
        result = None
        status = 'unknown'
        destroyTask = False
        try:
            status = self.task.get_status(task)
            logger.debug('Task {0} in state {1}'.format(task, status))
            if status == 'pending':
                status = 'running'
                progress = int(self.task.get_progress(task) * 100)
            elif status == 'success':
                result = self.task.get_result(task)
                destroyTask = True
            elif status == 'failure':
                result = XenFailure(self.task.get_error_info(task))
                destroyTask = True
        except XenAPI.Failure as e:
            logger.debug('XenServer Failure: {0}'.format(e.details[0]))
            if e.details[0] == 'HANDLE_INVALID':
                result = None
                status = 'unknown'
                progress = 0
            else:
                destroyTask = True
                result = e.details[0]
                status = 'failure'
        except Exception as e:
            logger.exception('Unexpected exception!')
            result = six.text_type(e)
            status = 'failure'

        # Removes <value></value> if present
        if result and not isinstance(result, XenFailure) and result.startswith('<value>'):
            result = result[7:-8]

        if destroyTask:
            try:
                self.task.destroy(task)
            except Exception as e:
                logger.info('Task {0} returned error {1}'.format(task, unicode(e)))

        return {'result': result, 'progress': progress, 'status': unicode(status)}

    def getSRs(self):
        for srId in self.SR.get_all():
            # Only valid SR shared, non iso
            name_label = self.SR.get_name_label(srId)
            if self.SR.get_content_type(srId) == 'iso' or \
               self.SR.get_shared(srId) is False or \
               name_label == '':
                continue

            valid = True
            allowed_ops = self.SR.get_allowed_operations(srId)
            for v in ['vdi_create', 'vdi_clone', 'vdi_snapshot', 'vdi_destroy']:
                if v not in allowed_ops:
                    valid = False

            if not valid:
                return

            yield {
                'id': srId,
                'name': name_label,
                'size': XenServer.toMb(self.SR.get_physical_size(srId)),
                'used': XenServer.toMb(self.SR.get_physical_utilisation(srId))
            }

    def getSRInfo(self, srId):
        return {
            'id': srId,
            'name': self.SR.get_name_label(srId),
            'size': XenServer.toMb(self.SR.get_physical_size(srId)),
            'used': XenServer.toMb(self.SR.get_physical_utilisation(srId))
        }

    def getNetworks(self):
        for netId in self.network.get_all():
            if self.network.get_other_config(netId).get('is_host_internal_management_network', False) is False:
                yield {
                    'id': netId,
                    'name': self.network.get_name_label(netId),
                }

    def getNetworkInfo(self, netId):
        return {
            'id': netId,
            'name': self.network.get_name_label(netId)
        }

    def getVMs(self):
        try:
            vms = self.VM.get_all()
            for vm in vms:
                # if self.VM.get_is_a_template(vm):  #  Sample set_tags, easy..
                #     self.VM.set_tags(vm, ['template'])
                #     continue
                if self.VM.get_is_control_domain(vm) or \
                   self.VM.get_is_a_template(vm):
                    continue

                yield {'id': vm, 'name': self.VM.get_name_label(vm)}
        except XenAPI.Failure as e:
            raise XenFailure(e.details)
        except Exception as e:
            raise XenException(unicode(e))

    def getVMPowerState(self, vmId):
        try:
            power_state = self.VM.get_power_state(vmId)
            logger.debug('Power state of {0}: {1}'.format(vmId, power_state))
            return power_state
        except XenAPI.Failure as e:
            raise XenFailure(e.details)

    def getVMInfo(self, vmId):
        try:
            return self.VM.get_record(vmId)
        except XenAPI.Failure as e:
            return XenFailure(e.details)

    def startVM(self, vmId, async=True):
        vmState = self.getVMPowerState(vmId)
        if vmState == XenPowerState.running:
            return None  # Already powered on

        if vmState == XenPowerState.suspended:
            return self.resumeVM(vmId, async)

        if async:
            return self.Async.VM.start(vmId, False, False)
        return self.VM.start(vmId, False, False)

    def stopVM(self, vmId, async=True):
        vmState = self.getVMPowerState(vmId)
        if vmState in (XenPowerState.suspended, XenPowerState.halted):
            return None  # Already powered off
        if async:
            return self.Async.VM.hard_shutdown(vmId)
        return self.VM.hard_shutdown(vmId)

    def resetVM(self, vmId, async=True):
        vmState = self.getVMPowerState(vmId)
        if vmState in (XenPowerState.suspended, XenPowerState.halted):
            return None  # Already powered off
        if async:
            return self.Async.VM.hard_reboot(vmId)
        return self.VM.hard_reboot(vmId)

    def canSuspendVM(self, vmId):
        operations = self.VM.get_allowed_operations(vmId)
        logger.debug('Operations: {}'.format(operations))
        return 'suspend' in operations

    def suspendVM(self, vmId, async=True):
        vmState = self.getVMPowerState(vmId)
        if vmState == XenPowerState.suspended:
            return None
        if async:
            return self.Async.VM.suspend(vmId)
        return self.VM.suspend(vmId)

    def resumeVM(self, vmId, async=True):
        vmState = self.getVMPowerState(vmId)
        if vmState != XenPowerState.suspended:
            return None
        if async:
            return self.Async.VM.resume(vmId, False, False)
        return self.VM.resume(vmId, False, False)

    def cloneVM(self, vmId, targetName, targetSR=None):
        '''
        If targetSR is NONE:
            Clones the specified VM, making a new VM.
            Clone automatically exploits the capabilities of the underlying storage repository
            in which the VM's disk images are stored (e.g. Copy on Write).
        Else:
            Copied the specified VM, making a new VM. Unlike clone, copy does not exploits the capabilities
            of the underlying storage repository in which the VM's disk images are stored.
            Instead, copy guarantees that the disk images of the newly created VM will be
            'full disks' - i.e. not part of a CoW chain.
        This function can only be called when the VM is in the Halted State.
        '''
        logger.debug('Cloning VM {0} to {1} on sr {2}'.format(vmId, targetName, targetSR))
        operations = self.VM.get_allowed_operations(vmId)
        logger.debug('Allowed operations: {0}'.format(operations))

        try:
            if targetSR:
                if 'copy' not in operations:
                    raise XenException('Clone is not supported for this machine')
                task = self.Async.VM.copy(vmId, targetName, targetSR)
            else:
                if 'clone' not in operations:
                    raise XenException('Clone is not supported for this machine')
                task = self.Async.VM.clone(vmId, targetName)
            return task
        except XenAPI.Failure as e:
            raise XenFailure(e.details)

    def removeVM(self, vmId):
        logger.debug('Removing machine')
        vdisToDelete = []
        for vdb in self.VM.get_VBDs(vmId):
            try:
                vdi = self.VBD.get_VDI(vdb)
                if vdi == 'OpaqueRef:NULL':
                    logger.debug('VDB without VDI')
                    continue
                logger.debug('VDI: {0}'.format(vdi))
            except:
                logger.exception('Exception getting VDI from VDB')
            if self.VDI.get_read_only(vdi) is True:
                logger.debug('{0} is read only, skipping'.format(vdi))
                continue
            logger.debug('VDI to delete: {0}'.format(vdi))
            vdisToDelete.append(vdi)
        self.VM.destroy(vmId)
        for vdi in vdisToDelete:
            self.VDI.destroy(vdi)

    def configureVM(self, vmId, **kwargs):
        '''
        Optional args:
            mac = { 'network': netId, 'mac': mac }
            memory = MEM in MB, minimal is 128

        Mac address should be in the range 02:xx:xx:xx:xx (recommended, but not a "have to")
        '''
        mac = kwargs.get('mac', None)
        memory = kwargs.get('memory', None)

        # If requested mac address change
        try:
            if mac is not None:
                for vifId in self.VM.get_VIFs(vmId):
                    vif = self.VIF.get_record(vifId)

                    if vif['network'] == mac['network']:
                        logger.debug('Found VIF: {0}'.format(vif['network']))
                        self.VIF.destroy(vifId)

                        # for k in ['status_code', 'status_detail', 'uuid']:
                        #     try:
                        #         del vif[k]
                        #     except:
                        #         logger.exception('Erasing property {0}'.format(k))
                        vif['MAC'] = mac['mac']
                        vif['MAC_autogenerated'] = False
                        self.VIF.create(vif)
            # If requested memory change
            if memory is not None:
                logger.debug('Setting up memory to {0} MB'.format(memory))
                # Convert memory to MB
                memory = unicode(int(memory) * 1024 * 1024)
                self.VM.set_memory_limits(vmId, memory, memory, memory, memory)
        except XenAPI.Failure as e:
            raise XenFailure(e.details)

    def provisionVM(self, vmId, **kwargs):
        tags = self.VM.get_tags(vmId)
        try:
            del tags[tags.index(TAG_TEMPLATE)]
        except Exception:
            pass
        tags.append(TAG_MACHINE)
        self.VM.set_tags(vmId, tags)

        if kwargs.get('async', True) is True:
            return self.Async.VM.provision(vmId)
        return self.VM.provision(vmId)

    def convertToTemplate(self, vmId, shadowMultiplier=4):
        try:
            operations = self.VM.get_allowed_operations(vmId)
            logger.debug('Allowed operations: {0}'.format(operations))
            if 'make_into_template' not in operations:
                raise XenException('Convert in template is not supported for this machine')
            self.VM.set_is_a_template(vmId, True)

            # Apply that is an "UDS Template" taggint it
            tags = self.VM.get_tags(vmId)
            try:
                del tags[tags.index(TAG_MACHINE)]
            except:
                pass
            tags.append(TAG_TEMPLATE)
            self.VM.set_tags(vmId, tags)

            # Set multiplier
            try:
                self.VM.set_HVM_shadow_multiplier(vmId, float(shadowMultiplier))
            except Exception:
                # Can't set shadowMultiplier, nothing happens
                pass  # TODO: Log this?
        except XenAPI.Failure as e:
            raise XenFailure(e.details)

    def removeTemplate(self, templateId):
        self.removeVM(templateId)

    def cloneTemplate(self, templateId, targetName):
        '''
        After cloning template, we must deploy the VM so it's a full usable VM
        '''
        return self.cloneVM(templateId, targetName)
