import csv
import os
import sys
import time
from queue import Queue
from PyQt5.QtCore import QThread, pyqtSignal, QMutex, Qt, QTime
from PyQt5.QtWidgets import (QMessageBox, QDialog, QTableWidget, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox,
                             QDialogButtonBox, QTableWidgetItem, QFileDialog, QHeaderView, QTimeEdit)
from program.MassFlowController.mfcdev import MFCComm

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
            while True:
                while True:
                    if self.data_queue.empty():
                        break
                    task = self.data_queue.get()
                    self.write_comm(task)
                result = self.read_comm()
                if result:
                    self.result_signal.emit(result)
                if self.stop:
                    self.mfc_comm.DisConnect()
                    self.mfc_comm = None
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

