import random
import sys
import time
from datetime import datetime

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QMainWindow, QApplication, QVBoxLayout, QWidget
from matplotlib import pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas


class MyMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi()

    def setupUi(self):
        self.setWindowTitle("温度曲线")
        self.figure_a, self.ax_a = plt.subplots()
        self.canvas_a = FigureCanvas(self.figure_a)
        self.times = []
        self.temperatures_pv = []
        self.line_pv_a, = self.ax_a.plot(self.times, self.temperatures_pv, 'ro')  # 'r-' 表示红色线条



        VLayout_tempDisplay_a = QVBoxLayout()
        VLayout_tempDisplay_a.addWidget(self.canvas_a, stretch=1)

        central_widget = QWidget()
        central_widget.setLayout(VLayout_tempDisplay_a)
        self.setCentralWidget(central_widget)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.updateGraph)
        self.timer.start(1000)

        # 设置时间轴的刻度和显示
        ctime = time.time()
        self.ax_a.set_xlim(ctime+1, ctime + 300)
        xticks = [ctime+i*60+1 for i in range(6)]
        xlabels = [datetime.fromtimestamp(ts).strftime('%H:%M:%S') for ts in xticks]
        self.ax_a.set_xticks(xticks, xlabels)

    def updateGraph(self):

        temperature_pv = 10
        try:
            ctime = time.time()
            if len(self.times) >= 300:  # 如果数据点超过50个，移除最早的点
                self.temperatures_pv = []
                self.times = []
                self.ax_a.set_xlim(ctime, ctime+299)
                xticks = [ctime+i*60 for i in range(6)]
                xlabels = [datetime.fromtimestamp(ts).strftime('%H:%M:%S') for ts in xticks]
                self.ax_a.set_xticks(xticks, xlabels)

            self.temperatures_pv.append(temperature_pv)
            self.times.append(ctime)

            self.line_pv_a.set_data(self.times, self.temperatures_pv)
            # 更新x轴的范围
            # self.ax_a.set_xlim(current_time - 300, current_time)
            self.ax_a.relim()  # 重新计算坐标轴的界限
            self.ax_a.autoscale_view(True, True, True)  # 自动缩放
            self.canvas_a.draw()  # 重绘画布
        except Exception as e:
            print(f'an error occurred: {e}')

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # 设置样式
    ex = MyMainWindow()
    ex.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()