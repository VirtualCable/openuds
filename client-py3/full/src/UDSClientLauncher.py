import sys
import os.path
import subprocess
import typing

from uds.log import logger
import UDSClient
from UDSLauncherMac import Ui_MacLauncher

from PyQt5 import QtCore, QtWidgets, QtGui

SCRIPT_NAME = 'UDSClientLauncher'

class UdsApplication(QtWidgets.QApplication):
    path: str
    def __init__(self, argv: typing.List[str]) -> None:
        super().__init__(argv)
        self.path = os.path.join(os.path.dirname(sys.argv[0]).replace('Resources', 'MacOS'), SCRIPT_NAME)

    def event(self, evnt: QtCore.QEvent) -> bool:
        logger.debug('Got event %s -> %s', evnt, evnt.type())

        if evnt.type() == QtCore.QEvent.FileOpen:
            fe = typing.cast(QtGui.QFileOpenEvent, evnt)
            logger.debug('Got url: %s', fe.url().url())
            fe.accept()
            logger.debug('Spawning %s', self.path)
            subprocess.Popen([self.path, fe.url().url()])

        return super().event(evnt)


def main(args: typing.List[str]):
    if len(args) > 1:
        UDSClient.main(args)
    else:
        app = UdsApplication(sys.argv)
        window = QtWidgets.QMainWindow()
        Ui_MacLauncher().setupUi(window)

        window.showMinimized()

        sys.exit(app.exec_())

if __name__ == "__main__":
    main(args=sys.argv)

