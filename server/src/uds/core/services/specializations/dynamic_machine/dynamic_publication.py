# # -*- coding: utf-8 -*-

# #
# # Copyright (c) 2012-2019 Virtual Cable S.L.
# # All rights reserved.
# #
# """
# Author: Adolfo Gómez, dkmaster at dkmon dot com
# """

# import abc
# from datetime import datetime
# import logging
# import time
# import typing

# from django.utils.translation import gettext as _
# from uds.core import services, types
# from uds.core.types.services import Operation
# from uds.core.util import autoserializable

# if typing.TYPE_CHECKING:
#     from .dynamic_service import DynamicService

# class DynamicPublication(services.Publication, autoserializable.AutoSerializable, abc.ABC):
#     suggested_delay = 20  # For publications, we can check every 20 seconds

#     _name = autoserializable.StringField(default='')
#     _vm = autoserializable.StringField(default='')
#     _queue = autoserializable.ListField[Operation]()

#     # Utility overrides for type checking...
#     def _current_op(self) -> Operation:
#         if not self._queue:
#             return Operation.FINISH

#         return self._queue[0]
    
#     def service(self) -> 'DynamicService':
#         return typing.cast('DynamicService', super().service())
    
#     def check_space(self) -> bool:
#         """
#         If the service needs to check space before publication, it should override this method
#         """
#         return True

#     def publish(self) -> types.states.TaskState:
#         """
#         """
#         try:
#             # First we should create a full clone, so base machine do not get fullfilled with "garbage" delta disks...
#             self._name = self.service().sanitize_machine_name(
#                 'UDS Pub'
#                 + ' '
#                 + self.servicepool_name()
#                 + "-"
#                 + str(self.revision())  # plus current time, to avoid name collisions
#                 + "-"
#                 + f'{int(time.time())%256:2X}'
#             )
#             comments = _('UDS Publication for {0} created at {1}').format(
#                 self.servicepool_name(), str(datetime.now()).split('.')[0]
#             )
#             self._state = types.states.State.RUNNING
#             self._operation = 'p'  # Publishing
#             self._destroy_after = False
#             return types.states.TaskState.RUNNING
#         except Exception as e:
#             logger.exception('Caught exception %s', e)
#             self._reason = str(e)
#             return types.states.TaskState.ERROR
        
#     def _execute_queue(self) -> types.states.TaskState:
#         op = self._current_op()
        
#         if op == Operation.ERROR:
#             return types.states.TaskState.ERROR

#         if op == Operation.FINISH:
#             return types.states.TaskState.FINISHED
        

#     def check_state(
#         self,
#     ) -> types.states.State:  # pylint: disable = too-many-branches,too-many-return-statements
#         if self._state != types.states.State.RUNNING:
#             return types.states.State.from_str(self._state)

#         task = self.service().get_task_info(self._task)
#         trans: typing.Dict[str, str] = {
#             VMWTask.ERROR: types.states.State.ERROR,
#             VMWTask.RUNNING: types.states.State.RUNNING,
#             VMWTask.FINISHED: types.states.State.FINISHED,
#             VMWTask.UNKNOWN_TASK: types.states.State.ERROR,
#         }
#         reasons: typing.Dict[str, str] = {
#             VMWTask.ERROR: 'Error',
#             VMWTask.RUNNING: 'Already running',
#             VMWTask.FINISHED: 'Finished',
#             VMWTask.UNKNOWN_TASK: 'Task not known by VC',
#         }

#         try:
#             st = task.state() or VMWTask.UNKNOWN_TASK
#         except TypeError as e:
#             logger.exception(
#                 'Catch exception invoking vmware, delaying request: %s %s',
#                 e.__class__,
#                 e,
#             )
#             return types.states.State.from_str(self._state)
#         except Exception as e:
#             logger.exception('Catch exception invoking vmware: %s %s', e.__class__, e)
#             self._state = types.states.State.ERROR
#             self._reason = str(e)
#             return self._state
#         self._reason = reasons[st]
#         self._state = trans[st]
#         if self._state == types.states.State.ERROR:
#             self._reason = task.result() or 'Publication not found!'
#         elif self._state == types.states.State.FINISHED:
#             if self._operation == 'x':  # Destroying snapshot
#                 return self._remove_machine()
#             if self._operation == 'p':
#                 self._vm = str(task.result() or '')
#                 # Now make snapshot
#                 if self._destroy_after:
#                     return self.destroy()

#                 if self.isFullCloner() is True:  # If full cloner is our father
#                     self._snapshot = ''
#                     self._task = ''
#                     self._state = types.states.State.FINISHED
#                     return self._state

#                 try:
#                     comments = 'UDS Snapshot created at ' + str(datetime.now())
#                     self._task = self.service().create_snapshot(self._vm, SNAPNAME, comments)
#                     self._state = types.states.State.RUNNING
#                     self._operation = 's'  # Snapshoting
#                 except Exception as e:
#                     self._state = types.states.State.ERROR
#                     self._reason = str(e)
#                     logger.exception('Exception caught creating snapshot')
#             elif self._operation == 's':
#                 self._snapshot = task.result() or ''
#                 if (
#                     self._destroy_after
#                 ):  # If publishing and was canceled or destroyed before finishing, do it now
#                     return self.destroy()
#             else:
#                 self._snapshot = ''
#         return types.states.State.from_str(self._state)

#     def finish(self) -> None:
#         self._task = ''
#         self._destroy_after = False

#     def destroy(self) -> types.states.State:
#         if (
#             self._state == types.states.State.RUNNING and self._destroy_after is False
#         ):  # If called destroy twice, will BREAK STOP publication
#             self._destroy_after = True
#             return types.states.State.RUNNING
#         self._destroy_after = False
#         # if self.snapshot != '':
#         #    return self.__removeSnapshot()
#         return self._remove_machine()

#     def cancel(self) -> types.states.State:
#         return self.destroy()

#     def error_reason(self) -> str:
#         return self._reason

#     def snapshot_reference(self) -> str:
#         return self.service().provider().get_current_snapshot(self._vm) or 'invalid-snapshot'
#         # return self.snapshot

#     def machine_reference(self) -> str:
#         return self._vm

#     def _remove_machine(self) -> types.states.State:
#         if not self._vm:
#             logger.error("Machine reference not found!!")
#             return types.states.State.ERROR
#         try:
#             self._task = self.service().remove_machine(self._vm)
#             self._state = types.states.State.RUNNING
#             self._operation = 'd'
#             self._destroy_after = False
#             return types.states.State.RUNNING
#         except Exception as e:
#             # logger.exception("Caught exception at __removeMachine %s:%s", e.__class__, e)
#             logger.error('Error removing machine: %s', e)
#             self._reason = str(e)
#             return types.states.State.ERROR

#     def unmarshal(self, data: bytes) -> None:
#         if autoserializable.is_autoserializable_data(data):
#             return super().unmarshal(data)

#         _auto_data = OldSerialData()
#         _auto_data.unmarshal(data)

#         # Fill own data from restored data
#         self._name = _auto_data._name
#         self._vm = _auto_data._vm
#         self._snapshot = _auto_data._snapshot
#         self._task = _auto_data._task
#         self._state = _auto_data._state
#         self._operation = _auto_data._operation
#         self._destroy_after = _auto_data._destroyAfter
#         self._reason = _auto_data._reason

#         # Flag for upgrade
#         self.mark_for_upgrade(True)
