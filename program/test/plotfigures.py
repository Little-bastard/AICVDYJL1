from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
import sys


class QtThread(QThread):
    def __init__(self):
        super(QtThread, self).__init__()

    # 重写run函数，实现线程的工作
    def run(self):
        # do something
        print("call pyqt5Thread fun")


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setGeometry(500, 300, 300, 300)

        self.thread = QtThread()
        self.thread.start()

        self.timer = QTimer(self)
        self.timer.start(1000)  # 每过5秒，定时器到期，产生timeout的信号
        self.timer.timeout.connect(self.call_thread)

    def call_thread(self):
        self.thread = QtThread()
        self.thread.start()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setApplicationName("测试")
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())