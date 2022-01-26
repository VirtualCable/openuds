import multiprocessing
import asyncio
import logging
import typing

import psutil

from . import config

if typing.TYPE_CHECKING:
    from multiprocessing.connection import Connection
    from multiprocessing.managers import Namespace

logger = logging.getLogger(__name__)

ProcessType = typing.Callable[['Connection', config.ConfigurationType, 'Namespace'],  typing.Coroutine[typing.Any, None, None]]

class Processes:
    """
    This class is used to store the processes that are used by the tunnel.
    """

    children: typing.List[
        typing.Tuple['Connection', multiprocessing.Process, psutil.Process]
    ]
    process: ProcessType
    cfg: config.ConfigurationType
    ns: 'Namespace'

    def __init__(self, process: ProcessType, cfg: config.ConfigurationType, ns: 'Namespace') -> None:
        self.children = []
        self.process = process  # type: ignore
        self.cfg = cfg
        self.ns = ns

        for i in range(cfg.workers):
            self.add_child_pid()

    def add_child_pid(self):
        own_conn, child_conn = multiprocessing.Pipe()
        task = multiprocessing.Process(
            target=Processes.runner,
            args=(self.process, child_conn, self.cfg, self.ns),
        )
        task.start()
        logger.debug('ADD CHILD PID: %s', task.pid)
        self.children.append((own_conn, task, psutil.Process(task.pid)))

    def best_child(self) -> 'Connection':
        best: typing.Tuple[float, 'Connection'] = (1000.0, self.children[0][0])
        missingProcesses: typing.List[int] = []
        for i, c in enumerate(self.children):
            try:
                if c[2].status() == 'zombie':  # Bad kill!!
                    raise psutil.ZombieProcess(c[2].pid)
                percent = c[2].cpu_percent()
            except (psutil.ZombieProcess, psutil.NoSuchProcess) as e:
                # Process is missing...
                logger.warning('Missing process found: %s', e.pid)
                try:
                    c[0].close()  # Close pipe to missing process
                except Exception:
                    logger.debug('Could not close handle for %s', e.pid)
                try:
                    c[1].kill()
                    c[1].close()
                except Exception:
                    logger.debug('Could not close process %s', e.pid)

                missingProcesses.append(i)
                continue

            logger.debug('PID %s has %s', c[2].pid, percent)

            if percent < best[0]:
                best = (percent, c[0])

        # If we have a missing process, try to add it back
        if missingProcesses:
            logger.debug('Regenerating missing processes: %s', len(missingProcesses))
            # Regenerate childs and recreate new proceeses for requests...
            tmpChilds = [
                self.children[i]
                for i in range(len(self.children))
                if i not in missingProcesses
            ]
            self.children[:] = tmpChilds
            # Now add new children
            for i in range(len(missingProcesses)):
                self.add_child_pid()

        return best[1]

    def stop(self):
        # Try to stop running childs
        for i in self.children:
            try:
                i[2].kill()
            except Exception as e:
                logger.info('KILLING child %s: %s', i[2], e)
    
    @staticmethod
    def runner(proc: ProcessType, conn: 'Connection', cfg: config.ConfigurationType, ns: 'Namespace') -> None:
        asyncio.run(proc(conn, cfg, ns))
