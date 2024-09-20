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

from program.Mainwindow import Ui_MainWindow
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
                    if self.program_req.empty():
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


class WebEngineView(QWebEngineView):

    def __init__(self):
        super(WebEngineView, self).__init__()

    def createWindow(self, QWebEnginePage_WebWindowType):
        return self


class TempWidget(QWidget):
    def __init__(self, parant=None):
        super(QWidget, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.init_tempctrl_ui()

    def init_tempctrl_ui(self):
        self.total_set_time_b = None
        self.total_set_time_a = None
        self.max_temperature_a = None
        self.max_temperature_b = None
        self.original_item_name = None
        self.dialog = None
        self.signal_comm = None
        self.flag_of_signal = False
        self.program_a = None
        self.program_b = None
        self.aiBUSParam = None
        self.tempdevData_a = None
        self.tempdevData_b = None
        self.temp_threshold = None
        self.temp_time_interval = 100  # ms
        self.dps = 1000 / self.temp_time_interval

        self.setWindowTitle('AICVD')
        self.selected_color = "background-color: rgba(85, 170, 255, 50); border: 1px solid rgba(0, 85, 255, 220); padding: 4px;border-radius: 4px"
        self.default_color = ""

        self.actionCreate = QAction(self)
        icon1 = QtGui.QIcon()
        icon1.addPixmap(QtGui.QPixmap("C:/Users/LuoJie/.designer/backup/icon/添加文件.png"), QtGui.QIcon.Normal,
                        QtGui.QIcon.Off)
        self.actionCreate.setIcon(icon1)
        self.actionCreate.setObjectName("actionCreate")
        self.actionOpen = QAction(self)
        icon2 = QtGui.QIcon()
        icon2.addPixmap(QtGui.QPixmap("C:/Users/LuoJie/.designer/backup/icon/打开.png"), QtGui.QIcon.Normal,
                        QtGui.QIcon.Off)
        self.actionOpen.setIcon(icon2)
        self.actionOpen.setObjectName("actionOpen")
        self.toolBar.addAction(self.actionCreate)
        self.toolBar.addAction(self.actionOpen)
        self.actionCreate.triggered.connect(self.createFile)  # type: ignore
        self.actionOpen.triggered.connect(self.openFile)  # type: ignore

        self.BT_hold_a.clicked.connect(self.onHoldA)  # type: ignore
        self.BT_run_a.clicked.connect(self.onRunA)  # type: ignore
        self.BT_hold_b.clicked.connect(self.onHoldB)  # type: ignore
        self.BT_run_b.clicked.connect(self.onRunB)  # type: ignore
        self.BT_stop_b.clicked.connect(self.onStopB)  # type: ignore
        self.BT_stop_a.clicked.connect(self.onStopA)  # type: ignore
        self.BT_connect_tempDev.clicked.connect(self.onConnectTempDev)  # type: ignore
        self.BT_connect_signalComm.clicked.connect(self.onConnectSignalComm)  # type: ignore
        self.BT_sendSignal.clicked.connect(self.onConnectSignalComm)  # type: ignore
        self.BT_set_temp_threshold.clicked.connect(self.onSetTempThreshold)
        self.figure_a, self.ax_a = plt.subplots()
        self.figure_a.set_facecolor('none')
        self.ax_a.set_facecolor('none')
        self.ax_a.grid(True, linestyle='--', alpha=0.5)
        self.canvas_a = FigureCanvas(self.figure_a)
        self.line_pv_a, = self.ax_a.plot([], [], 'r-')  # 'r-' 表示红色线条
        self.line_sv_a, = self.ax_a.plot([], [], 'b-')
        self.label_date_a = QLabel("date")
        self.VLayout_tempDisplay_a.addWidget(self.canvas_a, stretch=1)

        self.figure_b, self.ax_b = plt.subplots()
        self.figure_b.set_facecolor('none')
        self.ax_b.set_facecolor('none')
        self.ax_b.grid(True, linestyle='--', alpha=0.5)
        self.canvas_b = FigureCanvas(self.figure_b)
        self.line_pv_b, = self.ax_b.plot([], [], 'r-')  # 'r-' 表示红色线条
        self.line_sv_b, = self.ax_b.plot([], [], 'b-')
        self.label_date_b = QLabel("date")
        self.VLayout_tempDisplay_b.addWidget(self.canvas_b, stretch=1)

        self.tree_config.setColumnCount(1)
        self.tree_config.setHeaderLabels(["温度程序配置"])
        self.rootItem = QTreeWidgetItem(self.tree_config, ["Configuration"])

        self.tree_config.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_config.customContextMenuRequested.connect(self.showContextMenu)
        self.tree_config.itemChanged.connect(self.handleItemChange)
        # 列出文件夹内的所有文件
        for filepath in os.listdir(temp_config_path):
            if filepath.endswith('.csv'):
                # 获取文件的完整路径
                file_path = os.path.join(temp_config_path, filepath)
                # 创建一个新的QTreeWidgetItem并添加到QTreeWidget
                item = QTreeWidgetItem(self.rootItem, [os.path.splitext(filepath)[0]])
                item.setToolTip(0, file_path)
        # 展开所有项以便查看
        self.tree_config.expandAll()
        self.timer_temp = QTimer(self)
        self.timer_temp.timeout.connect(self.updateTempData)  # 连接定时器信号到槽函数

        # 设置时间轴的刻度和显示
        self.timerange = 120
        ctime = time.time()
        xticks = [ctime + i * self.timerange / 4 + 1 for i in range(5)]
        xlabels = [datetime.fromtimestamp(ts).strftime('%H:%M:%S') for ts in xticks]
        self.ax_a.set_xlim(ctime + 1, ctime + self.timerange)
        self.ax_a.set_xticks(xticks, xlabels)
        self.ax_a.yaxis.set_major_formatter(FormatStrFormatter('%.1f'))
        self.ax_b.set_xlim(ctime + 1, ctime + self.timerange)
        self.ax_b.set_xticks(xticks, xlabels)
        self.ax_b.yaxis.set_major_formatter(FormatStrFormatter('%.1f'))

        # 设置可用的comm端口号
        ports_list = list(serial.tools.list_ports.comports())
        ports_name = [port.name for port in ports_list]
        self.CBB_temp_port.clear()
        self.CBB_temp_port.addItems(ports_name)

        self.CBB_signal_port.clear()
        self.CBB_signal_port.addItems(ports_name)


    def showContextMenu(self, position):
        # 创建右键菜单
        try:
            selected = self.tree_config.itemAt(position)
            print(f'selected:{selected}')
            menu = QMenu(self.tree_config)
            addNewAction = QAction('添加', self.tree_config)
            renameAction = QAction('重命名', self.tree_config)
            editAction = QAction('编辑', self.tree_config)
            deleteAction = QAction('删除', self.tree_config)
            updateAction = QAction('刷新', self.tree_config)
            if selected:
                if selected == self.rootItem:
                    # 添加动作到菜单
                    menu.addAction(addNewAction)
                    addNewAction.triggered.connect(self.addNewItem)
                else:
                    menu.addAction(editAction)
                    menu.addAction(deleteAction)
                    menu.addAction(renameAction)
                    renameAction.triggered.connect(self.renameItem)
                    editAction.triggered.connect(self.editItem)
                    deleteAction.triggered.connect(self.deleteItem)
            else:
                menu.addAction(updateAction)
                updateAction.triggered.connect(self.updateItem)
            # 显示菜单
            menu.exec_(self.tree_config.viewport().mapToGlobal(position))
        except Exception as e:
            print(e)

    def addNewItem(self):
        selected = self.tree_config.currentItem()
        if not selected.parent():
            newItem = QTreeWidgetItem(self.rootItem, ["New Program"])

    def renameItem(self):
        selected = self.tree_config.currentItem()
        print(f'selected: {selected.text(0)}')
        selected.setFlags(selected.flags() | Qt.ItemIsEditable)
        self.tree_config.editItem(selected)
        print(f'selected: {selected.text(0)}')
        self.original_item_name = selected.text(0)

    def handleItemChange(self, item, column):
        # 当项被更改后，这个槽函数将被调用，并且接收被编辑的项和列索引
        if column == 0:  # 通常第一列包含项的文本
            filepath = os.path.join(temp_config_path, f'{self.original_item_name}.csv')
            filename_new = item.text(0)
            filepath_new = os.path.join(temp_config_path, f'{filename_new}.csv')
            if os.path.exists(filepath):
                print(f'old: {filepath}')
                print(f'new: {filepath_new}')
                try:
                    os.rename(filepath, filepath_new)
                    print(f'文件已重命名')
                except OSError as e:
                    print(f'重命名文件时出错： {e}')

    def editItem(self):
        # 编辑项的槽函数
        selected = self.tree_config.currentItem()

        if selected:
            print(f'selected:{selected.text(0)}')
            self.editFile(selected.text(0))

    def deleteItem(self):
        # 删除项的槽函数
        selected = self.tree_config.currentItem()
        print(f'{selected.parent()}')
        if selected:
            if selected.parent():
                # 如果是子节点，从父节点移除
                filepath = Path(os.path.join(temp_config_path, f'{selected.text(0)}.csv'))
                if os.path.exists(filepath):
                    try:
                        filepath.unlink()
                    except Exception as e:
                        print(f'删除文件时出错： {e}')
                selected.parent().takeChild(selected.parent().indexOfChild(selected))
            else:
                # 如果是顶级节点，从树中移除
                self.tree_config.takeTopLevelItem(self.tree_config.indexOfTopLevelItem(selected))
            # QMessageBox.information(self, "信息", "项已删除")

    def updateItem(self):
        while self.rootItem.childCount() > 0:
            # takeChild 方法删除子节点
            self.rootItem.takeChild(self.rootItem.childCount() - 1)
        # 列出文件夹内的所有文件
        for filepath in os.listdir(temp_config_path):
            if filepath.endswith('.csv'):
                # 获取文件的完整路径
                file_path = os.path.join(temp_config_path, filepath)
                # 创建一个新的QTreeWidgetItem并添加到QTreeWidget
                item = QTreeWidgetItem(self.rootItem, [os.path.splitext(filepath)[0]])
                item.setToolTip(0, file_path)
        # 展开所有项以便查看
        self.tree_config.expandAll()

    def onConnectTempDev(self):
        try:
            print(f'CBB_temp_port:{self.CBB_temp_port.currentText()}')
            self.aiBUSParam = AIBUSParam(portName=f"{self.CBB_temp_port.currentText()}", baudRate=9600)
            self.worker_a = TempWorker(self.aiBUSParam, 1)
            self.worker_a.result_signal.connect(self.handle_result_a)
            self.worker_b = TempWorker(self.aiBUSParam, 2)
            self.worker_b.result_signal.connect(self.handle_result_b)
            self.worker_a.start()
            self.worker_b.start()
            self.program_a, self.program_b = self.read_program_settings()
            self.BT_run_a.setEnabled(True)
            self.BT_hold_a.setEnabled(True)
            self.BT_stop_a.setEnabled(True)
            self.BT_run_b.setEnabled(True)
            self.BT_hold_b.setEnabled(True)
            self.BT_stop_b.setEnabled(True)
            self.timer_temp.start(self.temp_time_interval)
        except Exception as e:
            print(f"An error occurred connect to temperature control device: {e}")
            QMessageBox.critical(self, "Error", f"An error occurred connect to temperature control device: {e}")

    def onSetTempThreshold(self):
        self.temp_threshold = self.SB_temp_threshold.text()
        print(f'set temp threshold: {self.temp_threshold}')

    def onConnectSignalComm(self):
        try:
            self.signal_comm = serial.Serial(port=f"{self.CBB_signal_port.currentText()}", baudrate=9600)
            self.BT_sendSignal.setEnabled(True)
        except Exception as e:
            print(f"An error occurred connect to signal comm: {e}")
            QMessageBox.critical(self, "Error", f"An error occurred connect to signal comm: {e}")

    def read_program_settings(self):
        try:
            pgm_temps_a = []
            pgm_times_a = []
            pgm_temps_b = []
            pgm_times_b = []
            i = 0
            while i < 50:
                temp_a = self.aiBUSParam.ReadParam(iParamNo=i * 2 + 80, iDevAdd=1)
                time_a = self.aiBUSParam.ReadParam(iParamNo=i * 2 + 81, iDevAdd=1)
                if temp_a and time_a:
                    pgm_temps_a.append(int(temp_a))
                    pgm_times_a.append(int(time_a))
                else:
                    break
                i = i + 1

            j = 0
            while j < 50:
                temp_b = self.aiBUSParam.ReadParam(iParamNo=j * 2 + 80, iDevAdd=2)
                time_b = self.aiBUSParam.ReadParam(iParamNo=j * 2 + 81, iDevAdd=2)
                if temp_b and time_b:
                    pgm_temps_b.append(int(temp_b))
                    pgm_times_b.append(int(time_b))
                else:
                    break
                j = j + 1
            if pgm_times_a:
                if 6432 in pgm_times_a:
                    index_a = pgm_times_a.index(6432)
                else:
                    index_a = len(pgm_times_a) - 1
                pgm_times_a = pgm_times_a[:index_a + 1]
                pgm_temps_a = pgm_temps_a[:index_a + 1]
            if pgm_times_b:
                if 6432 in pgm_times_b:
                    index_b = pgm_times_b.index(6432)
                else:
                    index_b = len(pgm_times_b) - 1
                pgm_times_b = pgm_times_b[:index_b + 1]
                pgm_temps_b = pgm_temps_b[:index_b + 1]
            return (pgm_temps_a, pgm_times_a), (pgm_temps_b, pgm_times_b)
        except Exception as e:
            print(e)


    def handle_result_a(self, result):
        self.tempdevData_a = result
        print(f'result updated a')

    def handle_result_b(self, result):
        self.tempdevData_b = result
        print(f'result updated b')

    def onRunA(self):
        self.BT_run_a.setChecked(True)
        self.aiBUSParam.SetParam(iParamNo=27, Value=0, iDevAdd=1)
        print(f'runA')

    def onRunB(self):
        self.flag_of_signal = False
        self.BT_run_b.setChecked(True)
        self.aiBUSParam.SetParam(iParamNo=27, Value=0, iDevAdd=2)
        print(f'runB')

    def onHoldA(self):
        self.BT_hold_a.setChecked(True)
        self.aiBUSParam.SetParam(iParamNo=27, Value=2, iDevAdd=1)
        print(f'holdA')

    def onHoldB(self):
        self.BT_hold_b.setChecked(True)
        self.aiBUSParam.SetParam(iParamNo=27, Value=2, iDevAdd=2)
        print(f'holdB')

    def onStopA(self):
        self.BT_stop_a.setChecked(True)
        self.aiBUSParam.SetParam(iParamNo=27, Value=1, iDevAdd=1)
        print(f'stopA')

    def onStopB(self):
        self.BT_stop_b.setChecked(True)
        self.aiBUSParam.SetParam(iParamNo=27, Value=1, iDevAdd=2)
        print(f'stopB')

    def readTempParameter(self):
        try:
            self.aiBUSParam.ReadParam(iParamNo=74, iDevAdd=1)
            pv = self.aiBUSParam.ParamValue
            self.aiBUSParam.ReadParam(iParamNo=75, iDevAdd=1)
            sv = self.aiBUSParam.ParamValue
            self.aiBUSParam.ReadParam(iParamNo=76, iDevAdd=1)
            mv = self.aiBUSParam.ParamValue
            self.aiBUSParam.ReadParam(iParamNo=46, iDevAdd=1)
            step = self.aiBUSParam.ParamValue
            self.aiBUSParam.ReadParam(iParamNo=47, iDevAdd=1)
            tim = self.aiBUSParam.ParamValue
            self.aiBUSParam.ReadParam(iParamNo=27, iDevAdd=1)
            state = self.aiBUSParam.ParamValue
            if None in [pv, sv, mv, step, tim, state]:
                self.tempdevData_a = None
            else:
                self.tempdevData_a = TempOutputData(pv, sv, mv, step, tim, state)

            self.aiBUSParam.ReadParam(iParamNo=74, iDevAdd=2)
            pv = self.aiBUSParam.ParamValue
            self.aiBUSParam.ReadParam(iParamNo=75, iDevAdd=2)
            sv = self.aiBUSParam.ParamValue
            self.aiBUSParam.ReadParam(iParamNo=76, iDevAdd=2)
            mv = self.aiBUSParam.ParamValue
            self.aiBUSParam.ReadParam(iParamNo=46, iDevAdd=2)
            step = self.aiBUSParam.ParamValue
            self.aiBUSParam.ReadParam(iParamNo=47, iDevAdd=2)
            tim = self.aiBUSParam.ParamValue
            self.aiBUSParam.ReadParam(iParamNo=27, iDevAdd=2)
            state = self.aiBUSParam.ParamValue
            if None in [pv, sv, mv, step, tim, state]:
                self.tempdevData_b = None
            else:
                self.tempdevData_b = TempOutputData(pv, sv, mv, step, tim, state)
        except Exception as e:
            print(e)

    def updateTempData(self):
        # 读取设备参数
        # self.readTempParameter()
        # 将获取到的温度值显示在QLineEdit中
        if self.tempdevData_a:
            self.lbl_pv_a.setText(str(self.tempdevData_a.pv))
            self.lbl_sv_a.setText(str(self.tempdevData_a.sv))
            self.lbl_mv_a.setText(str(self.tempdevData_a.mv))
            self.lbl_step_a.setText(str(self.tempdevData_a.step))
            self.lbl_time_a.setText(str(self.tempdevData_a.tim))
            if self.tempdevData_a.state == 0:
                self.BT_run_a.setChecked(True)
                self.BT_run_a.setStyleSheet(self.selected_color)
                self.BT_hold_a.setStyleSheet(self.default_color)
                self.BT_stop_a.setStyleSheet(self.default_color)
            elif self.tempdevData_a.state == 1:
                self.BT_stop_a.setChecked(True)
                self.BT_stop_a.setStyleSheet(self.selected_color)
                self.BT_hold_a.setStyleSheet(self.default_color)
                self.BT_run_a.setStyleSheet(self.default_color)
            elif self.tempdevData_a.state == 2:
                self.BT_hold_a.setChecked(True)
                self.BT_hold_a.setStyleSheet(self.selected_color)
                self.BT_run_a.setStyleSheet(self.default_color)
                self.BT_stop_a.setStyleSheet(self.default_color)
            else:
                print(f'state_a error')

        if self.tempdevData_b:
            self.lbl_pv_b.setText(str(self.tempdevData_b.pv))
            self.lbl_sv_b.setText(str(self.tempdevData_b.sv))
            self.lbl_mv_b.setText(str(self.tempdevData_b.mv))
            self.lbl_step_b.setText(str(self.tempdevData_b.step))
            self.lbl_time_b.setText(str(self.tempdevData_b.tim))
            if self.tempdevData_b.state == 0:
                self.BT_run_b.setChecked(True)
                self.BT_run_b.setStyleSheet(self.selected_color)
                self.BT_hold_b.setStyleSheet(self.default_color)
                self.BT_stop_b.setStyleSheet(self.default_color)
            elif self.tempdevData_b.state == 1:
                self.BT_stop_b.setChecked(True)
                self.BT_stop_b.setStyleSheet(self.selected_color)
                self.BT_hold_b.setStyleSheet(self.default_color)
                self.BT_run_b.setStyleSheet(self.default_color)
            elif self.tempdevData_b.state == 2:
                self.BT_hold_b.setChecked(True)
                self.BT_hold_b.setStyleSheet(self.selected_color)
                self.BT_run_b.setStyleSheet(self.default_color)
                self.BT_stop_b.setStyleSheet(self.default_color)
            else:
                print(f'state_b error')
        # 绘制进度条
        try:
            if self.tempdevData_a:
                if self.program_a[1]:
                    total_set_time_a = sum(self.program_a[1][:-1])
                    progress_time_a = sum(self.program_a[1][:self.tempdevData_a.step - 1]) + self.tempdevData_a.tim
                    progress_percent_a = int(progress_time_a / total_set_time_a * 100)
                    self.psbar_a.setValue(progress_percent_a)
                    self.max_temperature_a = max(self.program_a[0])*1.4
                    self.total_set_time_a = total_set_time_a
                else:
                    self.max_temperature_a = max(self.tempdevData_a.pv, self.tempdevData_a.sv)*1.4
                    self.psbar_a.setValue(0)
            if self.tempdevData_b:
                if self.program_b[1]:
                    total_set_time_b = sum(self.program_b[1][:-1])
                    progress_time_b = sum(self.program_b[1][:self.tempdevData_b.step - 1]) + self.tempdevData_b.tim
                    progress_percent_b = int(progress_time_b / total_set_time_b * 100)
                    self.psbar_b.setValue(progress_percent_b)
                    self.max_temperature_b = max(self.program_b[0])*1.4
                    self.total_set_time_b = total_set_time_b
                else:
                    self.max_temperature_b = max(self.tempdevData_b.pv, self.tempdevData_b.sv)*1.4
                    self.psbar_b.setValue(0)
        except Exception as e:
            print(e)
        try:
            if self.tempdevData_a:
                # 绘制ZoneA温度曲线
                ctime = time.time()
                if self.total_set_time_a and self.total_set_time_b:
                    self.timerange = max(self.total_set_time_a, self.total_set_time_b) * 60
                x_data_pv_a, y_data_pv_a = self.line_pv_a.get_data()
                if len(x_data_pv_a) > self.timerange * self.dps:
                    x_data_pv_a = []
                    y_data_pv_a = []
                    self.ax_a.set_xlim(ctime, ctime + self.timerange - 1)
                    xticks = [ctime + i * self.timerange / 4 for i in range(5)]
                    xlabels = [datetime.fromtimestamp(ts).strftime('%H:%M:%S') for ts in xticks]
                    self.ax_a.set_xticks(xticks, xlabels)
                x_data_pv_a = np.append(x_data_pv_a, ctime)
                y_data_pv_a = np.append(y_data_pv_a, self.tempdevData_a.pv)

                x_data_sv_a, y_data_sv_a = self.line_sv_a.get_data()
                if len(x_data_sv_a) > self.timerange * self.dps:
                    x_data_sv_a = []
                    y_data_sv_a = []
                x_data_sv_a = np.append(x_data_sv_a, ctime)
                y_data_sv_a = np.append(y_data_sv_a, self.tempdevData_a.sv)
                # 更新图形
                self.line_pv_a.set_data(x_data_pv_a, y_data_pv_a)
                self.line_sv_a.set_data(x_data_sv_a, y_data_sv_a)
                self.ax_a.set_ylim(-5, self.max_temperature_a)
                self.ax_a.relim()  # 重新计算坐标轴的界限
                self.ax_a.autoscale_view(True, True, True)  # 自动缩放
                self.canvas_a.draw()  # 重绘画布
            if self.tempdevData_b:
                # 绘制ZoneB温度曲线
                x_data_pv_b, y_data_pv_b = self.line_pv_b.get_data()
                if len(x_data_pv_b) > self.timerange * self.dps:
                    x_data_pv_b = []
                    y_data_pv_b = []
                    self.ax_b.set_xlim(ctime, ctime + self.timerange - 1)
                    xticks = [ctime + i * self.timerange / 4 for i in range(5)]
                    xlabels = [datetime.fromtimestamp(ts).strftime('%H:%M:%S') for ts in xticks]
                    self.ax_b.set_xticks(xticks, xlabels)
                x_data_pv_b = np.append(x_data_pv_b, ctime)
                y_data_pv_b = np.append(y_data_pv_b, self.tempdevData_b.pv)

                x_data_sv_b, y_data_sv_b = self.line_sv_b.get_data()
                if len(x_data_sv_b) > self.timerange * self.dps:
                    x_data_sv_b = []
                    y_data_sv_b = []
                x_data_sv_b = np.append(x_data_sv_b, ctime)
                y_data_sv_b = np.append(y_data_sv_b, self.tempdevData_b.sv)
                # 更新图形
                self.line_pv_b.set_data(x_data_pv_b, y_data_pv_b)
                self.line_sv_b.set_data(x_data_sv_b, y_data_sv_b)
                self.ax_b.set_ylim(-5, self.max_temperature_b)
                self.ax_b.relim()  # 重新计算坐标轴的界限
                self.ax_b.autoscale_view(True, True, True)  # 自动缩放
                self.canvas_b.draw()  # 重绘画布

            # 判断实验是否结束，发送信号
            if self.tempdevData_b:
                if self.tempdevData_b.step == len(self.program_b[0]) - 1:
                    self.flag_of_signal = True
                print(f'flag: {self.flag_of_signal}')
                if self.temp_threshold:
                    if self.flag_of_signal and self.tempdevData_b.pv < self.temp_threshold:
                        self.onSendSignal()
        except Exception as e:
            print(e)

    def onSendSignal(self):
        print(f'send signal')
        try:
            data_to_send = bytearray(8)
            data_to_send[0] = 129
            data_to_send[1] = 129
            data_to_send[2] = 82
            data_to_send[3] = 74
            data_to_send[4] = 0
            data_to_send[5] = 0
            data_to_send[6] = 83
            data_to_send[7] = 1
            # data = '81 81 52 01 00 00 53 01'
            print(f'发送:{data_to_send} 到 {self.CBB_signal_port.currentText()}')
            write_len = self.signal_comm.write(b'a')
            time.sleep(0.05)
            print(f'发送成功')
            print("串口发出{}个字节。".format(write_len))
        except Exception as e:
            print(e)

    def createFile(self):
        try:
            filename = 'New Program'
            self.dialog = TempProgramTableDialog(self, filename)
            if self.dialog.exec_() == QDialog.Accepted:
                print("Dialog was accepted.")
        except Exception as e:
            print(e)

    def editFile(self, filename):
        print(f"Selected file: {filename}")
        filepath = os.path.join(temp_config_path, f'{filename}.csv')
        try:
            if not os.path.exists(filepath):
                self.dialog = TempProgramTableDialog(self, filename)
            else:
                self.dialog = TempProgramTableDialog(self, filename)
                self.dialog.loadTable(filename)
                print(f"Selected file: {filename}")
            if self.dialog.exec_() == QDialog.Accepted:
                print("Dialog was accepted.")
        except Exception as e:
            print(e)

    def openFile(self):
        # 弹出文件选择对话框
        file_path, _ = QFileDialog.getOpenFileName(self, "Open File", "", "CSV Files (*.csv);;All Files (*)")
        filename, _ = os.path.splitext(os.path.basename(file_path))
        if filename:
            # 这里可以添加代码来处理选中的文件42
            self.dialog = TempProgramTableDialog(self, filename)
            self.dialog.loadTable(filename)
            print(f"Selected file: {filename}")
            if self.dialog.exec_() == QDialog.Accepted:
                print("Dialog was accepted.")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    mw = TempWidget()
    mw.show()
    sys.exit(app.exec_())
