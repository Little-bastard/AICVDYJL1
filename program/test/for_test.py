import sys
import csv
from PyQt5.QtWidgets import QApplication, QDialog, QTableWidget, QTableWidgetItem, QVBoxLayout
from PyQt5.QtGui import QColor, QBrush
from PyQt5.QtCore import Qt

class TaskManagerDialog(QDialog):
    def __init__(self, csv_file_path, parent=None):
        super(TaskManagerDialog, self).__init__(parent)
        self.csv_file_path = csv_file_path
        self.initUI()

    def initUI(self):
        self.setWindowTitle('任务管理表格')
        self.tableWidget = QTableWidget()
        self.tableWidget.setRowCount(0)
        self.tableWidget.setColumnCount(3)
        self.tableWidget.setHorizontalHeaderLabels(['任务ID', '任务描述', '进度', '完成状态'])
        self.loadData()
        layout = QVBoxLayout()
        layout.addWidget(self.tableWidget)
        self.setLayout(layout)
        self.resize(600, 400)

    def loadData(self):
        try:
            with open(self.csv_file_path, 'r') as csvfile:
                reader = csv.reader(csvfile)
                for row_index, row in enumerate(reader):
                    if row_index == 0:
                        continue  # 跳过标题行
                    self.tableWidget.insertRow(row_index)
                    for column_index, data in enumerate(row):
                        item = QTableWidgetItem(data)
                        self.tableWidget.setItem(row_index-1, column_index, item)
                    self.setRowColor(row_index, self.getColorByStatus(row[2]))
        except FileNotFoundError:
            print(f"文件 {self.csv_file_path} 未找到。")
        except Exception as e:
            print(f"读取文件时发生错误：{e}")

    def getColorByStatus(self, status):
        if status == "进行中":
            return QColor("yellow")
        elif status == "未开始":
            return QColor("gray")
        elif status == "已完成":
            return QColor("green")
        else:
            return QColor("white")  # 默认颜色为白色

    def setRowColor(self, row, color):
        # 设置整行的颜色
        for column in range(self.tableWidget.columnCount()):
            item = self.tableWidget.item(row, column) if self.tableWidget.item(row, column) else QTableWidgetItem()
            item.setBackground(QBrush(color))
            self.tableWidget.setItem(row-1, column, item)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    csv_file_path = '../TaskManagement/实验任务进度管理表.csv'  # 替换为你的CSV文件路径
    dialog = TaskManagerDialog(csv_file_path)
    dialog.show()
    sys.exit(app.exec_())