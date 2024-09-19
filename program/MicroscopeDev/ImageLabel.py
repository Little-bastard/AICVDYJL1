import sys
from PyQt5.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout, QToolTip
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QPen, QMouseEvent, QFontMetrics, QCursor


class DrawableLabel(QLabel):
    def __init__(self, parent=None):
        super(DrawableLabel, self).__init__(parent)
        self.coefficient = 1.0
        self.setMouseTracking(True)
        self.start_point = None
        self.end_point = None
        self.is_drawing = False

    def setCoefficient(self, coefficient):
        self.coefficient = coefficient
        self.update()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            if self.start_point is None:
                self.start_point = event.pos()
            else:
                self.end_point = event.pos()
        elif event.button() == Qt.RightButton:
            self.cancel_drawing()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            if self.start_point and self.end_point:
                self.start_point = None
                self.end_point = None
                # self.update()

    def cancel_drawing(self):
        self.start_point = None
        self.end_point = None
        self.is_drawing = False
        self.update()  # 重绘以清除临时线

    def mouseMoveEvent(self, event: QMouseEvent):
        # 获取鼠标在标签内的相对坐标
        # x = event.pos().x()
        # y = event.pos().y()
        # # 使用QToolTip在鼠标下方显示坐标
        # QToolTip.showText(event.globalPos(), f"X: {x}, Y: {y}", self)
        # event.accept()
        if self.start_point:
            self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setPen(QPen(Qt.black, 2, Qt.SolidLine, Qt.RoundCap))
        if self.start_point:
            current_pos = self.mapFromGlobal(QCursor.pos())
            painter.setPen(QPen(Qt.gray))
            painter.drawLine(self.start_point, current_pos)
            length = self.calculate_distance(self.start_point, current_pos) * self.coefficient
            if length != 0:
                self.draw_length(painter, int(length), (self.start_point + current_pos) / 2)

    def calculate_distance(self, p1, p2):
        return ((p2.x() - p1.x()) ** 2 + (p2.y() - p1.y()) ** 2) ** 0.5

    def draw_length(self, painter, length, position):
        font = painter.font()
        font.setPointSize(12)
        painter.setPen(QPen(Qt.gray))
        painter.setFont(font)
        fm = QFontMetrics(font)
        text = f"{length:.2f}"
        text_width = fm.horizontalAdvance(text)
        text_height = fm.height()
        painter.drawText(int(position.x() - text_width / 2), int(position.y() - text_height / 2), text)

class Example(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setGeometry(300, 300, 400, 300)
        self.setWindowTitle('Draw Line and Show Length')

        # 创建DrawableLabel并添加到布局中
        self.drawable_label = DrawableLabel(self)
        layout = QVBoxLayout()
        layout.addWidget(self.drawable_label)
        self.setLayout(layout)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = Example()
    ex.show()
    sys.exit(app.exec_())
