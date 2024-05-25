# -*- coding: utf-8 -*-
#
# Copyright (c) 2014-2024 Virtual Cable S.L.U.
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

import datetime
import enum
import dataclasses
import typing


class PowerState(enum.StrEnum):
    HALTED = 'Halted'
    RUNNING = 'Running'
    SUSPENDED = 'Suspended'
    PAUSED = 'Paused'

    # Internal UNKNOW state
    UNKNOW = 'Unknow'

    def is_running(self) -> bool:
        return self == PowerState.RUNNING

    def is_stopped(self) -> bool:
        return self in (PowerState.HALTED, PowerState.SUSPENDED)

    def is_suspended(self) -> bool:
        return self == PowerState.SUSPENDED

    @staticmethod
    def from_str(value: str) -> 'PowerState':
        try:
            return PowerState(value.capitalize())
        except ValueError:
            return PowerState.UNKNOW


class TaskStatus(enum.StrEnum):
    """
    Values:
        pending	task is in progress
        success	task was completed successfully
        failure	task has failed
        cancelling	task is being cancelled
        cancelled	task has been cancelled
    """

    PENDING = 'pending'
    SUCCESS = 'success'
    FAILURE = 'failure'
    CANCELLING = 'cancelling'
    CANCELLED = 'cancelled'

    # Internal UNKNOW state
    UNKNOW = 'unknow'

    def is_done(self) -> bool:
        return self in (TaskStatus.SUCCESS, TaskStatus.FAILURE, TaskStatus.CANCELLED)

    def is_success(self) -> bool:
        return self == TaskStatus.SUCCESS

    def is_failure(self) -> bool:
        return self == TaskStatus.FAILURE

    @staticmethod
    def from_str(value: str) -> 'TaskStatus':
        try:
            return TaskStatus(value.lower())
        except ValueError:
            return TaskStatus.UNKNOW


class StorageOperations(enum.StrEnum):
    """
    Values:
        scan 	Scanning backends for new or deleted VDIs
        destroy 	Destroying the SR
        forget 	Forgetting about SR
        plug 	Plugging a PBD into this SR
        unplug 	Unplugging a PBD from this SR
        update 	Refresh the fields on the SR
        vdi_create 	Creating a new VDI
        vdi_introduce 	Introducing a new VDI
        vdi_destroy 	Destroying a VDI
        vdi_resize 	Resizing a VDI
        vdi_clone 	Cloneing a VDI
        vdi_snapshot 	Snapshotting a VDI
        vdi_mirror 	Mirroring a VDI
        vdi_enable_cbt 	Enabling changed block tracking for a VDI
        vdi_disable_cbt 	Disabling changed block tracking for a VDI
        vdi_data_destroy 	Deleting the data of the VDI
        vdi_list_changed_blocks 	Exporting a bitmap that shows the changed blocks between two VDIs
        vdi_set_on_boot 	Setting the on_boot field of the VDI
        pbd_create 	Creating a PBD for this SR
        pbd_destroy 	Destroying one of this SR's PBDs
    """

    SCAN = 'scan'
    DESTROY = 'destroy'
    FORGET = 'forget'
    PLUG = 'plug'
    UNPLUG = 'unplug'
    UPDATE = 'update'
    VDI_CREATE = 'vdi_create'
    VDI_INTRODUCE = 'vdi_introduce'
    VDI_DESTROY = 'vdi_destroy'
    VDI_RESIZE = 'vdi_resize'
    VDI_CLONE = 'vdi_clone'
    VDI_SNAPSHOT = 'vdi_snapshot'
    VDI_MIRROR = 'vdi_mirror'
    VDI_ENABLE_CBT = 'vdi_enable_cbt'
    VDI_DISABLE_CBT = 'vdi_disable_cbt'
    VDI_DATA_DESTROY = 'vdi_data_destroy'
    VDI_LIST_CHANGED_BLOCKS = 'vdi_list_changed_blocks'
    VDI_SET_ON_BOOT = 'vdi_set_on_boot'
    PBD_CREATE = 'pbd_create'
    PBD_DESTROY = 'pbd_destroy'

    # Internal UNKNOW storage operation
    UNKNOW = 'unknow'

    @staticmethod
    def from_str(value: str) -> 'StorageOperations':
        try:
            return StorageOperations(value.lower())
        except ValueError:
            return StorageOperations.UNKNOW

    @staticmethod
    def is_usable(values: typing.Iterable['StorageOperations']) -> bool:
        # To be usable, must contain ALL required operations
        # Where the required operations are:
        #  VDI_CREATE, VDI_CLONE, VDI_SNAPSHOT, VDI_DESTROY
        return all(
            op in values
            for op in (
                StorageOperations.VDI_CREATE,
                StorageOperations.VDI_CLONE,
                StorageOperations.VDI_SNAPSHOT,
                StorageOperations.VDI_DESTROY,
            )
        )


class VMOperations(enum.StrEnum):
    """
    Values:
        snapshot 	refers to the operation "snapshot"
        clone 	refers to the operation "clone"
        copy 	refers to the operation "copy"
        create_template 	refers to the operation "create_template"
        revert 	refers to the operation "revert"
        checkpoint 	refers to the operation "checkpoint"
        snapshot_with_quiesce 	refers to the operation "snapshot_with_quiesce"
        provision 	refers to the operation "provision"
        start 	refers to the operation "start"
        start_on 	refers to the operation "start_on"
        pause 	refers to the operation "pause"
        unpause 	refers to the operation "unpause"
        clean_shutdown 	refers to the operation "clean_shutdown"
        clean_reboot 	refers to the operation "clean_reboot"
        hard_shutdown 	refers to the operation "hard_shutdown"
        power_state_reset 	refers to the operation "power_state_reset"
        hard_reboot 	refers to the operation "hard_reboot"
        suspend 	refers to the operation "suspend"
        csvm 	refers to the operation "csvm"
        resume 	refers to the operation "resume"
        resume_on 	refers to the operation "resume_on"
        pool_migrate 	refers to the operation "pool_migrate"
        migrate_send 	refers to the operation "migrate_send"
        get_boot_record 	refers to the operation "get_boot_record"
        send_sysrq 	refers to the operation "send_sysrq"
        send_trigger 	refers to the operation "send_trigger"
        query_services 	refers to the operation "query_services"
        shutdown 	refers to the operation "shutdown"
        call_plugin 	refers to the operation "call_plugin"
        changing_memory_live 	Changing the memory settings
        awaiting_memory_live 	Waiting for the memory settings to change
        changing_dynamic_range 	Changing the memory dynamic range
        changing_static_range 	Changing the memory static range
        changing_memory_limits 	Changing the memory limits
        changing_shadow_memory 	Changing the shadow memory for a halted VM.
        changing_shadow_memory_live 	Changing the shadow memory for a running VM.
        changing_VCPUs 	Changing VCPU settings for a halted VM.
        changing_VCPUs_live 	Changing VCPU settings for a running VM.
        changing_NVRAM 	Changing NVRAM for a halted VM.
        assert_operation_valid
        data_source_op 	Add, remove, query or list data sources
        update_allowed_operations
        make_into_template 	Turning this VM into a template
        import 	importing a VM from a network stream
        export 	exporting a VM to a network stream
        metadata_export 	exporting VM metadata to a network stream
        reverting 	Reverting the VM to a previous snapshotted state
        destroy 	refers to the act of uninstalling the VM
        create_vtpm 	Creating and adding a VTPM to this VM
    """

    SNAPSHOOT = 'snapshot'
    CLONE = 'clone'
    COPY = 'copy'
    CREATE_TEMPLATE = 'create_template'
    REVERT = 'revert'
    CHECKPOINT = 'checkpoint'
    SNAPSHOT_WITH_QUIESCE = 'snapshot_with_quiesce'
    PROVISION = 'provision'
    START = 'start'
    START_ON = 'start_on'
    PAUSE = 'pause'
    UNPAUSE = 'unpause'
    CLEAN_SHUTDOWN = 'clean_shutdown'
    CLEAN_REBOOT = 'clean_reboot'
    HARD_SHUTDOWN = 'hard_shutdown'
    POWER_STATE_RESET = 'power_state_reset'
    HARD_REBOOT = 'hard_reboot'
    SUSPEND = 'suspend'
    CSVM = 'csvm'
    RESUME = 'resume'
    RESUME_ON = 'resume_on'
    POOL_MIGRATE = 'pool_migrate'
    MIGRATE_SEND = 'migrate_send'
    GET_BOOT_RECORD = 'get_boot_record'
    SEND_SYSRQ = 'send_sysrq'
    SEND_TRIGGER = 'send_trigger'
    QUERY_SERVICES = 'query_services'
    SHUTDOWN = 'shutdown'
    CALL_PLUGIN = 'call_plugin'
    CHANGING_MEMORY_LIVE = 'changing_memory_live'
    AWAITING_MEMORY_LIVE = 'awaiting_memory_live'
    CHANGING_DYNAMIC_RANGE = 'changing_dynamic_range'
    CHANGING_STATIC_RANGE = 'changing_static_range'
    CHANGING_MEMORY_LIMITS = 'changing_memory_limits'
    CHANGING_SHADOW_MEMORY = 'changing_shadow_memory'
    CHANGING_SHADOW_MEMORY_LIVE = 'changing_shadow_memory_live'
    CHANGING_VCPUS = 'changing_VCPUs'
    CHANGING_VCPUS_LIVE = 'changing_VCPUs_live'
    CHANGING_NVRAM = 'changing_NVRAM'
    ASSERT_OPERATION_VALID = 'assert_operation_valid'
    DATA_SOURCE_OP = 'data_source_op'
    UPDATE_ALLOWED_OPERATIONS = 'update_allowed_operations'
    MAKE_INTO_TEMPLATE = 'make_into_template'
    IMPORT = 'import'
    EXPORT = 'export'
    METADATA_EXPORT = 'metadata_export'
    REVERTING = 'reverting'
    DESTROY = 'destroy'
    CREATE_VTPM = 'create_vtpm'

    # Internal UNKNOW VM operation
    UNKNOW = 'unknow'

    @staticmethod
    def from_str(value: str) -> 'VMOperations':
        try:
            return VMOperations(value.lower())
        except ValueError:
            return VMOperations.UNKNOW


@dataclasses.dataclass
class StorageInfo:
    opaque_ref: str
    uuid: str
    name: str
    description: str
    allowed_operations: typing.List[StorageOperations]
    # current_operations not used
    VDIs: list[str]  # List of VDIs UUIDs
    PBDs: list[str]  # List of PDBs UUIDs
    virtual_allocation: int  # Virtual size of the storage
    physical_utilisation: int  # Used size of the storage
    physical_size: int  # Total size of the storage
    type: str  # Type of the storage
    content_type: str  # Content type of the storage
    shared: bool  # Shared storage

    @staticmethod
    def from_dict(data: dict[str, typing.Any], opaque_ref: str) -> 'StorageInfo':
        return StorageInfo(
            opaque_ref=opaque_ref,
            uuid=data['uuid'],
            name=data['name_label'],
            description=data['name_description'],
            allowed_operations=[StorageOperations.from_str(op) for op in data['allowed_operations']],
            VDIs=typing.cast(list[str], data.get('VDIs', '')),
            PBDs=typing.cast(list[str], data.get('PBDs', '')),
            virtual_allocation=int(data['virtual_allocation']),
            physical_utilisation=int(data['physical_utilisation']),
            physical_size=int(data['physical_size']),
            type=data['type'],
            content_type=data['content_type'],
            shared=data['shared'],
        )

    def is_usable(self) -> bool:
        if self.type == 'iso' or self.shared is False or self.name == '':
            return False

        return StorageOperations.is_usable(self.allowed_operations)


@dataclasses.dataclass
class VMInfo:
    opaque_ref: str
    uuid: str
    name: str
    description: str
    power_state: PowerState
    is_control_domain: bool
    is_a_template: bool
    snapshot_time: datetime.datetime
    snapshots: list[str]
    allowed_operations: typing.List[VMOperations]

    # Other useful configuration
    folder: str

    @staticmethod
    def from_dict(data: dict[str, typing.Any], opaque_ref: str) -> 'VMInfo':
        try:
            snapshot_time = datetime.datetime.fromisoformat(data['snapshot_time'].value)
        except ValueError:
            snapshot_time = datetime.datetime.now()

        other_config = typing.cast(dict[str, str], data.get('other_config', {}))

        return VMInfo(
            opaque_ref=opaque_ref,
            uuid=data['uuid'],
            name=data['name_label'],
            description=data['name_description'],
            power_state=PowerState.from_str(data['power_state']),
            is_control_domain=data['is_control_domain'],
            is_a_template=data['is_a_template'],
            snapshot_time=snapshot_time,
            snapshots=typing.cast(list[str], data.get('snapshots', [])),
            allowed_operations=[VMOperations.from_str(op) for op in data['allowed_operations']],
            folder=other_config.get('folder', ''),
        )

    @staticmethod
    def empty(opaque_ref: str) -> 'VMInfo':
        return VMInfo(
            opaque_ref=opaque_ref,
            uuid='',
            name='Unknown',
            description='Unknown VM',
            power_state=PowerState.UNKNOW,
            is_control_domain=False,
            is_a_template=False,
            snapshot_time=datetime.datetime.now(),
            snapshots=[],
            allowed_operations=[],
            folder='',
        )

    def is_usable(self) -> bool:
        if self.is_control_domain or self.is_a_template:
            return False

        return True

    def supports_suspend(self) -> bool:
        return VMOperations.SUSPEND in self.allowed_operations

@dataclasses.dataclass
class NetworkInfo:
    opaque_ref: str
    uuid: str
    name: str
    description: str
    managed: bool
    VIFs: list[str]  # List of VIFs opaques
    PIFs: list[str]  # List of PIFs opaques
    
    # Other useful configuration
    is_guest_installer_network: bool
    is_host_internal_management_network: bool
    ip_begin: str
    ip_end: str
    netmask: str
    
    @staticmethod
    def from_dict(data: dict[str, typing.Any], opaque_ref: str) -> 'NetworkInfo':
        other_config = typing.cast(dict[str, typing.Any], data.get('other_config', {}))

        return NetworkInfo(
            opaque_ref=opaque_ref,
            uuid=data['uuid'],
            name=data['name_label'],
            description=data['name_description'],
            managed=data['managed'],
            VIFs=typing.cast(list[str], data.get('VIFs', [])),
            PIFs=typing.cast(list[str], data.get('PIFs', [])),
            is_guest_installer_network=other_config.get('is_guest_installer_network', False),
            is_host_internal_management_network=other_config.get('is_host_internal_management_network', False),
            ip_begin=other_config.get('ip_begin', ''),
            ip_end=other_config.get('ip_end', ''),
            netmask=other_config.get('netmask', ''),
        )
    

@dataclasses.dataclass
class TaskInfo:
    opaque_ref: str
    uuid: str
    name: str
    description: str
    created: datetime.datetime
    finished: datetime.datetime
    status: TaskStatus
    result: str
    progress: float

    @staticmethod
    def from_dict(data: dict[str, typing.Any], opaque_ref: str) -> 'TaskInfo':
        result = data.get('result', '')
        if result and result.startswith('<value>'):
            result = result[7:-8]

        try:
            created = datetime.datetime.fromisoformat(data['created'].value)
        except ValueError:
            created = datetime.datetime.now()
        try:
            finished = datetime.datetime.fromisoformat(data['finished'].value)
        except ValueError:
            finished = created

        return TaskInfo(
            opaque_ref=opaque_ref,
            uuid=data['uuid'],
            name=data['name_label'],
            description=data['name_description'],
            created=created,
            finished=finished,
            status=TaskStatus.from_str(data['status']),
            result=result,
            progress=float(data['progress']),
        )

    @staticmethod
    def unknown_task(opaque_ref: str) -> 'TaskInfo':
        return TaskInfo(
            opaque_ref=opaque_ref,
            uuid='',
            name='Unknown',
            description='Unknown task',
            created=datetime.datetime.now(),
            finished=datetime.datetime.now(),
            status=TaskStatus.UNKNOW,
            result='',
            progress=0.0,
        )

    def is_done(self) -> bool:
        return self.status.is_done()

    def is_success(self) -> bool:
        return self.status.is_success()

    def is_failure(self) -> bool:
        return self.status.is_failure()
