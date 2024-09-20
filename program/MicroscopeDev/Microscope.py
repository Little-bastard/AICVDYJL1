import sys

from PyQt5.QtCore import pyqtSignal, QTimer, QSignalBlocker, Qt, QCoreApplication
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QMessageBox, QMenu, QAction, QApplication, QMainWindow

from program.MicroscopeDev import toupcam
from program.MicroscopeDev.qt import MainWidget
from program.Mainwindow import Ui_MainWindow


class CameraWorker:
    resultSignal = pyqtSignal(int)

    def __init__(self, cur):
        super().__init__()
        self.cur = cur
        self.hcam = toupcam.Toupcam.Open(self.cur.id)


class MciroscopeWindow(QMainWindow, Ui_MainWindow):
    evtCallback = pyqtSignal(int)
    @staticmethod
    def makeLayout(lbl1, sli1, val1, lbl2, sli2, val2):
        hlyt1 = QHBoxLayout()
        hlyt1.addWidget(lbl1)
        hlyt1.addStretch()
        hlyt1.addWidget(val1)
        hlyt2 = QHBoxLayout()
        hlyt2.addWidget(lbl2)
        hlyt2.addStretch()
        hlyt2.addWidget(val2)
        vlyt = QVBoxLayout()
        vlyt.addLayout(hlyt1)
        vlyt.addWidget(sli1)
        vlyt.addLayout(hlyt2)
        vlyt.addWidget(sli2)
        return vlyt

    def __init__(self, parent=None):
        super(MciroscopeWindow, self).__init__(parent)
        self.hcam = None
        self.timer = QTimer(self)
        self.imgWidth = 0
        self.imgHeight = 0
        self.pData = None
        self.res = 0
        self.temp = toupcam.TOUPCAM_TEMP_DEF
        self.tint = toupcam.TOUPCAM_TINT_DEF
        self.count = 0
        self.setupUi(self)
        self.init_ui()

    def init_ui(self):
        self.setMinimumSize(1024, 768)
        self.cmb_res.currentIndexChanged.connect(self.onResolutionChanged)
        self.cbox_auto.stateChanged.connect(self.onAutoExpo)
        self.slider_expoTime.valueChanged.connect(self.onExpoTime)
        self.slider_expoGain.valueChanged.connect(self.onExpoGain)

        self.btn_autoWB.clicked.connect(self.onAutoWB)
        self.lbl_temp.setText(str(toupcam.TOUPCAM_TEMP_DEF))
        self.lbl_tint.setText(str(toupcam.TOUPCAM_TINT_DEF))
        self.slider_temp.setRange(toupcam.TOUPCAM_TEMP_MIN, toupcam.TOUPCAM_TEMP_MAX)
        self.slider_temp.setValue(toupcam.TOUPCAM_TEMP_DEF)
        self.slider_tint.setRange(toupcam.TOUPCAM_TINT_MIN, toupcam.TOUPCAM_TINT_MAX)
        self.slider_tint.setValue(toupcam.TOUPCAM_TINT_DEF)
        self.slider_temp.valueChanged.connect(self.onWBTemp)
        self.slider_tint.valueChanged.connect(self.onWBTint)

        self.btn_open.clicked.connect(self.onBtnOpen)
        self.btn_snap.clicked.connect(self.onBtnSnap)
        self.btn_save.clicked.connect(self.onBtnSave)

        self.timer.timeout.connect(self.onTimer)
        self.evtCallback.connect(self.onevtCallback)

    def onTimer(self):
        if self.hcam:
            nFrame, nTime, nTotalFrame = self.hcam.get_FrameRate()  # 1r
            self.lbl_frame.setText("{}, fps = {:.1f}".format(nTotalFrame, nFrame * 1000.0 / nTime))

    def closeCamera(self):
        if self.hcam:
            self.hcam.Close()
        self.hcam = None
        self.pData = None

        self.btn_open.setText("Open")
        self.timer.stop()
        self.lbl_frame.clear()
        self.cbox_auto.setEnabled(False)
        self.slider_expoGain.setEnabled(False)
        self.slider_expoTime.setEnabled(False)
        self.btn_autoWB.setEnabled(False)
        self.slider_temp.setEnabled(False)
        self.slider_tint.setEnabled(False)
        self.btn_snap.setEnabled(False)
        self.cmb_res.setEnabled(False)
        self.cmb_res.clear()

    def closeEvent(self, event):
        self.closeCamera()

    def onResolutionChanged(self, index):
        if self.hcam: #step 1: stop camera
            self.hcam.Stop()

        self.res = index
        self.imgWidth = self.cur.model.res[index].width
        self.imgHeight = self.cur.model.res[index].height

        if self.hcam: #step 2: restart camera
            self.hcam.put_eSize(self.res)  # 2w
            self.startCamera()

    def onAutoExpo(self, state):
        if self.hcam:
            self.hcam.put_AutoExpoEnable(1 if state else 0)  # 3w
            self.slider_expoTime.setEnabled(not state)
            self.slider_expoGain.setEnabled(not state)

    def onExpoTime(self, value):
        self.lbl_expoTime.setText(str(value))
        if not self.cbox_auto.isChecked():
            self.hcam.put_ExpoTime(value)  # 4w

    def onExpoGain(self, value):
        self.lbl_expoGain.setText(str(value))
        if not self.cbox_auto.isChecked():
            self.hcam.put_ExpoAGain(value)  # 5w

    def onAutoWB(self):
        if self.hcam:
            self.hcam.AwbOnce()  # 6w

    def wbCallback(nTemp, nTint, self):
        self.slider_temp.setValue(nTemp)
        self.slider_tint.setValue(nTint)

    def onWBTemp(self, value):
        if self.hcam:
            self.temp = value
            self.hcam.put_TempTint(self.temp, self.tint)  # 7w
            self.lbl_temp.setText(str(value))

    def onWBTint(self, value):
        if self.hcam:
            self.tint = value
            self.hcam.put_TempTint(self.temp, self.tint)  # 8w
            self.lbl_tint.setText(str(value))

    def startCamera(self):
        self.pData = bytes(toupcam.TDIBWIDTHBYTES(self.imgWidth * 24) * self.imgHeight)
        uimin, uimax, uidef = self.hcam.get_ExpTimeRange()  # 9r
        self.slider_expoTime.setRange(uimin, uimax)
        self.slider_expoTime.setValue(uidef)
        usmin, usmax, usdef = self.hcam.get_ExpoAGainRange()  # 10r
        self.slider_expoGain.setRange(usmin, usmax)
        self.slider_expoGain.setValue(usdef)
        self.handleExpoEvent()
        if self.cur.model.flag & toupcam.TOUPCAM_FLAG_MONO == 0:
            self.handleTempTintEvent()
        try:
            self.hcam.StartPullModeWithCallback(self.eventCallBack, self)
        except toupcam.HRESULTException:
            self.closeCamera()
            QMessageBox.warning(self, "Warning", "Failed to start camera.")
        else:
            self.cmb_res.setEnabled(True)
            self.cbox_auto.setEnabled(True)
            self.btn_autoWB.setEnabled(self.cur.model.flag & toupcam.TOUPCAM_FLAG_MONO == 0)
            self.slider_temp.setEnabled(self.cur.model.flag & toupcam.TOUPCAM_FLAG_MONO == 0)
            self.slider_tint.setEnabled(self.cur.model.flag & toupcam.TOUPCAM_FLAG_MONO == 0)
            self.btn_open.setText("Close")
            self.btn_snap.setEnabled(True)
            bAuto = self.hcam.get_AutoExpoEnable()
            self.cbox_auto.setChecked(1 == bAuto)
            self.timer.start(1000)

    def openCamera(self):
        self.hcam = toupcam.Toupcam.Open(self.cur.id)
        if self.hcam:
            self.res = self.hcam.get_eSize()
            self.imgWidth = self.cur.model.res[self.res].width
            self.imgHeight = self.cur.model.res[self.res].height
            with QSignalBlocker(self.cmb_res):
                self.cmb_res.clear()
                for i in range(0, self.cur.model.preview):
                    self.cmb_res.addItem("{}*{}".format(self.cur.model.res[i].width, self.cur.model.res[i].height))
                self.cmb_res.setCurrentIndex(self.res)
                self.cmb_res.setEnabled(True)
            self.hcam.put_Option(toupcam.TOUPCAM_OPTION_BYTEORDER, 0)  # Qimage use RGB byte order
            self.hcam.put_AutoExpoEnable(1)
            self.startCamera()

    def onBtnOpen(self):
        if self.hcam:
            self.closeCamera()
        else:
            arr = toupcam.Toupcam.EnumV2()
            if 0 == len(arr):
                QMessageBox.warning(self, "Warning", "No camera found.")
            elif 1 == len(arr):
                self.cur = arr[0]
                self.openCamera()
            else:
                menu = QMenu()
                for i in range(0, len(arr)):
                    action = QAction(arr[i].displayname, self)
                    action.setData(i)
                    menu.addAction(action)
                action = menu.exec(self.mapToGlobal(self.btn_open.pos()))
                if action:
                    self.cur = arr[action.data()]
                    self.openCamera()

    def onBtnSnap(self):
        if self.hcam:
            if 0 == self.cur.model.still:  # not support still image capture
                if self.pData is not None:
                    image = QImage(self.pData, self.imgWidth, self.imgHeight, QImage.Format_RGB888)
                    self.count += 1
                    image.save("pyqt{}.jpg".format(self.count))
            else:
                menu = QMenu()
                for i in range(0, self.cur.model.still):
                    action = QAction("{}*{}".format(self.cur.model.res[i].width, self.cur.model.res[i].height), self)
                    action.setData(i)
                    menu.addAction(action)
                action = menu.exec(self.mapToGlobal(self.btn_snap.pos()))
                self.hcam.Snap(action.data())

    def onBtnSave(self):
        pass

    @staticmethod
    def eventCallBack(nEvent, self):
        '''callbacks come from toupcam.dll/so internal threads, so we use qt signal to post this event to the UI thread'''
        self.evtCallback.emit(nEvent)

    def onevtCallback(self, nEvent):
        '''this run in the UI thread'''
        if self.hcam:
            if toupcam.TOUPCAM_EVENT_IMAGE == nEvent:
                self.handleImageEvent()
            elif toupcam.TOUPCAM_EVENT_EXPOSURE == nEvent:
                self.handleExpoEvent()
            elif toupcam.TOUPCAM_EVENT_TEMPTINT == nEvent:
                self.handleTempTintEvent()
            elif toupcam.TOUPCAM_EVENT_STILLIMAGE == nEvent:
                self.handleStillImageEvent()
            elif toupcam.TOUPCAM_EVENT_ERROR == nEvent:
                self.closeCamera()
                QMessageBox.warning(self, "Warning", "Generic Error.")
            elif toupcam.TOUPCAM_EVENT_STILLIMAGE == nEvent:
                self.closeCamera()
                QMessageBox.warning(self, "Warning", "Camera disconnect.")

    def handleImageEvent(self):
        try:
            self.hcam.PullImageV3(self.pData, 0, 24, 0, None)
        except toupcam.HRESULTException:
            pass
        else:
            image = QImage(self.pData, self.imgWidth, self.imgHeight, QImage.Format_RGB888)
            newimage = image.scaled(self.lbl_video.width(), self.lbl_video.height(), Qt.KeepAspectRatio, Qt.FastTransformation)
            self.lbl_video.setPixmap(QPixmap.fromImage(newimage))

    def handleExpoEvent(self):
        time = self.hcam.get_ExpoTime()
        gain = self.hcam.get_ExpoAGain()
        with QSignalBlocker(self.slider_expoTime):
            self.slider_expoTime.setValue(time)
        with QSignalBlocker(self.slider_expoGain):
            self.slider_expoGain.setValue(gain)
        self.lbl_expoTime.setText(str(time))
        self.lbl_expoGain.setText(str(gain))

    def handleTempTintEvent(self):
        nTemp, nTint = self.hcam.get_TempTint()
        with QSignalBlocker(self.slider_temp):
            self.slider_temp.setValue(nTemp)
        with QSignalBlocker(self.slider_tint):
            self.slider_tint.setValue(nTint)
        self.lbl_temp.setText(str(nTemp))
        self.lbl_tint.setText(str(nTint))

    def handleStillImageEvent(self):
        info = toupcam.ToupcamFrameInfoV3()
        try:
            self.hcam.PullImageV3(None, 1, 24, 0, info) # peek
        except toupcam.HRESULTException:
            pass
        else:
            if info.width > 0 and info.height > 0:
                buf = bytes(toupcam.TDIBWIDTHBYTES(info.width * 24) * info.height)
                try:
                    self.hcam.PullImageV3(buf, 1, 24, 0, info)
                except toupcam.HRESULTException:
                    pass
                else:
                    image = QImage(buf, info.width, info.height, QImage.Format_RGB888)
                    self.count += 1
                    image.save("pyqt{}.jpg".format(self.count))


if __name__ == '__main__':
    QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    toupcam.Toupcam.GigeEnable(None, None)
    app = QApplication(sys.argv)
    mw = MciroscopeWindow()
    mw.show()
    sys.exit(app.exec_())
