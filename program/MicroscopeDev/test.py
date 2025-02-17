import cv2
import numpy as np
import toupcam
from PyQt5.QtCore import QTimer, QSignalBlocker, Qt, pyqtSignal, QUrl, QCoreApplication, QPoint, QLineF, QSize, QTime
from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen, QFont, QColor
from PyQt5.QtWidgets import (QMainWindow, QMessageBox, QMenu, QAction, QApplication, QDialog, QFileDialog,
                             QTreeWidgetItem, QLabel, QToolBar, QPushButton, QLineEdit, QButtonGroup, QRadioButton,
                             QSizePolicy, QToolTip)

# info = toupcam.ToupcamFrameInfoV3()
# buf = bytes(toupcam.TDIBWIDTHBYTES(info.width * 24) * info.height)
# image = QImage(buf, info.width, info.height, QImage.Format_RGB888)
# print(buf)


def jpg_to_qimage_from_path(file_path):
    if file_path.endswith('.jpg'):
        try:
            image = QImage(file_path)
            return image
        except:
            print(f"无法从 {file_path} 加载图片并转换为QImage对象")
    return None

def ss(file_path):
    img_color = cv2.imread(file_path)
    img_gray_from_color = cv2.cvtColor(img_color, cv2.COLOR_BGR2GRAY)
    laplacian_result = cv2.Laplacian(img_gray_from_color, cv2.CV_16S, ksize=3).var()
    return laplacian_result


if __name__ == "__main__":
    filePath = '../image/None_None_173700_7.jpg'
    image = ss(filePath)
    print(image)
