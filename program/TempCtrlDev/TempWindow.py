import csv
import os
import sys
from datetime import datetime
from pathlib import Path
from queue import Queue

import numpy as np
import time
import matplotlib.pyplot as plt
import serial.tools.list_ports
from PyQt5.QtCore import QUrl, Qt, QThread, pyqtSignal, QObject, QTimer, QElapsedTimer
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtWebEngineWidgets import QWebEngineView
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QDialog, QVBoxLayout, QDialogButtonBox, \
    QTableWidget, QPushButton, QTableWidgetItem, QFileDialog, QComboBox, QLabel, QAction, QMenu, QTreeWidgetItem, \
    QWidget, QHBoxLayout
from matplotlib.ticker import FormatStrFormatter

from program.Ui_MainWindow import Ui_MainWindow
from program.TempCtrlDev.tempdev import AIBUSParam

BASE_DIR = os.path.dirname(os.path.realpath(sys.argv[0]))
config_directory_path = os.path.join(BASE_DIR, 'config')
temp_config_path = os.path.join(BASE_DIR, 'config', 'temp_config')


class TempInputData:
    def __init__(self, iParamNo=None, Value=None, iDevAdd=None):
        self.iParamNo = iParamNo
        self.Value = Value
        self.iDevAdd = iDevAdd


class TempProgramData:
    def __init__(self, temp_seg, time_seg):
        self.temp_seg = temp_seg
        self.time_seg = time_seg


class TempOutputData:
    def __init__(self, pv=None, sv=None, mv=None, step=None, tim=None, state=None):
        self.pv = pv
        self.sv = sv
        self.mv = mv
        self.step = step
        self.tim = tim
        self.state = state


class TempWorker(QThread):
    result_signal = pyqtSignal([list])
    program_signal = pyqtSignal([list])

    def __init__(self, portName, baudRate):
        super().__init__()
        self.aiBUSParam = AIBUSParam(portName=portName, baudRate=baudRate)
        self.start_time = time.time()
        self.stop = False
        self.result = [None for _ in range(2)]
        self.data_queue = Queue()
        self.program_req = Queue()

    def run(self):
        try:
            while True:
                if self.stop:
                    self.aiBUSParam.DisConnect()
                    self.aiBUSParam = None
                    break
                while True:
                    if self.data_queue.empty():
                        break
                    else:
                        data = self.data_queue.get()
                        print(f'data: {[data.Value, data.iDevAdd, data.iParamNo]}')
                        self.write_comm(data)
                while True:
                    if self.program_req.empty() or not self.data_queue.empty():
                        break
                    data = self.program_req.get()
                    program = self.read_program()
                    if program:
                        self.program_signal.emit(program)
                result = self.read_comm()
                if result:
                    self.result_signal.emit(result)
                self.sleep(1)
        except Exception as e:
            print(f'An error occurred when emit temp data: {e}')

    def read_comm(self):
        if self.aiBUSParam:
            try:
                for i in range(2):
                    self.aiBUSParam.ReadParam(iParamNo=74, iDevAdd=i+1)
                    pv = self.aiBUSParam.ParamValue
                    self.aiBUSParam.ReadParam(iParamNo=75, iDevAdd=i+1)
                    sv = self.aiBUSParam.ParamValue
                    self.aiBUSParam.ReadParam(iParamNo=76, iDevAdd=i+1)
                    mv = self.aiBUSParam.ParamValue
                    self.aiBUSParam.ReadParam(iParamNo=46, iDevAdd=i+1)
                    step = self.aiBUSParam.ParamValue
                    self.aiBUSParam.ReadParam(iParamNo=47, iDevAdd=i+1)
                    tim = self.aiBUSParam.ParamValue
                    self.aiBUSParam.ReadParam(iParamNo=27, iDevAdd=i+1)
                    state = self.aiBUSParam.ParamValue
                    # pv = 60
                    # sv = 80
                    # mv = 0
                    # step = -1
                    # tim = 1.5
                    # state = 0
                    if None in [pv, sv, mv, step, tim, state]:
                        self.result[i] = None
                    else:
                        self.result[i] = TempOutputData(pv, sv, mv, step, tim, state)
            except Exception as e:
                print(f'An error occurred when reading temp params: {e}')
        return self.result

    def read_program(self):
        print(f'reading programs')
        try:
            pgm = []
            for k in range(2):
                idev = k + 1
                pgm_temps = []
                pgm_times = []
                i = 0
                while i < 50:
                    temp_a = self.aiBUSParam.ReadParam(iParamNo=i * 2 + 80, iDevAdd=idev)
                    time_a = self.aiBUSParam.ReadParam(iParamNo=i * 2 + 81, iDevAdd=idev)
                    if temp_a and time_a:
                        pgm_temps.append(float(temp_a/10))
                        pgm_times.append(float(time_a/10))
                    else:
                        break
                    i = i + 1
                if pgm_times:
                    if 6432.6 in pgm_times:
                        index_a = pgm_times.index(6432.6)
                    else:
                        index_a = len(pgm_times) - 1
                    pgm_times = pgm_times[:index_a + 1]
                    pgm_temps = pgm_temps[:index_a + 1]
                pgm.append((pgm_temps, pgm_times))
            return pgm
        except Exception as e:
            print(e)
            return None

    def write_comm(self, data: TempInputData):
        self.aiBUSParam.SetParam(iParamNo=data.iParamNo, Value=data.Value, iDevAdd=data.iDevAdd)

    def write_data(self, data: TempInputData):
        self.data_queue.put(data)

    def read_program_settings(self):
        self.program_req.put("req")

    def stop_run(self):
        self.stop = True


class TempProgramTableDialog(QDialog):
    def __init__(self, mainWindow, filename):
        print(f'init dialog')
        super(TempProgramTableDialog, self).__init__(mainWindow)
        self.mainWin = mainWindow
        self.filename = filename
        self.initUI()

    def initUI(self):
        print(f'init dialog...')
        self.setWindowTitle(self.filename)
        self.resize(800, 400)

        # 设置默认的5行3列
        self.tableWidget = QTableWidget(5, 3)
        self.tableWidget.setHorizontalHeaderLabels(['Step', 'Temperature (°C)', 'Time (min)'])
        self.tableWidget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

        # 初始化第一列的自增数字，设置为不可编辑
        self.fillStepColumn()

        # 隐藏行号
        self.tableWidget.verticalHeader().setVisible(False)

        # 使第二列和第三列可编辑
        self.makeColumnsEditable(1, 2)

        # 调整列宽以适应内容
        self.tableWidget.resizeColumnsToContents()
        self.tableWidget.horizontalHeader().setStretchLastSection(True)

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
        self.zoneComboBox.addItem("ZoneA")
        self.zoneComboBox.addItem("ZoneB")
        hlayout.addWidget(self.zoneComboBox)

        # 添加写入程序按钮
        self.writeButton = QPushButton("写入")
        self.writeButton.clicked.connect(self.mainWin.writeBuffer)
        hlayout.addWidget(self.writeButton)

        layout.addLayout(hlayout)
        # 添加保存和取消按钮
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.buttonBox.button(QDialogButtonBox.Save).setText("保存")
        self.buttonBox.button(QDialogButtonBox.Cancel).setText("取消")
        self.buttonBox.accepted.connect(self.saveTable)
        self.buttonBox.rejected.connect(self.reject)
        layout.addWidget(self.buttonBox)

    def fillStepColumn(self):
        for row in range(self.tableWidget.rowCount()):
            item = QTableWidgetItem(str(row + 1))
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.tableWidget.setItem(row, 0, item)

    def makeColumnsEditable(self, startColumn, endColumn):
        for column in range(startColumn, endColumn + 1):
            for row in range(self.tableWidget.rowCount()):
                item = QTableWidgetItem()
                self.tableWidget.setItem(row, column, item)

    def addRow(self):
        # 添加新行到表格，并设置第一列为自增数字
        self.tableWidget.insertRow(self.tableWidget.rowCount())
        self.fillStepColumn()

    def delRow(self):
        self.tableWidget.removeRow(self.tableWidget.rowCount() - 1)

    def saveTable(self):
        if self.filename == "New Program":
            filepath, _ = QFileDialog.getSaveFileName(self, "Save Table Data", "", "CSV Files (*.csv)")
        else:
            filepath = os.path.join(temp_config_path, f"{self.filename}.csv")
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
                        row_data = []
                        for column in range(self.tableWidget.columnCount()):
                            # 检查项是否存在，如果不存在则添加空字符串
                            item = self.tableWidget.item(row, column) if self.tableWidget.item(row, column) else None
                            row_data.append(item.text() if item else '')
                        print(row_data)
                        writer.writerow(row_data)
                print(f"Table data saved to {filepath}.")
                self.accept()  # 关闭对话框
            except Exception as e:
                print(f"An error occurred while writing to the file: {e}")
                QMessageBox.critical(self, "Error", f"An error occurred while writing to the file: {e}")

    def loadTable(self, filename):
        filepath = os.path.join(temp_config_path, f'{filename}.csv')
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
                    self.tableWidget.insertRow(row_idx - 1)  # 行索引从0开始
                    for column_idx, value in enumerate(row_data):
                        item = QTableWidgetItem(value)
                        if column_idx == 0:  # 第一列设置为不可编辑
                            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                        self.tableWidget.setItem(row_idx - 1, column_idx, item)
        except Exception as e:
            print(f"An error occurred while reading the file: {e}")
            QMessageBox.critical(self, "Error", f"An error occurred while reading the file: {e}")

