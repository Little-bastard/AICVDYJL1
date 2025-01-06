from PyQt5.QtCore import QThread, pyqtSignal

from program.MicroscopeDev.FocusAPI import FocusAPI


class FocusWorker(QThread):
    focus_signal = pyqtSignal(str)

    def __init__(self, portName):
        super().__init__()
        portNumber = portName.replace("COM", "")
        self.focus = FocusAPI(portNumber=portNumber)
        self.stop = False

    def run(self):
        while True:
            result = self.get_position()
            result = str(result)
            if result:
                self.focus_signal.emit(result)
            if self.stop:
                self.focus.disconnect()
                self.focus = None
                break
            self.sleep(1)

    def move_up(self, distance):
        print(f'move up')
        self.focus.move_relative(distance)

    def move_down(self, distance):
        print(f'move down')
        self.focus.move_relative(distance)

    def set_high_limit(self):
        self.focus.set_high_limit()

    def set_low_limit(self):
        self.focus.set_low_limit()

    def set_zero_position(self):
        self.focus.set_position(0)

    def set_speed(self, velocity):
        self.focus.set_max_speed(velocity)
        # self.focus.move_at_velocity(velocity)

    def get_position(self):
        position = self.focus.get_cur_position()
        if position is not None:
            return position

    def stop_abruptly(self):
        print(f'stop abruptly')
        self.focus.stop_abruptly()

    def stop_run(self):
        self.stop = True

