import sys

from PyQt5.QtCore import pyqtSignal, QTimer, QSignalBlocker, Qt, QCoreApplication
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QMessageBox, QMenu, QAction, QApplication, QMainWindow

from program.MicroscopeDev import toupcam
from program.MicroscopeDev.qt import MainWidget
from program.Ui_MainWindow import Ui_MainWindow


class CameraWorker:
    evtCallback = pyqtSignal(int)

    def __init__(self, hcam):
        super().__init__()
        self.hcam = hcam
        self.stop = False

    def run(self):
        try:
            while True:
                if self.stop:
                    break
                self.evtCallback.emit()

        except Exception as e:
            print(f'An error occurred when emit temp data: {e}')



