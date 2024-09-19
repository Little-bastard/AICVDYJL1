import sys
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QRadioButton

class Example(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.button1 = QPushButton("按钮1")
        self.button2 = QPushButton("按钮2")

        self.radio1 = QRadioButton("选择按钮1")
        self.radio2 = QRadioButton("选择按钮2")

        layout = QVBoxLayout()
        layout.addWidget(self.radio1)
        layout.addWidget(self.radio2)
        layout.addWidget(self.button1)
        layout.addWidget(self.button2)

        self.setLayout(layout)

        self.radio1.toggled.connect(lambda: self.applyStyle(self.button1, self.button2))
        self.radio2.toggled.connect(lambda: self.applyStyle(self.button2, self.button1))

    def applyStyle(self, active_button, inactive_button):
        active_button.setStyleSheet("background-color: red; color: white;")
        inactive_button.setStyleSheet("background-color: white; color: black;")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = Example()
    ex.show()
    sys.exit(app.exec_())