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
#    * Neither the name of Virtual Cable S.L.U. nor the names of its contributors
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

"""
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
from datetime import datetime
import time
import logging
import typing
import collections.abc

from django.utils.translation import gettext as _
from uds.core import services
from uds.core.util import autoserializable
from uds.core.types.states import State

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from .service import ProxmoxLinkedService
    from . import client

logger = logging.getLogger(__name__)


class ProxmoxPublication(services.Publication, autoserializable.AutoSerializable):
    suggested_delay = 20
    
    _name = autoserializable.StringField(default='')
    _vm = autoserializable.StringField(default='')
    _task = autoserializable.StringField(default='')
    _state = autoserializable.StringField(default='')
    _operation = autoserializable.StringField(default='')
    _destroy_after = autoserializable.BoolField(default=False)
    _reason = autoserializable.StringField(default='')

    # Utility overrides for type checking...
    def service(self) -> 'ProxmoxLinkedService':
        return typing.cast('ProxmoxLinkedService', super().service())

    def unmarshal(self, data: bytes) -> None:
        """
        deserializes the data and loads it inside instance.
        """
        if not data.startswith(b'v'):
            return super().unmarshal(data)
        
        logger.debug('Data: %s', data)
        vals = data.decode('utf8').split('\t')
        if vals[0] == 'v1':
            (
                self._name,
                self._vm,
                self._task,
                self._state,
                self._operation,
                destroy_after,
                self._reason,
            ) = vals[1:]
        else:
            raise ValueError('Invalid data format')
            
        self._destroy_after = destroy_after != ''
        
        self.mark_for_upgrade()  # Flag so manager can save it again with new format

    def publish(self) -> str:
        """
        If no space is available, publication will fail with an error
        """
        try:
            # First we should create a full clone, so base machine do not get fullfilled with "garbage" delta disks...
            self._name = (
                'UDS '
                + _('Publication')
                + ' '
                + self.servicepool_name()
                + "-"
                + str(self.revision())
            )
            comments = _('UDS Publication for {0} created at {1}').format(
                self.servicepool_name(), str(datetime.now()).split('.')[0]
            )
            task = self.service().clone_machine(self._name, comments)
            self._vm = str(task.vmid)
            self._task = ','.join((task.upid.node, task.upid.upid))
            self._state = State.RUNNING
            self._operation = 'p'  # Publishing
            self._destroy_after = False
            return State.RUNNING
        except Exception as e:
            logger.exception('Caught exception %s', e)
            self._reason = str(e)
            return State.ERROR

    def check_state(
        self,
    ) -> str:  # pylint: disable = too-many-branches,too-many-return-statements
        if self._state != State.RUNNING:
            return self._state
        node, upid = self._task.split(',')
        try:
            task = self.service().get_task_info(node, upid)
            if task.is_running():
                return State.RUNNING
        except Exception as e:
            logger.exception('Proxmox publication')
            self._state = State.ERROR
            self._reason = str(e)
            return self._state

        if task.is_errored():
            self._reason = task.exitstatus
            self._state = State.ERROR
        else:  # Finished
            if self._destroy_after:
                return self.destroy()
            self._state = State.FINISHED
            if self._operation == 'p':  # not Destroying
                # Disable Protection (removal)
                self.service().set_protection(int(self._vm), protection=False)
                time.sleep(
                    0.5
                )  # Give some tome to proxmox. We have observed some concurrency issues
                # And add it to HA if
                self.service().enable_ha(int(self._vm))
                time.sleep(0.5)
                # Mark vm as template
                self.service().make_template(int(self._vm))

                # This seems to cause problems on Proxmox
                # makeTemplate --> setProtection (that calls "config"). Seems that the HD dissapears...
                # Seems a concurrency problem?

        return self._state

    def finish(self) -> None:
        self._task = ''
        self._destroy_after = False

    def destroy(self) -> str:
        if (
            self._state == State.RUNNING and self._destroy_after is False
        ):  # If called destroy twice, will BREAK STOP publication
            self._destroy_after = True
            return State.RUNNING

        self.state = State.RUNNING
        self._operation = 'd'
        self._destroy_after = False
        try:
            task = self.service().remove_machine(self.machine())
            self._task = ','.join((task.node, task.upid))
            return State.RUNNING
        except Exception as e:
            self._reason = str(e)  # Store reason of error
            logger.warning('Problem destroying publication %s: %s. Please, check machine state On Proxmox', self.machine(), e)
            return State.ERROR

    def cancel(self) -> str:
        return self.destroy()

    def error_reason(self) -> str:
        return self._reason

    def machine(self) -> int:
        return int(self._vm)
