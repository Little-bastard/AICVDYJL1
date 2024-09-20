import os
import sys

from PyQt5.QtCore import QCoreApplication, Qt
from PyQt5.QtWidgets import QApplication

from program.TempCtrlDev.TempWindow import TemperatureWindow

current_file_path = os.path.abspath(__file__)
print(f'Guiaicvd path: {current_file_path}')

if __name__ == "__main__":
    QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    app = QApplication(sys.argv)

    myWin = TemperatureWindow()
    # myWin.start_thread()
    myWin.show()

    sys.exit(app.exec_())
