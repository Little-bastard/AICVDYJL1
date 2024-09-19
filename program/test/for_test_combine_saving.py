import sys
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QPushButton
from PyQt5.QtGui import QPixmap, QPainter, QPolygon, QPen
from PyQt5.QtCore import QTimer, Qt, QPoint


class Canvas(QWidget):
    def __init__(self, parent=None):
        super(Canvas, self).__init__(parent)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(QPen(Qt.black, 2))  # 设置画笔颜色为黑色，宽度为2

        # 定义曲线的点
        points = QPolygon([
            self.rect().topLeft(),
            self.rect().topRight(),
            self.rect().bottomLeft() + QPoint(50, -50),
            self.rect().bottomRight()
        ])

        # 绘制曲线
        painter.drawPolyline(points)

class MainWindow(QWidget):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.initUI()

    def initUI(self):
        # 加载图像到 QLabel
        self.label = QLabel(self)
        pixmap = QPixmap('../icon/保存.png')  # 替换为你的图片路径
        self.label.setPixmap(pixmap)

        self.canvas = Canvas(self)  # 创建 Canvas 用于绘图

        layout = QVBoxLayout(self)
        layout.addWidget(self.canvas)
        layout.addWidget(self.label)

        self.saveButton = QPushButton('Save to Image', self)
        self.saveButton.clicked.connect(self.saveToImage)
        layout.addWidget(self.saveButton)

        self.setGeometry(300, 300, 800, 400)  # 设置主窗口的位置和大小
        self.setWindowTitle('Save Canvas and QLabel to Image')

    def saveToImage(self):
        # 捕获 Canvas 和 QLabel 的图像
        canvasPixmap = self.canvas.grab()
        labelPixmap = self.label.grab()

        # 根据需要调整尺寸，这里假设两者宽度相同，高度相加
        totalWidth = labelPixmap.width()
        totalHeight = canvasPixmap.height() + labelPixmap.height()

        # 创建一个新的 QPixmap，用于合并图像
        fullPixmap = QPixmap(totalWidth, totalHeight)

        # 使用 QPainter 将两部分合并
        painter = QPainter(fullPixmap)
        painter.drawPixmap(0, 0, canvasPixmap)  # 绘制 Canvas 图像
        painter.drawPixmap(0, canvasPixmap.height(), labelPixmap)  # 绘制 QLabel 图像

        # 保存到文件
        fullPixmap.save('combined_image.png')

if __name__ == '__main__':
    app = QApplication(sys.argv)
    mainWindow = MainWindow()
    mainWindow.show()
    sys.exit(app.exec_())