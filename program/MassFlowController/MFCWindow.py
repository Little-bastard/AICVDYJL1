import csv
import os
import sys
import time
from queue import Queue

import numpy as np
import serial
import serial.tools.list_ports
from PyQt5.QtCore import QTimer, QThread, pyqtSignal, QMutex, Qt, QTime
from PyQt5.QtWidgets import QMainWindow, QMessageBox, QApplication, QButtonGroup, QLabel, QWidget, QDialog, \
    QTableWidget, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, QDialogButtonBox, QTableWidgetItem, QFileDialog, \
    QHeaderView, QTimeEdit
from matplotlib import pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.ticker import MultipleLocator

from program.MassFlowController.mfcdev import MFCComm
from program.Mainwindow import Ui_MainWindow

BASE_DIR = os.path.dirname(os.path.realpath(sys.argv[0]))
mfc_config_path = os.path.join(BASE_DIR, 'config', 'mfc_config')


class MFCProgramTableDialog(QDialog):
    def __init__(self, mainWindow, filename):
        super(MFCProgramTableDialog, self).__init__(mainWindow)
        self.mainWin = mainWindow
        self.filename = filename
        self.initUI()

    def initUI(self):
        self.setWindowTitle(self.filename)
        self.resize(800, 400)

        # 设置默认的5行3列
        self.tableWidget = QTableWidget(1, 3)
        self.tableWidget.setHorizontalHeaderLabels(['时间', '设定点', '单位'])
        self.tableWidget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

        # 隐藏行号
        self.tableWidget.verticalHeader().setVisible(False)

        # 调整列宽以适应内容
        self.tableWidget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # 填充数据
        for i in range(1):
            time_edit = QTimeEdit()
            time_edit.setDisplayFormat("HH:mm:ss")
            time_edit.setTime(QTime(0, 0, 0))  # 默认时间
            self.tableWidget.setCellWidget(i, 0, time_edit)
            self.tableWidget.setItem(i, 1, QTableWidgetItem("0"))
            self.tableWidget.setItem(i, 2, QTableWidgetItem("mL/min"))

        # 布局管理
        layout = QVBoxLayout()
        layout.addWidget(self.tableWidget)
        hlayout = QHBoxLayout()
        self.setLayout(layout)

        # 添加"添加行"按钮
        self.addRowButton = QPushButton("添加行")
        self.addRowButton.clicked.connect(self.addRow)
        hlayout.addWidget(self.addRowButton)

        self.delRowButton = QPushButton("删除行")
        self.delRowButton.clicked.connect(self.delRow)
        hlayout.addWidget(self.delRowButton)

        # 添加温区选择框
        self.zoneComboBox = QComboBox()
        for i in range(16):
            self.zoneComboBox.addItem(f"{i}")
        hlayout.addWidget(self.zoneComboBox)

        # 添加写入程序按钮
        self.writeButton = QPushButton("写入")
        self.writeButton.clicked.connect(self.mainWin.writeMFCProgram)
        hlayout.addWidget(self.writeButton)

        layout.addLayout(hlayout)
        # 添加保存和取消按钮
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.buttonBox.button(QDialogButtonBox.Save).setText("保存")
        self.buttonBox.button(QDialogButtonBox.Cancel).setText("取消")
        self.buttonBox.accepted.connect(self.saveTable)
        self.buttonBox.rejected.connect(self.reject)
        layout.addWidget(self.buttonBox)

    def addRow(self):
        # 添加新行到表格，并设置第一列为自增数字
        rowcount = self.tableWidget.rowCount()
        self.tableWidget.insertRow(rowcount)
        time_edit = QTimeEdit()
        time_edit.setDisplayFormat("HH:mm:ss")
        time_edit.setTime(QTime(0, 0, 0))  # 默认时间
        self.tableWidget.setCellWidget(rowcount, 0, time_edit)
        self.tableWidget.setItem(rowcount, 1, QTableWidgetItem("0"))
        self.tableWidget.setItem(rowcount, 2, QTableWidgetItem("mL/min"))

    def delRow(self):
        self.tableWidget.removeRow(self.tableWidget.rowCount() - 1)

    def saveTable(self):
        if self.filename == "New Program":
            filepath, _ = QFileDialog.getSaveFileName(self, "Save Table Data", "", "CSV Files (*.csv)")
        else:
            filepath = os.path.join(mfc_config_path, f"{self.filename}.csv")
        try:
            if not os.path.exists(filepath):
                with open(filepath, mode='w', encoding='utf-8') as ff:
                    print("文件创建成功！")
        except Exception as e:
            print(e)
        if filepath:
            try:
                # 打开文件准备写入
                with open(filepath, mode='w', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)

                    # 获取水平头标签
                    headers = [self.tableWidget.horizontalHeaderItem(i).text() for i in
                               range(self.tableWidget.columnCount())]
                    writer.writerow(headers)

                    # 写入表格数据
                    for row in range(self.tableWidget.rowCount()):
                        time = self.tableWidget.cellWidget(row, 0).time().toString("HH:mm:ss")
                        value = self.tableWidget.item(row, 1).text()
                        unit = self.tableWidget.item(row, 2).text()
                        writer.writerow([time, value, unit])
                print(f"Table data saved to {filepath}.")
                self.accept()  # 关闭对话框
            except Exception as e:
                print(f"An error occurred while writing to the file: {e}")
                QMessageBox.critical(self, "Error", f"An error occurred while writing to the file: {e}")

    def loadTable(self, filename):
        filepath = os.path.join(mfc_config_path, f'{filename}.csv')
        try:
            with open(filepath, mode='r', newline='', encoding='utf-8') as file:
                reader = csv.reader(file)
                # 清空现有表格数据
                self.tableWidget.clearContents()
                self.tableWidget.setRowCount(0)

                # 读取CSV文件的头部作为表头
                headers = next(reader, None)
                if headers:
                    self.tableWidget.setHorizontalHeaderLabels(headers)

                # 填充表格数据
                for row_idx, row_data in enumerate(reader, start=1):
                    print(f'row data: {row_data[0]}')
                    self.tableWidget.insertRow(row_idx-1)  # 行索引从0开始
                    time_edit = QTimeEdit()
                    time_edit.setDisplayFormat("HH:mm:ss")
                    time_edit.setTime(QTime.fromString(row_data[0], "HH:mm:ss"))
                    self.tableWidget.setCellWidget(row_idx-1, 0, time_edit)
                    self.tableWidget.setItem(row_idx-1, 1, QTableWidgetItem(row_data[1]))
                    self.tableWidget.setItem(row_idx-1, 2, QTableWidgetItem(row_data[2]))
        except Exception as e:
            print(f"An error occurred while reading the file: {e}")
            QMessageBox.critical(self, "Error", f"An error occurred while reading the file: {e}")


class MFCProgramData:
    def __init__(self, time, value):
        self.time = time
        self.value = value

class MFCInputData:
    def __init__(self, value=None, id=None, addr=None):
        self.value = value
        self.id = id
        self.addr = addr


class MFCOutputData:
    def __init__(self, pv=None, sv=None, ctrl_mode=None, switch_state=None, unit=None, full_scale=None):
        self.pv = pv
        self.sv = sv
        self.ctrl_mode = ctrl_mode
        self.switch_state = switch_state
        self.unit = unit
        self.fs = full_scale


class MFCWorker(QThread):
    result_signal = pyqtSignal([list])

    def __init__(self, portName, baudRate):
        super().__init__()
        self.mfc_comm = MFCComm(portName=portName, baudRate=baudRate)
        self.start_time = time.time()
        self.stop = False
        self.data_queue = Queue()
        self.mutex = QMutex()
        self.result = [None for _ in range(16)]

    def run(self):
        try:
            while not self.stop:
                while True:
                    if self.data_queue.empty():
                        break
                    task = self.data_queue.get()
                    self.write_comm(task)
                result = self.read_comm()
                if result:
                    self.result_signal.emit(result)
                if self.stop:
                    break
                self.sleep(1)
        except Exception as e:
            print(f'An error occurred when emit mfc data: {e}')

    def read_comm(self):
        if self.mfc_comm:
            try:
                for i in range(16):
                    sv = self.mfc_comm.read_sv(id=i)
                    # if i == 2 or i == 0:
                    #     sv = 20
                    if sv is not None:
                        pv = self.mfc_comm.read_pv(id=i)
                        cmode = self.mfc_comm.read_switch_single(id=i, addr=3)
                        switch_state = self.mfc_comm.read_switch_vctrl(id=i)
                        unit = self.mfc_comm.read_unit(id=i)
                        fs = self.mfc_comm.read_fs(id=i)
                        # if i == 2:
                        #     pv = 20
                        #     cmode = 1
                        #     switch_state = 2
                        #     unit = 'mL/min'
                        #     fs = 500
                        # if i == 0:
                        #     pv = 18
                        #     cmode = 0
                        #     switch_state = 1
                        #     unit = 'mL/min'
                        #     fs = 100

                        if None in [sv, pv, cmode, switch_state, unit, fs]:
                            self.result[i] = None
                        else:
                            self.result[i] = MFCOutputData(pv=pv, sv=sv, ctrl_mode=cmode, switch_state=switch_state, unit=unit, full_scale=fs)
                return self.result
            except Exception as e:
                print(f'An error occurred when read mfc parameter: {e}')

    def write_comm(self, task):
        try:
            if task['type'] == 'sv':
                self.mfc_comm.write_sv(value=task['data'].value, id=task['data'].id)
            if task['type'] == 'switch':
                self.mfc_comm.write_switch(value=task['data'].value, id=task['data'].id, addr=task['data'].addr)
        except Exception as e:
            print(f'An error occurred when write mfc parameter: {e}')

    def write_data(self, datatype, data):
        self.data_queue.put({'type': datatype, 'data': data})

    def stop_run(self):
        self.stop = True
        self.mfc_comm.DisConnect()
        self.mfc_comm = None


class MFCWindow(QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None):
        super(MFCWindow, self).__init__(parent)
        self.mfcData_2 = MFCOutputData()
        self.mfcData_0 = MFCOutputData()
        self.button_group = None
        self.mfc_comm = None
        self.setupUi(self)
        self.init_mfc_ui()

    def init_mfc_ui(self):
        ports_list = list(serial.tools.list_ports.comports())
        ports_name = [port.name for port in ports_list]
        self.CBB_mfc_port.clear()
        self.CBB_mfc_port.addItems(ports_name)
        baudrate_list = ["4800", "9600", "19200", "38400", "43000", "56000", "57600"]
        self.BT_set_mfc_sv.clicked.connect(self.onSetSV)
        self.CBB_mfc_buadrate.clear()
        self.CBB_mfc_buadrate.addItems(baudrate_list)
        self.button_group = QButtonGroup()
        self.button_group.addButton(self.RB_0, 0)
        self.button_group.addButton(self.RB_2, 2)

        # 创建一个Figure和FigureCanvas
        self.figure_mfc = Figure()
        self.canvas_mfc = FigureCanvas(self.figure_mfc)
        self.ax_mfc = self.figure_mfc.add_subplot(111)
        self.VLayout_mfc_display.addWidget(self.canvas_mfc)
        #初始化图表
        self.ax_mfc.set_xlim(0, 20)  # 设置x轴的范围，可以根据需要调整
        self.ax_mfc.set_ylim(0, 100)  # 设置y轴的范围
        self.line_mfc_pv_0, = self.ax_mfc.plot([], [], 'r-')  # 'r-' 表示红色线条
        self.line_mfc_sv_0, = self.ax_mfc.plot([], [], 'b-')  # 'r-' 表示红色线条
        self.line_mfc_pv_2, = self.ax_mfc.plot([], [], 'r-')  # 'r-' 表示红色线条
        self.line_mfc_sv_2, = self.ax_mfc.plot([], [], 'b-')  # 'r-' 表示红色线条
        self.ax_mfc.xaxis.set_major_locator(MultipleLocator(4))

        self.timer_mfc = QTimer(self)
        self.timer_mfc.timeout.connect(self.updateMFCData)
        self.timer_mfc.start(1000)

    def onConnectMFC(self):
        try:
            print(f'CBB_temp_port:{self.CBB_temp_port.currentText()}')
            self.mfc_comm = MFCComm(portName=self.CBB_mfc_port.currentText(), baudRate=self.CBB_mfc_buadrate.currentText())
        except Exception as e:
            print(f"An error occurred connect to mfc comm: {e}")
            QMessageBox.critical(self, "Error", f"An error occurred connect to mfc comm: {e}")

    def onSetSV(self):
        print(f'set value')
        if self.mfc_comm:
            try:
                sv = self.SB_mfc_sv.value()
                self.mfc_comm.write_sv(value=sv, id=self.button_group.checkedId())
            except Exception as e:
                print(f"An error occurred when set mfc value: {e}")
                QMessageBox.critical(self, "Error", f"An error occurred when set mfc value: {e}")

    def onValueCtrl(self):
        self.mfc_comm.write_switch(value=True, id=self.button_group.checkedId(), addr=1)

    def onSwitchClean(self):
        self.mfc_comm.write_switch(value=True, id=self.button_group.checkedId(), addr=2)

    def onSwitchClose(self):
        self.mfc_comm.write_switch(value=True, id=self.button_group.checkedId(), addr=0)

    def onAnalogMode(self):
        self.mfc_comm.write_switch(value=False, id=self.button_group.checkedId(), addr=3)

    def onDigitalMode(self):
        self.mfc_comm.write_switch(value=True, id=self.button_group.checkedId(), addr=3)

    def readMFCParam(self):
        try:
            if self.mfc_comm:
                sv_0 = self.mfc_comm.read_sv(id=0)
                pv_0 = self.mfc_comm.read_pv(id=0)
                sv_2 = self.mfc_comm.read_sv(id=2)
                pv_2 = self.mfc_comm.read_pv(id=2)
                cmode_0 = self.mfc_comm.read_switch_single(id=0, addr=3)
                cmode_2 = self.mfc_comm.read_switch_single(id=2, addr=3)
                switch_state_0 = self.mfc_comm.read_switch_vctrl(id=0)
                switch_state_2 = self.mfc_comm.read_switch_vctrl(id=2)
                self.mfcData_0 = MFCOutputData(pv=pv_0, sv=sv_0, ctrl_mode=cmode_0, switch_state=switch_state_0)
                self.mfcData_2 = MFCOutputData(pv=pv_2, sv=sv_2, ctrl_mode=cmode_2, switch_state=switch_state_2)
        except Exception as e:
            print(f'An error occurred when read mfc parameter: {e}')

    def updateMFCData(self):
        # 读取MFC参数
        self.readMFCParam()
        # 显示流量设定值和实际值
        self.lbl_pv_mfc0.setText(str(self.mfcData_0.pv))
        self.lbl_sv_mfc0.setText(str(self.mfcData_0.sv))
        self.lbl_pv_mfc2.setText(str(self.mfcData_2.pv))
        self.lbl_sv_mfc2.setText(str(self.mfcData_2.sv))
        # 显示控制模式
        if self.button_group.checkedId() == 0:
            if self.mfcData_0.ctrl_mode == -1:
                self.RB_mfc_crtllock.setChecked(True)
            elif self.mfcData_0.ctrl_mode == 0:
                self.RB_mfc_analog.setChecked(True)
            elif self.mfcData_0.ctrl_mode == 1:
                self.RB_mfc_digital.setChecked(True)
            else:
                print(f'ctrl mode error')
        elif self.button_group.checkedId() == 2:
            if self.mfcData_2.ctrl_mode == -1:
                self.RB_mfc_crtllock.setChecked(True)
            elif self.mfcData_2.ctrl_mode == 0:
                self.RB_mfc_analog.setChecked(True)
            elif self.mfcData_2.ctrl_mode == 1:
                self.RB_mfc_digital.setChecked(True)
            else:
                print(f'ctrl mode error')
        else:
            print(f'MFC Dev number is not Chosen')
        # 显示阀控状态
        if self.button_group.checkedId() == 0:
            if self.mfcData_0.switch_state == -1:
                self.RB_mfc_switchlock.setChecked(True)
            elif self.mfcData_0.switch_state == 1:
                self.RB_mfc_close.setChecked(True)
            elif self.mfcData_0.switch_state == 2:
                self.RB_mfc_vctrl.setChecked(True)
            elif self.mfcData_0.switch_state == 4:
                self.RB_mfc_clean.setChecked(True)
            else:
                print(f'switch state error')
        elif self.button_group.checkedId() == 2:
            if self.mfcData_2.switch_state == -1:
                self.RB_mfc_switchlock.setChecked(True)
            elif self.mfcData_2.switch_state == 1:
                self.RB_mfc_close.setChecked(True)
            elif self.mfcData_2.switch_state == 2:
                self.RB_mfc_vctrl.setChecked(True)
            elif self.mfcData_2.switch_state == 4:
                self.RB_mfc_clean.setChecked(True)
            else:
                print(f'switch state error')
        else:
            print(f'MFC Dev number is not Chosen')
        if ((self.button_group.checkedId() == 0 and self.mfcData_0.switch_state == 2 and self.mfcData_0.ctrl_mode == 1)
                or (self.button_group.checkedId() == 2 and self.mfcData_2.switch_state == 2 and
                    self.mfcData_2.ctrl_mode == 1)):
            self.BT_set_mfc_sv.setEnabled(True)
        # 绘制mfc_0流量曲线
        current_time = time.time()
        # 更新line_mfc_pv_0
        pv_0 = np.random.randint(0, 10)  # 随机生成流量值
        xdata_mfc_pv_0, ydata_mfc_pv_0 = self.line_mfc_pv_0.get_data()
        xdata_mfc_pv_0 = np.append(xdata_mfc_pv_0, current_time)
        ydata_mfc_pv_0 = np.append(ydata_mfc_pv_0, pv_0)
        # 限制数据点数量，避免内存无限增长
        if len(xdata_mfc_pv_0) > 30:  # 保留最近120个数据点，即2分钟
            xdata_mfc_pv_0 = xdata_mfc_pv_0[-30:]
            ydata_mfc_pv_0 = ydata_mfc_pv_0[-30:]
        # 更新line_mfc_sv_0
        sv_0 = 10
        xdata_mfc_sv_0, ydata_mfc_sv_0 = self.line_mfc_sv_0.get_data()
        xdata_mfc_sv_0 = np.append(xdata_mfc_sv_0, current_time)
        ydata_mfc_sv_0 = np.append(ydata_mfc_sv_0, sv_0)
        # 限制数据点数量，避免内存无限增长
        if len(xdata_mfc_sv_0) > 30:  # 保留最近120个数据点，即2分钟
            xdata_mfc_sv_0 = xdata_mfc_sv_0[-30:]
            ydata_mfc_sv_0 = ydata_mfc_sv_0[-30:]

        # 更新line_mfc_pv_2
        pv_2 = np.random.randint(0, 10)  # 随机生成流量值
        xdata_mfc_pv_2, ydata_mfc_pv_2 = self.line_mfc_pv_2.get_data()
        xdata_mfc_pv_2 = np.append(xdata_mfc_pv_2, current_time)
        ydata_mfc_pv_2 = np.append(ydata_mfc_pv_2, pv_2)
        # 限制数据点数量，避免内存无限增长
        if len(xdata_mfc_pv_2) > 30:  # 保留最近120个数据点，即2分钟
            xdata_mfc_pv_2 = xdata_mfc_pv_2[-30:]
            ydata_mfc_pv_2 = ydata_mfc_pv_2[-30:]
        # 更新line_mfc_sv_2
        sv_2 = 10
        xdata_mfc_sv_2, ydata_mfc_sv_2 = self.line_mfc_sv_2.get_data()
        xdata_mfc_sv_2 = np.append(xdata_mfc_sv_2, current_time)
        ydata_mfc_sv_2 = np.append(ydata_mfc_sv_2, sv_2)
        # 限制数据点数量，避免内存无限增长
        if len(xdata_mfc_sv_2) > 30:  # 保留最近120个数据点，即2分钟
            xdata_mfc_sv_2 = xdata_mfc_sv_2[-30:]
            ydata_mfc_sv_2 = ydata_mfc_sv_2[-30:]

        # 更新图表
        if self.button_group.checkedId() == 0:
            self.line_mfc_pv_0.set_visible(True)
            self.line_mfc_sv_0.set_visible(True)
            self.line_mfc_pv_2.set_visible(False)
            self.line_mfc_sv_2.set_visible(False)
            self.line_mfc_pv_0.set_data(xdata_mfc_pv_0, ydata_mfc_pv_0)
            self.line_mfc_sv_0.set_data(xdata_mfc_sv_0, ydata_mfc_sv_0)
            self.ax_mfc.relim()  # 重新计算轴的限制
            self.ax_mfc.autoscale_view()  # 自动缩放视图
            # 滚动x轴
            self.ax_mfc.set_xlim(max(0, xdata_mfc_pv_0[-1] - 20), xdata_mfc_pv_0[-1])
            self.ax_mfc.set_ylim(0, 100)
            # 绘制更新后的图表
            self.canvas_mfc.draw()
        elif self.button_group.checkedId() == 2:

            self.line_mfc_pv_0.set_visible(False)
            self.line_mfc_sv_0.set_visible(False)
            self.line_mfc_pv_2.set_visible(True)
            self.line_mfc_sv_2.set_visible(True)

            self.line_mfc_pv_2.set_data(xdata_mfc_pv_2, ydata_mfc_pv_2)
            self.line_mfc_sv_2.set_data(xdata_mfc_sv_2, ydata_mfc_sv_2)
            self.ax_mfc.relim()  # 重新计算轴的限制
            self.ax_mfc.autoscale_view()  # 自动缩放视图
            # 滚动x轴
            self.ax_mfc.set_xlim(max(0, xdata_mfc_pv_2[-1] - 20), xdata_mfc_pv_2[-1])
            self.ax_mfc.set_ylim(0, 500)
            # 绘制更新后的图表
            self.canvas_mfc.draw()
        else:
            print(f'MFC Dev number is not Chosen')



if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        mw = MFCWindow()
        mw.show()
        sys.exit(app.exec_())
    except Exception as e:
        print(e)
