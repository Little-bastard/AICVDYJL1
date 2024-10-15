import csv
import os
import sys

import openpyxl
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QBrush
from PyQt5.QtWidgets import QDialog, QHeaderView, QTableWidgetItem, QVBoxLayout, QTableWidget, QMessageBox, \
    QAbstractItemView

BASE_DIR = os.path.dirname(os.path.realpath(sys.argv[0]))
task_management_path = os.path.join(BASE_DIR, 'TaskManagement')


class TaskManagerTableDialog(QDialog):
    def __init__(self):
        super(TaskManagerTableDialog, self).__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle("实验任务进度管理")
        self.resize(800, 400)
        layout = QVBoxLayout()

        self.tableWidget = QTableWidget(1, 7)
        layout.addWidget(self.tableWidget)
        self.setLayout(layout)
        self.loadTable()

    def loadTable(self):
        filepath = os.path.join(task_management_path, f'实验任务进度管理表.csv')
        try:
            with open(filepath, mode='r', newline='') as file:
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
                        item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
                        if column_idx == 0:  # 第一列设置为不可编辑
                            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                        self.tableWidget.setItem(row_idx - 1, column_idx, item)
                    # 根据完成状态设置整行颜色
                    status = row_data[self.getColumnInfoByName('完成状态')]
                    if status == "进行中":
                        self.setRowColor(row_idx-1, QColor("darkgoldenrod"))
                    elif status == "未开始":
                        self.setRowColor(row_idx-1, QColor("gray"))
                    elif status == "已完成":
                        self.setRowColor(row_idx-1, QColor("darkgreen"))
        except Exception as e:
            print(f"An error occurred while reading the file: {e}")
            QMessageBox.critical(self, "Error", f"An error occurred while reading the file: {e}")
        # 隐藏行号
        self.tableWidget.verticalHeader().setVisible(False)
        # 调整列宽以适应内容
        self.tableWidget.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        # 设置表格的行可以被选中，但不能编辑
        self.tableWidget.setEditTriggers(QAbstractItemView.NoEditTriggers)

    def getColumnInfoByName(self, header_name):
        # 获取列索引
        for index in range(self.tableWidget.columnCount()):
            if self.tableWidget.horizontalHeaderItem(index).text() == header_name:
                return index
        return -1

    def setRowColor(self, row, color):
        # 设置整行的颜色
        for column in range(self.tableWidget.columnCount()):
            item = self.tableWidget.item(row, column) or QTableWidgetItem()
            item.setForeground(color)
            self.tableWidget.setItem(row, column, item)

