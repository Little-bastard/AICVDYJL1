import copy
import csv
import json
import os
import sys
import time
import traceback
from datetime import datetime, time as dt_time
from pathlib import Path
from typing import Union

import cv2
import modbus_tk.defines as cst
import numpy as np
import pandas as pd
import qdarktheme
import serial
from PyQt5.QtCore import QTimer, QSignalBlocker, Qt, pyqtSignal, QUrl, QCoreApplication, QPoint, QLineF, QSize, QTime, \
    QObject
from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen, QFont, QColor
from PyQt5.QtWidgets import (QMainWindow, QMessageBox, QMenu, QAction, QApplication, QDialog, QFileDialog,
                             QTreeWidgetItem, QLabel, QToolBar, QPushButton, QLineEdit, QButtonGroup, QRadioButton,
                             QSizePolicy, QToolTip)
from matplotlib import pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.ticker import MultipleLocator, FormatStrFormatter
from modbus_tk import modbus_rtu
from openpyxl.styles import Font, Alignment, PatternFill
from serial.tools import list_ports

from program.Flask import FlaskThread
from program.MassFlowController.MFCWindow import MFCWorker, MFCInputData, MFCProgramTableDialog
from program.MicroscopeDev import toupcam
from program.MicroscopeDev.FocusWorker import FocusWorker
from program.MicroscopeDev.ImageLabel import DrawableLabel
from program.TaskManagement.TaskManager import TaskManagerTableDialog
from program.TempCtrlDev.TempWindow import TempProgramTableDialog, TempWorker, TempInputData
from program.Ui_MainWindow import Ui_MainWindow
from program.autoFocus import search_once
from program.robotControl.RobotWindow import WebEngineView

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
config_directory_path = os.path.join(BASE_DIR, 'config')
video_directory_path = os.path.join(BASE_DIR, 'video')
image_directory_path = os.path.join(BASE_DIR, 'image')
result_directory_path = os.path.join(BASE_DIR, 'result')
temp_config_path = os.path.join(BASE_DIR, 'config', "temp_config")
task_management_path = os.path.join(BASE_DIR, 'TaskManagement')


class AICVD(QMainWindow, Ui_MainWindow):
    evtCallback = pyqtSignal(int)

    # 添加信号
    snap_signal = pyqtSignal()  # 手动拍照信号
    snap_auto_signal = pyqtSignal()  # 自动对焦拍照信号
    focus_up_signal = pyqtSignal()
    focus_down_signal = pyqtSignal()

    def __init__(self, parent=None):
        super(AICVD, self).__init__(parent)
        self.cacheTempData = np.empty((0, 5))
        self.cacheMFCData = np.empty((0, 3))
        self.combinedData = None
        self.qimage = None
        self.num = 0
        self.buf =None
        self.total = 0
        self.laplacian_var = 20
        self.recordFlag = False
        self.focus_velocity = None
        self.focusData = None
        self.focus_worker = None
        self.signal_mode = 0
        self.start_sending = None
        self.exp_id = None
        self.out_image_path = None
        self.timer_temperature_window = None
        self.IsLaunched = None
        self.IsThresholdSet = None
        self.total_order = None
        self.IsResultSaved = None
        self.IsExpEnd = None
        self.exp_start_time = None
        self.result_filepath = None
        self.mfc_launch_time = None
        self.temperature_program_name_a = None
        self.temperature_program_name_b = None
        self.temperature_program_a = None
        self.params = None
        self.order = None
        self.cfg_file = None
        self.line_len = 0
        self.default_clean_time = 0 # 默认清洗3分钟
        self.counter = self.default_clean_time
        self.startCounting = False
        self.restartFlag = False
        self.showSettings = False
        self.setupUi(self)
        self.init_microscope_ui()
        self.init_focus_ui()
        self.init_tempctrl_ui()
        self.init_robot_ui()
        self.init_mfc_ui()
        self.BT_settings.clicked.connect(self.onSettings)
        self.widget_settings.hide()
        self.widget_mag.hide()
        self.BT_select_cfg.clicked.connect(self.onSelectConfigFile)
        self.BT_apply_cfg.clicked.connect(self.onApplyConfiguration)
        self.BT_launch_experiment.clicked.connect(self.onLaunchExperiment)
        self.lbl_cfg.enterEvent = self.showCfgTooltip
        self.lbl_cfg.leaveEvent = self.hideCfgTooltip

        self.BT_task_manage.clicked.connect(self.onManageTasks)

        self.api_thread = FlaskThread()
        self.api_thread.start_experiment_signal.connect(self.start_experiment)
        self.api_thread.stop_experiment_signal.connect(self.stop_experiment)
        self.api_thread.set_parameters_signal.connect(self.set_parameters_table)
        self.api_thread.start()

        self.setWindowTitle('AICVD')
        self.selected_color = ("background-color: rgba(85, 170, 255, 50); "
                               "border: 1px solid rgba(0, 85, 255, 220); "
                               "padding: 4px;"
                               "border-radius: 4px")
        self.default_color = ""

        self.timer_main = QTimer(self)
        self.timer_main.timeout.connect(self.main_loop)
        self.timer_main.start(1000)

        # 自动对焦相关
        self.autoFocusFlag = False
        self.original_auto_focus_flag = None
        self.auto_focus_thread = None
        self.target_dir = None

        # 启动实验自动快照定时器相关默认值
        self.auto_focus_dir = None
        self.auto_focus_counter = 0
        self.auto_focus_max = 7
        self.auto_focus_timer = None

        # 初始化自动对焦工作器
        self.auto_focus_worker = AutoFocusWorker(self)

        # 连接信号
        self.snap_signal.connect(self.onBtnSnap)  # 手动拍照
        self.snap_auto_signal.connect(self.onBtnSnapAuto)  # 自动对焦拍照
        self.focus_up_signal.connect(self.onFocusUp)
        self.focus_down_signal.connect(self.onFocusDown)

        # 连接自动对焦信号
        self.auto_focus_worker.progress.connect(self.on_auto_focus_progress)
        self.auto_focus_worker.sharpness_calculated.connect(self.on_sharpness_calculated)
        self.auto_focus_worker.finished.connect(self.on_auto_focus_finished)

    def onConnectFocus(self):
        if self.focus_worker:
            self.closeFocus()
        else:
            self.startFocus()

    def startFocus(self):
        try:
            print(f'CBB_focus_port:{self.CBB_focus_port.currentText()}')
            self.focus_worker = FocusWorker(portName=self.CBB_focus_port.currentText())
        except Exception as e:
            print(f"An error occurred connect to focus comm: {e}")
            QMessageBox.critical(self, "Error", f"An error occurred connect to focus comm: {e}")
        if self.focus_worker:
            self.timer_focus_window.start(1000)
            self.focus_worker.focus_signal.connect(self.handle_result_focus)
            self.focus_worker.start()
            self.BT_focus_connect.setText("断开")

    def closeFocus(self):
        self.timer_focus_window.stop()
        self.lbl_focus_position.setText("")
        if self.focus_worker:
            self.focus_worker.stop_run()
        self.focus_worker = None
        self.BT_focus_connect.setText("连接")


    def handle_result_focus(self, result):
        self.focusData = result

    def onFocusUp(self):
        if self.focus_velocity is not None:
            self.focus_worker.move_up(self.focus_velocity)

    def onFocusDown(self):
        if self.focus_velocity is not None:
            self.focus_worker.move_down(-self.focus_velocity)

    def onSetUpLimit(self):
        self.focus_worker.set_high_limit()

    def onSetDownLimit(self):
        self.focus_worker.set_low_limit()

    def onSetZero(self):
        self.focus_worker.set_zero_position()

    def onSetSpeed(self):
        index = self.CBB_focus_speed.currentIndex()
        print('*'*100, index)
        if index == 0:
            self.focus_velocity = 1
        if index == 1:
            self.focus_velocity = 2
        if index == 2:
            self.focus_velocity = 20
        if index == 3:
            self.focus_velocity = 200
        if index == 4:
            self.focus_velocity = 2000
        if index == 5:
            self.focus_velocity = 20000
        if index == 6:
            self.focus_velocity = 200000

    def onFocusEMS(self):
        self.focus_worker.stop_abruptly()

    def showCfgTooltip(self, event):
        # 显示工具提示
        QToolTip.showText(event.globalPos(), self.lbl_cfg.toolTip(), self.lbl_cfg)

    def hideCfgTooltip(self, event):
        # 隐藏工具提示
        QToolTip.hideText()

    def onSelectConfigFile(self, exp_id=None):
        if exp_id:
            file_path = os.path.join(config_directory_path, 'exp_config', f'{exp_id}.xlsx')
        else:
            file_path, _ = QFileDialog.getOpenFileName(self, "Open File", f'{config_directory_path}/exp_config',
                                                       "XLSX Files (*.xlsx);;All Files (*)")
        filename, file_extension = os.path.splitext(os.path.basename(file_path))
        if filename:
            self.lbl_cfg.setText(f'{filename}{file_extension}')
            self.lbl_cfg.setToolTip(file_path)
            self.cfg_file = file_path
            print(f'select config file: {file_path}')
            self.BT_apply_cfg.setChecked(False)
            self.BT_apply_cfg.setStyleSheet(self.default_color)

    def onApplyConfiguration(self):
        if self.cfg_file:
            if self.IsLaunched:
                self.stop_experiment()
            self.lbl_order.clear()
            self.BT_apply_cfg.setChecked(True)
            self.BT_apply_cfg.setStyleSheet(self.selected_color)
            self.order = 1
            current_profile = {
                '实验配置文件': self.cfg_file,
                '轮次': self.order
            }
            with open(f'{config_directory_path}/profile.json', 'w', encoding='utf-8') as profile:
                json.dump(current_profile, profile, ensure_ascii=False, indent=4)
            print(f'保存实验状态到文件：{current_profile}')
            # 创建一个只有表头的空Excel表, 用于保存每轮实验的结果
            df = pd.read_excel(self.cfg_file, sheet_name='Sheet1')
            self.total_order = df['Order'].max()
            columns = df.columns.tolist() + ["Video", "Image", "Date"]
            df_new = pd.DataFrame(columns=columns)
            current_time = datetime.now().strftime("%Y%m%d%H%M%S")
            filename = f'result_{current_time}.xlsx'
            self.result_filepath = os.path.join(result_directory_path, filename)
            df_new.to_excel(self.result_filepath, index=False)
            #初始化任务管理表
            headers = ["experiment_id", "task_id", "progress", "task_status", "start_time", "end_time", "video_result", "image_result", "status_code"]
            filepath = os.path.join(task_management_path, "实验任务进度管理表.csv")
            exp_file = os.path.basename(self.cfg_file)
            self.exp_id, file_extension = os.path.splitext(exp_file)
            try:
                with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(headers)  # 写入表头
                    # 写入数据行
                    for i in range(1, self.total_order + 1):
                        row = [f'{self.exp_id}', f'{i}', "0%", "未开始", "", "", "", ""]
                        writer.writerow(row)
            except Exception as e:
                print(f'An error occurred when init 实验任务进度管理表.csv: {e}')

    def onLaunchExperiment(self):
        if self.IsLaunched:
            self.stop_experiment()
        else:
            self.start_experiment()

    def onManageTasks(self):
        try:
            self.dialog = TaskManagerTableDialog()
            if self.dialog.exec_() == QDialog.Accepted:
                print("Dialog was accepted.")
        except Exception as e:
            print(e)

    def updateTaskTable(self, fieldName, value):
        # 更新任务管理表
        try:
            csv_file_path = os.path.join(task_management_path, '实验任务进度管理表.csv')
            df = pd.read_csv(csv_file_path)
            if fieldName == 'video_result' or fieldName == 'image_result' or "begin_time" or "end_time" or "status":    # 任务状态,开始时间,结束时间,视频结果,图像结果
                df[fieldName] = df[fieldName].astype('object')
            df.loc[df['task_id'] == self.order, fieldName] = value
            df.to_csv(csv_file_path, index=False)
        except Exception as e:
            print(e)


    def start_experiment2(self):
        print("实验启动了！")

    def stop_experiment2(self):
        print("实验停止了！")

    def set_parameters_table(self, exp_id):
        print("设置参数表")
        # 选择参数表
        self.onSelectConfigFile(exp_id)
        # 应用参数表
        self.onApplyConfiguration()

    def stop_experiment(self):
        # 停止录像
        self.stop_recording()
        # 停止并清理自动对焦定时器
        try:
            if hasattr(self, 'auto_focus_timer') and self.auto_focus_timer:
                self.auto_focus_timer.stop()
                self.auto_focus_timer = None
            # 重置计数器与目录
            self.auto_focus_counter = 0
            self.auto_focus_dir = None
        except Exception as e:
            print(f'停止自动对焦定时器失败: {e}')
        # 停止温控
        self.onStopA()
        self.onStopB()
        # 停止流量计
        for idev in range(self.mfc_dev_num):
            if self.mfc_worker:
                self.mfc_worker.write_data('switch',
                                           MFCInputData(value=True, id=idev, addr=0))
        self.IsLaunched = False
        self.BT_launch_experiment.setText("启动实验")
        print(f'停止实验')
        # 更新任务进度管理表
        self.updateTaskTable("task_status", "停止中")

    def start_experiment(self):
        try:
            # 获取实验跟踪信息：配置文件名和当前轮次
            with open(f'{config_directory_path}/profile.json', 'r', encoding='utf-8') as profile:
                current_profile = json.load(profile)
                self.cfg_file = current_profile['实验配置文件']
                self.order = current_profile['轮次']
            # 获取当前轮次对应的参数配置
            if self.cfg_file:
                # 读取每一个参数
                df = pd.read_excel(self.cfg_file, sheet_name='Sheet1')
                # 获取总轮次
                self.total_order = df['Order'].max()
                self.params = df[df['Order'] == self.order].reset_index(drop=True)
                print(f'当前轮次（轮次{self.order}）配置参数: {self.params}')
                self.temperature_program_name_a = self.params['A'].iloc[0]
                self.temperature_program_name_b = self.params['B'].iloc[0]
                self.mass_a = self.params['mass_A'].iloc[0]
                self.mass_b = self.params['mass_B'].iloc[0]
                self.substrate = self.params['Substrate']
                columns = self.params.columns[self.params.columns.get_loc('A_step1_temperature'):self.params.columns.get_loc('A_end_time') + 1]
                self.temperature_program_a = self.params.loc[0, columns].tolist()
                print(f'temperature_program_a: {self.temperature_program_a}')
                columns = self.params.columns[self.params.columns.get_loc('B_step1_temperature'):self.params.columns.get_loc('B_end_time') + 1]
                self.temperature_program_b = self.params.loc[0, columns].tolist()
                print(f'temperature_program_b: {self.temperature_program_b}')
                columns = self.params.columns[
                          self.params.columns.get_loc('Ar_step1_time'):self.params.columns.get_loc('Ar_end_flow') + 1]
                self.mfc_program_Ar = self.params.loc[0, columns].tolist()
                print(f'mfc_program_Ar: {self.mfc_program_Ar}')
                columns = self.params.columns[
                          self.params.columns.get_loc('H2_step1_time'):self.params.columns.get_loc('H2_end_flow') + 1]
                self.mfc_program_H2 = self.params.loc[0, columns].tolist()
                print(f'mfc_program_H2: {self.mfc_program_H2}')
                # 氧气
                columns = self.params.columns[
                          self.params.columns.get_loc('O2_step1_time'):self.params.columns.get_loc('O2_end_flow') + 1]
                self.mfc_program_O2 = self.params.loc[0, columns].tolist()
                print(f'mfc_program_O2: {self.mfc_program_O2}')
                # 二氧化碳
                columns = self.params.columns[
                          self.params.columns.get_loc('CO2_step1_time'):self.params.columns.get_loc('CO2_end_flow') + 1]
                self.mfc_program_CO2 = self.params.loc[0, columns].tolist()
                print(f'mfc_program_CO2: {self.mfc_program_CO2}')
                # 将参数写入对应设备
                # 将温度程序参数写入温控设备
                if self.temp_worker:
                    for i in range(len(self.temperature_program_a)):
                        iparam = 80 + i
                        self.temp_worker.write_data(
                            TempInputData(iParamNo=iparam, Value=self.temperature_program_a[i], iDevAdd=1))
                    self.lbl_buffer_a.setText(f'{self.temperature_program_name_a}')
                    for i in range(len(self.temperature_program_b)):
                        iparam = 80 + i
                        self.temp_worker.write_data(
                            TempInputData(iParamNo=iparam, Value=self.temperature_program_b[i], iDevAdd=2))
                    self.lbl_buffer_b.setText(f'{self.temperature_program_name_b}')
                    self.program_a = (self.temperature_program_a[0::2], self.temperature_program_a[1::2])
                    self.program_b = (self.temperature_program_b[0::2], self.temperature_program_b[1::2])
                    self.temp_worker.read_program_settings()
                # 将流量写入MFC
                # 先将各纯气体流量值转化为各设备通道输入值
                self.air_transform(Ar=self.mfc_program_Ar, H2=self.mfc_program_H2, O2=self.mfc_program_O2, CO2=self.mfc_program_CO2)
                # 设置实验开始标志位
                self.IsExpEnd = False
                self.is_final_step_b = False
                self.IsLaunched = True
                self.BT_launch_experiment.setText("停止实验")
                self.lbl_order.setText(f'{self.order}/{self.total_order}')
                # 停止发送信号
                self.stop_send()
                # 清洗MFC
                self.cleanMFC()
                print(f'启动实验')
                # 确保同级目录存在 autoFocus 文件夹
                auto_focus_dir = os.path.join(BASE_DIR, 'autoFocus')
                if not os.path.isdir(auto_focus_dir):
                    os.makedirs(auto_focus_dir, exist_ok=True)
                # 使用定时器每10秒触发一次：移动显微镜并拍摄快照保存到 autoFocus
                try:
                    # 保存目录与计数器为类属性，便于回调使用
                    self.auto_focus_dir = auto_focus_dir
                    self.auto_focus_counter = 1
                    self.auto_focus_max = 7

                    # 若已有定时器则先停止
                    if hasattr(self, 'auto_focus_timer') and self.auto_focus_timer:
                        self.auto_focus_timer.stop()

                    # 创建并启动定时器
                    self.auto_focus_timer = QTimer(self)
                    self.auto_focus_timer.setInterval(15000)  # 10秒
                    self.auto_focus_timer.timeout.connect(self.on_auto_focus_timer_tick)
                    self.auto_focus_timer.start()
                    print('已启动自动对焦定时器，每10秒触发一次移动与快照。')
                except Exception as e:
                    print(f'启动实验自动对焦定时器失败: {e}')
                self.updateTaskTable("progress", "0%")
                self.updateTaskTable("task_status", "进行中")
                # 测试用
                # self.updateTaskTable("图像结果", r"D:\pythonproject\AICVD\program\image\result.jpg")
                # self.updateTaskTable("视频结果", r"D:\pythonproject\AICVD\program\video\材料视频.mp4")
        except Exception as e:
            self.updateTaskTable("task_status", "实验执行异常")
            print(e)

    def on_auto_focus_timer_tick(self):
        """定时器回调：每次按固定步长移动并保存顺序编号快照"""
        try:
            # 移动显微镜
            if self.focus_worker and self.focus_velocity is not None:
                self.focus_worker.move_up(self.focus_velocity)

            # 保存快照
            if self.hcam and self.pData is not None and hasattr(self, 'auto_focus_dir'):
                image = QImage(self.pData, self.imgWidth, self.imgHeight, QImage.Format_RGB888)
                filename = os.path.join(self.auto_focus_dir, f"{self.auto_focus_counter}.jpg")
                image.save(filename)
                print(f'save snapshot to {filename}')

                # 更新计数并判断是否停止
                self.auto_focus_counter += 1
                if hasattr(self, 'auto_focus_max') and self.auto_focus_counter > self.auto_focus_max:
                    if hasattr(self, 'auto_focus_timer') and self.auto_focus_timer:
                        self.auto_focus_timer.stop()
                    print('自动对焦定时器完成7次快照，已停止。')
                    search_once(3, 10)
        except Exception as e:
            print(f'自动对焦定时器操作失败: {e}')

    def onRunAll(self):
        # 显微镜切换回原来的分辨率
        self.cmb_res.setCurrentIndex(self.res)
        # 开始运行温控程序
        self.onRunA()
        self.onRunB()
        # 再启动计时写入程序
        self.onLaunchMFCProgram()
        # 开始录像
        self.start_recording()
        # 设置标志位
        self.IsResultSaved = False
        # 记录起始时间
        self.exp_start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # 更新任务进度管理表
        self.updateTaskTable("start_time", f'{self.exp_start_time}')

    def to_time(self, time_value: Union[str, datetime, dt_time]) -> dt_time:
        if isinstance(time_value, dt_time):
            # 如果已经是 datetime.time 对象，直接返回
            return time_value
        elif isinstance(time_value, datetime):
            # 如果是 datetime.datetime 对象，提取时间部分
            return time_value.time()
        elif isinstance(time_value, str):
            # 如果是字符串，解析为 datetime.datetime 对象，然后提取时间部分
            return datetime.strptime(time_value, '%H:%M:%S').time()
        else:
            raise ValueError("Unsupported time format")

    def air_transform(self, **kwargs):
        print(f'transform air')
        for key, value in kwargs.items():
            if key == "Ar":
                Ar = value
                print(f"Ar = {Ar}")
            if key == "H2":
                H2 = value
                print(f"H2 = {H2}")
            if key == "O2":
                O2 = value
                print(f"O2 = {O2}")
            if key == "CO2":
                CO2 = value
                print(f"CO2 = {CO2}")
            # TODO 如果有其他其他参与，在这里继续添加其他气体，还要重新写气体混合公式，以建立纯气体与设备通道之间的映射
            # if key == "xx":
            #     xx = value
            #     print(f"xx = {xx}")
        for idev in range(self.mfc_dev_num):
            self.mfc_schedules[idev].clear()
        # 将气体流量转化为设备输入值后，写入每个设备的定时输入计划，以下的公式，即为纯氩气和纯氢气与设备通道0和2之间的映射
        # 氧气 通道4；二氧化碳通道6
        if O2:
            for i in range(int(len(O2) / 2)):
                index = i * 2
                t_o2 = self.to_time(O2[index])
                t = t_o2.hour * 3600 + t_o2.minute * 60 + t_o2.second
                index = i * 2
                o2 = O2[index + 1]
                sv_4 = round(o2, 1)
                self.mfc_schedules[4][t] = sv_4
                print(f'dev 4 schedules: {self.mfc_schedules[4]}')
        if CO2:
            for i in range(int(len(CO2) / 2)):
                index = i * 2
                t_co2 = self.to_time(CO2[index])
                t = t_co2.hour * 3600 + t_co2.minute * 60 + t_co2.second
                index = i * 2
                co2 = CO2[index + 1]
                sv_6 = round(co2, 1)
                self.mfc_schedules[6][t] = sv_6
                print(f'dev 6 schedules: {self.mfc_schedules[6]}')
        if Ar and H2:
            for i in range(int(len(Ar) / 2)):
                index = i * 2
                t_ar = self.to_time(Ar[index])
                print(f'Ar array: {Ar}')
                t_h2 = self.to_time(H2[index])
                ar = Ar[index+1]
                h2 = H2[index+1]
                # 重写判断条件
                if t_ar == t_h2:
                    t = t_ar.hour * 3600 + t_ar.minute * 60 + t_ar.second
                    sv_0 = round(h2 / 0.131, 1)
                    sv_2 = round(ar - 1179 * h2 / 131, 1)
                    self.mfc_schedules[0][t] = sv_0
                    self.mfc_schedules[2][t] = sv_2
                else:
                    print(f"error: Ar's time is not consistent with H2's")
            print(f'dev 0 schedules: {self.mfc_schedules[0]}')
            print(f'dev 2 schedules: {self.mfc_schedules[2]}')
    def onSaveResult(self):
        try:
            # 保存结果
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f'params: {self.params}')
            self.params["Video"] = f'{self.out_video_path}'
            self.params["Image"] = f'{self.out_image_path}'
            self.params["Date"] = f'{self.exp_start_time}, {current_time}'
            old_df = pd.read_excel(self.result_filepath, sheet_name=0)
            # updated_df = pd.concat([old_df, self.params], ignore_index=True)
            # updated_df.to_excel(self.result_filepath, index=False)
            print(f'结果已保存')
            # 更新任务进度管理表
            self.updateTaskTable("end_time", f'{current_time}')
            self.updateTaskTable("task_status", "已完成")
            self.updateTaskTable("video_result", f'{self.out_video_path}')
            self.updateTaskTable("image_result", f'{self.out_image_path}')
        except Exception as e:
            print(f'An error occurred when save result: {e}')
        try:
            # 更新轮次
            self.order = self.order + 1
            current_profile = {
                '实验配置文件': self.cfg_file,
                '轮次': self.order
            }
            with open(f'{config_directory_path}/profile.json', 'w', encoding='utf-8') as profile:
                json.dump(current_profile, profile, ensure_ascii=False, indent=4)
            print(f'保存实验追踪信息: {current_profile}')
        except Exception as e:
            print(f'An error occurred when snap experiment tracking configuration: {e}')

    # MFC RELATED
    def init_mfc_ui(self):
        self.mfc_worker = None
        self.mfc_dev_num = 16
        self.mfcData = [None for _ in range(self.mfc_dev_num)]
        self.mfc_schedules = [{} for _ in range(self.mfc_dev_num)]
        self.button_group = None
        self.mfc_comm = None
        self.mfc_time_interval = 100  # ms
        self.mfc_fps = 1000 / self.mfc_time_interval
        ports_list = list(list_ports.comports())
        ports_name = [port.name for port in ports_list]
        self.CBB_mfc_port.clear()
        self.CBB_mfc_port.addItems(ports_name)
        baudrate_list = ["4800", "9600", "19200", "38400", "43000", "56000", "57600"]
        self.CBB_mfc_buadrate.clear()
        self.CBB_mfc_buadrate.addItems(baudrate_list)
        self.button_group = QButtonGroup()
        for i in range(self.mfc_dev_num):
            radio_button = self.findChild(QRadioButton, f'RB_mfc_{i}')
            if radio_button:
                self.button_group.addButton(radio_button, i)
        self.BT_connect_mfc.clicked.connect(self.onConnectMFC)
        self.BT_set_mfc_sv.clicked.connect(self.onSetMFCSV)
        self.RB_mfc_vctrl.clicked.connect(self.onValueCtrl)
        self.RB_mfc_clean.clicked.connect(self.onSwitchClean)
        self.RB_mfc_close.clicked.connect(self.onSwitchClose)
        self.RB_mfc_digital.clicked.connect(self.onDigitalMode)
        self.RB_mfc_analog.clicked.connect(self.onAnalogMode)
        self.BT_mfc_setProgram.clicked.connect(self.onSetMFCProgram)
        self.BT_mfc_loadProgram.clicked.connect(self.onLoadMFCProgram)
        self.BT_mfc_launchProgram.clicked.connect(self.onLaunchMFCProgram)

        self.timer_mfc_window = QTimer(self)
        self.timer_mfc_window.timeout.connect(self.updateMFCData)
        self.timer_mfc_program = QTimer(self)
        self.timer_mfc_program.timeout.connect(self.checkTime)

    def onSetMFCProgram(self):
        try:
            filename = 'New Program'
            self.dialog = MFCProgramTableDialog(self, filename)
            if self.dialog.exec_() == QDialog.Accepted:
                print("Dialog was accepted.")
        except Exception as e:
            print(e)

    def onLoadMFCProgram(self):
        # 弹出文件选择对话框
        file_path, _ = QFileDialog.getOpenFileName(self, "Open File", f'{config_directory_path}/mfc_config', "CSV Files (*.csv);;All Files (*)")
        filename, _ = os.path.splitext(os.path.basename(file_path))
        if filename:
            # 这里可以添加代码来处理选中的文件42
            self.dialog = MFCProgramTableDialog(self, filename)
            self.dialog.loadTable(filename)
            print(f"Selected file: {filename}")
            if self.dialog.exec_() == QDialog.Accepted:
                print("Dialog was accepted.")

    def onLaunchMFCProgram(self):
        if self.mfc_worker:
            for idev in range(self.mfc_dev_num):
                self.mfc_worker.write_data('switch', MFCInputData(value=True, id=idev, addr=1))
                self.mfc_worker.write_data('switch', MFCInputData(value=True, id=idev, addr=3))
            self.mfc_launch_time = time.time()
            self.timer_mfc_program.start(1000)

    def writeMFCProgram(self):
        try:
            idev = self.dialog.zoneComboBox.currentIndex()
            print(f'idev: {idev}')
            # 清空现有的计划
            self.mfc_schedules[idev].clear()
            # 从表格中读取时间和设定值
            for row in range(self.dialog.tableWidget.rowCount()):
                time_edit = self.dialog.tableWidget.cellWidget(row, 0)
                t = int(time_edit.time().msecsSinceStartOfDay() / 1000)
                value = self.dialog.tableWidget.item(row, 1).text()
                self.mfc_schedules[idev][t] = value
            print(f'dev {idev} schedules: {self.mfc_schedules[idev]}')
            self.dialog.saveTable()
            QMessageBox.information(None, "文件写入", "文件写入成功！", QMessageBox.Ok)
        except Exception as e:
            print(e)

    def checkTime(self):
        try:
            time_since_launch = round(time.time() - self.mfc_launch_time)
            for idev in range(self.mfc_dev_num):
                for t in self.mfc_schedules[idev].keys():
                    diff = t - time_since_launch
                    if diff <= 0 and abs(diff) < 1:
                        value = self.mfc_schedules[idev][t]
                        self.writeToMFC(idev, value)
        except Exception as e:
            print(f'{e}')

    def writeToMFC(self, idev, value):
        # 写入设备
        if self.mfc_worker:
            print(f"Writing value {value} to device {idev} at {QTime.currentTime().toString('HH:mm:ss')}")
            self.mfc_worker.write_data('sv', MFCInputData(value=value, id=idev))

    def createMFCFig(self):
        # 创建一个Figure和FigureCanvas
        self.figure_mfc, self.ax_mfc = plt.subplots(constrained_layout=False)
        # self.figure_mfc.subplots_adjust(left=0.1, right=0.9, top=0.95,bottom=0.1)
        self.canvas_mfc = FigureCanvas(self.figure_mfc)
        self.ax_mfc.tick_params(axis='both', labelsize=8, labelcolor='gray')
        self.figure_mfc.set_facecolor('none')
        self.ax_mfc.set_facecolor('none')
        self.ax_mfc.grid(True, linestyle='--', alpha=0.5)
        self.VLayout_mfc_display.addWidget(self.canvas_mfc)
        #初始化图表
        self.mfc_time_range = 20
        self.xticks_interval = 4
        self.ax_mfc.xaxis.set_major_locator(MultipleLocator(self.xticks_interval))
        ctime = time.time()
        self.ax_mfc.set_xlim(ctime, ctime + self.mfc_time_range)
        tick_locs = self.ax_mfc.get_xticks()
        xlabels = [datetime.fromtimestamp(ts).strftime('%H:%M:%S') for ts in tick_locs]
        self.ax_mfc.set_xticks(tick_locs)
        self.ax_mfc.set_xticklabels(xlabels)
        self.ax_mfc.set_ylim(0, 100)  # 设置y轴的范围
        self.line_mfc_pv = [self.ax_mfc.plot([], [], 'r-')[0] for _ in range(self.mfc_dev_num)]
        self.line_mfc_sv = [self.ax_mfc.plot([], [], 'b-')[0] for _ in range(self.mfc_dev_num)]

    def onConnectMFC(self):
        if self.mfc_worker:
            self.closeMFC()
        else:
            self.startMFC()

    def startMFC(self):
        try:
            print(f'CBB_mfc_port:{self.CBB_mfc_port.currentText()}')
            self.mfc_worker = MFCWorker(portName=self.CBB_mfc_port.currentText(),
                                        baudRate=self.CBB_mfc_buadrate.currentText())
        except Exception as e:
            print(f"An error occurred connect to mfc comm: {e}")
            QMessageBox.critical(self, "Error", f"An error occurred connect to mfc comm: {e}")
        if self.mfc_worker:
            self.timer_mfc_window.start(self.mfc_time_interval)
            self.mfc_worker.result_signal.connect(self.handle_result_mfc)
            self.mfc_worker.start()
            self.GB_mfc_setSV.setEnabled(True)
            self.GB_mfc_switch.setEnabled(True)
            self.GB_mfc_crtlmode.setEnabled(True)
            self.GB_mfc_dev.setEnabled(True)
            self.createMFCFig()
            self.BT_connect_mfc.setText("断开")

    def closeMFC(self):
        self.timer_mfc_window.stop()
        self.figure_mfc.clf()
        self.canvas_mfc.draw()
        self.VLayout_mfc_display.removeWidget(self.canvas_mfc)
        self.canvas_mfc = None
        self.GB_mfc_setSV.setEnabled(False)
        self.GB_mfc_switch.setEnabled(False)
        self.GB_mfc_crtlmode.setEnabled(False)
        self.GB_mfc_dev.setEnabled(False)
        for i in range(self.mfc_dev_num):
            rb_mfc = self.findChild(QRadioButton, f'RB_mfc_{i}')
            rb_mfc.setEnabled(False)
            rb_mfc.setText("")
            rb_mfc.setEnabled(False)
            lbl_pv_mfc = self.findChild(QLabel, f'lbl_pv_mfc_{i}')
            lbl_pv_mfc.setText("")
            lbl_sv_mfc = self.findChild(QLabel, f'lbl_sv_mfc_{i}')
            lbl_sv_mfc.setText("")
        if self.mfc_worker:
            self.mfc_worker.stop_run()
        self.mfc_worker = None
        self.BT_connect_mfc.setText("连接")

    def handle_result_mfc(self, result):
        self.mfcData = copy.deepcopy(result)
        # print(f'mfc result updated')

    def onSetMFCSV(self):
        print(f'set value')
        try:
            if self.mfc_worker:
                sv = float(self.SB_mfc_sv.value())
                print(f'sv: {sv}')
                print(f'checked_id: {self.button_group.checkedId()}')
                self.mfc_worker.write_data('sv', MFCInputData(value=sv, id=self.button_group.checkedId()))
        except Exception as e:
            print(f"An error occurred when set mfc value: {e}")
            QMessageBox.critical(self, "Error", f"An error occurred when set mfc value: {e}")

    def onValueCtrl(self):
        if self.mfc_worker:
            self.mfc_worker.write_data('switch', MFCInputData(value=True, id=self.button_group.checkedId(), addr=1))

    def onSwitchClean(self):
        if self.mfc_worker:
            self.mfc_worker.write_data('switch', MFCInputData(value=True, id=self.button_group.checkedId(), addr=2))

    def onSwitchClose(self):
        if self.mfc_worker:
            self.mfc_worker.write_data('switch', MFCInputData(value=True, id=self.button_group.checkedId(), addr=0))

    def onAnalogMode(self):
        if self.mfc_worker:
            self.mfc_worker.write_data('switch', MFCInputData(value=False, id=self.button_group.checkedId(), addr=3))

    def onDigitalMode(self):
        if self.mfc_worker:
            self.mfc_worker.write_data('switch', MFCInputData(value=True, id=self.button_group.checkedId(), addr=3))

    def updateMFCData(self):
        current_time = time.time()
        points_num = int(self.mfc_time_range * self.mfc_fps)

        # 显示流量设定值和实际值
        for i in range(self.mfc_dev_num):
            try:
                if self.mfcData[i]:
                    rb_mfc = self.findChild(QRadioButton, f'RB_mfc_{i}')
                    rb_mfc.setEnabled(True)
                    rb_mfc.setText(f'{i}: {self.mfcData[i].fs}\n{self.mfcData[i].unit}')
                    lbl_pv_mfc = self.findChild(QLabel, f'lbl_pv_mfc_{i}')
                    lbl_pv_mfc.setText(f'{self.mfcData[i].pv} {self.mfcData[i].unit}')
                    lbl_sv_mfc = self.findChild(QLabel, f'lbl_sv_mfc_{i}')
                    lbl_sv_mfc.setText(f'{self.mfcData[i].sv} {self.mfcData[i].unit}')
                    # 显示当前选中设备设定值和瞬时流量值
                    if self.button_group.checkedId() == i:
                        self.lbl_mfc_sv.setText(f'{self.mfcData[i].sv} {self.mfcData[i].unit}')
                        self.lbl_mfc_pv.setText(f'{self.mfcData[i].pv} {self.mfcData[i].unit}')

                        # 统计最新的流量值
                        if self.recordFlag:
                            timestamp = int(time.time())
                            mfc_pv = self.mfcData[i].pv
                            mfc_sv = self.mfcData[i].sv
                            new_row = np.array([[timestamp, mfc_pv, mfc_sv]])
                            self.cacheMFCData = np.vstack((self.cacheMFCData, new_row))

                    # 显示控制模式
                    if self.button_group.checkedId() == i:
                        if self.mfcData[i].ctrl_mode == -1:
                            self.RB_mfc_crtllock.setChecked(True)
                        elif self.mfcData[i].ctrl_mode == 0:
                            self.RB_mfc_analog.setChecked(True)
                        elif self.mfcData[i].ctrl_mode == 1:
                            self.RB_mfc_digital.setChecked(True)
                        else:
                            print(f'ctrl mode error')
                    # 显示阀控状态
                    if self.button_group.checkedId() == i:
                        if self.mfcData[i].switch_state == -1:
                            self.RB_mfc_switchlock.setChecked(True)
                        elif self.mfcData[i].switch_state == 1:
                            self.RB_mfc_close.setChecked(True)
                        elif self.mfcData[i].switch_state == 2:
                            self.RB_mfc_vctrl.setChecked(True)
                        elif self.mfcData[i].switch_state == 4:
                            self.RB_mfc_clean.setChecked(True)
                        else:
                            print(f'switch state error')
                    # 设置设定按钮可用性和设定值单位
                    if self.button_group.checkedId() == i:
                        if self.mfcData[i].switch_state == 2 and self.mfcData[i].ctrl_mode == 1:
                            self.BT_set_mfc_sv.setEnabled(True)
                        else:
                            self.BT_set_mfc_sv.setEnabled(False)
                        self.lbl_mfc_sv_unit.setText(str(self.mfcData[i].unit))

                    # 更新line_mfc_pv
                    pv = self.mfcData[i].pv
                    xdata_mfc_pv, ydata_mfc_pv = self.line_mfc_pv[i].get_data()
                    xdata_mfc_pv = np.append(xdata_mfc_pv, current_time)
                    ydata_mfc_pv = np.append(ydata_mfc_pv, pv)
                    # 限制数据点数量，避免内存无限增长
                    if len(xdata_mfc_pv) > points_num:  # 保留最近数据点
                        xdata_mfc_pv = xdata_mfc_pv[-points_num:]
                        ydata_mfc_pv = ydata_mfc_pv[-points_num:]
                    # 更新line_mfc_sv
                    sv = self.mfcData[i].sv
                    xdata_mfc_sv, ydata_mfc_sv = self.line_mfc_sv[i].get_data()
                    xdata_mfc_sv = np.append(xdata_mfc_sv, current_time)
                    ydata_mfc_sv = np.append(ydata_mfc_sv, sv)
                    # 限制数据点数量，避免内存无限增长
                    if len(xdata_mfc_sv) > points_num:
                        xdata_mfc_sv = xdata_mfc_sv[-points_num:]
                        ydata_mfc_sv = ydata_mfc_sv[-points_num:]
                    # 更新图表
                    self.line_mfc_pv[i].set_data(xdata_mfc_pv, ydata_mfc_pv)
                    self.line_mfc_sv[i].set_data(xdata_mfc_sv, ydata_mfc_sv)
                    try:
                        if self.button_group.checkedId() == i:
                            self.line_mfc_pv[i].set_visible(True)
                            self.line_mfc_sv[i].set_visible(True)
                            tick_locs = self.ax_mfc.get_xticks()
                            x_min = max(0, xdata_mfc_pv[-1] - self.mfc_time_range)
                            x_max = xdata_mfc_pv[-1]
                            if tick_locs[0] < x_min:
                                tick_locs = tick_locs + self.xticks_interval
                            xlabels = [datetime.fromtimestamp(ts).strftime('%H:%M:%S') for ts in tick_locs]
                            self.ax_mfc.set_xticks(tick_locs)
                            self.ax_mfc.set_xticklabels(xlabels)
                            self.ax_mfc.set_xlim(x_min, x_max)
                            self.ax_mfc.relim()  # 重新计算轴的限制
                            self.ax_mfc.autoscale_view()  # 自动缩放视图
                            max_flow = max(self.mfcData[i].fs, self.mfcData[i].pv, self.mfcData[i].sv) * 1.4
                            self.ax_mfc.set_ylim(-1, max_flow)
                        else:
                            self.line_mfc_pv[i].set_visible(False)
                            self.line_mfc_sv[i].set_visible(False)
                    except Exception as e:
                        print(e)
                else:
                    rb_mfc = self.findChild(QRadioButton, f'RB_mfc_{i}')
                    rb_mfc.setText(f'{i}: 未连接')
                    rb_mfc.setEnabled(False)
            except Exception as e:
                print(e)
        # 绘制更新后的图表
        self.canvas_mfc.draw()

    # TEMPERATURE RELATED
    def init_tempctrl_ui(self):
        self.temp_worker = None
        self.rtu_server = None
        self.slave = None
        self.total_set_time_b = None
        self.total_set_time_a = None
        self.max_temperature_a = 0
        self.max_temperature_b = 0
        self.original_item_name = None
        self.dialog = None
        self.signal_comm = None
        self.is_final_step_a = False
        self.is_final_step_b = False
        self.program_a = None
        self.program_b = None
        self.aiBUSParam = None
        self.temp_zone_num = 2
        self.tempdevData = [None for _ in range(self.temp_zone_num)]
        self.temp_threshol_high = None
        self.temp_threshold_low = None
        self.temp_time_interval = 1000  # ms
        self.temp_fps = 1000 / self.temp_time_interval
        self.figure_a = None
        self.figure_b = None

        self.actionCreate.triggered.connect(self.createFile)
        self.actionOpen.triggered.connect(self.openFile)

        self.BT_hold_a.clicked.connect(self.onHoldA)
        self.BT_run_a.clicked.connect(self.onRunA)
        self.BT_hold_b.clicked.connect(self.onHoldB)
        self.BT_run_b.clicked.connect(self.onRunB)
        self.BT_stop_b.clicked.connect(self.onStopB)
        self.BT_stop_a.clicked.connect(self.onStopA)
        self.BT_connect_tempDev.clicked.connect(self.onConnectTempDev)
        self.BT_connect_signalComm.clicked.connect(self.onConnectSignalComm)
        self.BT_sendSignal.clicked.connect(self.onSendSignal)
        self.BT_set_temp_threshold.clicked.connect(self.onSetTempThreshold)

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
        self.timer_temperature_window = QTimer(self)
        self.timer_temperature_window.timeout.connect(self.updateTempData)  # 连接定时器信号到槽函数

        # 设置可用的comm端口号
        ports_list = list(list_ports.comports())
        ports_name = [port.name for port in ports_list]
        self.CBB_temp_port.clear()
        self.CBB_temp_port.addItems(ports_name)

        self.CBB_signal_port.clear()
        self.CBB_signal_port.addItems(ports_name)

    # slot functions for TempCtrlDev
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

    def writeTempProgram(self):
        current_index = self.dialog.zoneComboBox.currentIndex()
        print(f'current_index={current_index}')
        idev = current_index + 1
        try:
            if self.temp_worker:
                for row in range(self.dialog.tableWidget.rowCount()):
                    row_data = []
                    for column in range(self.dialog.tableWidget.columnCount()):
                        # 检查项是否存在，如果不存在则添加空字符串
                        item = self.dialog.tableWidget.item(row, column) if self.dialog.tableWidget.item(row, column) else None
                        row_data.append(item.text() if item else '')
                        print(f'item: {item.text() if item else ""}, row: {row}, column: {column}')
                        if item:
                            if column != 0 and item.text():
                                iparam = row * 2 + column + 79
                                value = float(item.text())
                                print(f'iparam: {iparam}, value: {value}')
                                self.temp_worker.write_data(TempInputData(iParamNo=iparam, Value=value, iDevAdd=idev))
                        else:
                            break
                if idev == 1:
                    self.lbl_buffer_a.setText(f'{self.dialog.filename}')
                else:
                    self.lbl_buffer_b.setText(f'{self.dialog.filename}')
                self.dialog.saveTable()
                QMessageBox.information(None, "文件写入", "文件写入成功！", QMessageBox.Ok)
                self.temp_worker.read_program_settings()
        except Exception as e:
            print(f"An error occurred while writing to the Buffer: {e}")
            QMessageBox.critical(self, "Error", f"An error occurred while writing to the Buffer: {e}")

    def onConnectTempDev(self):
        if self.temp_worker:
            self.close_temp()
        else:
            self.start_temp()

    def start_temp(self):
        try:
            print(f'CBB_temp_port:{self.CBB_temp_port.currentText()}')
            self.temp_worker = TempWorker(portName=f"{self.CBB_temp_port.currentText()}", baudRate=9600)
        except Exception as e:
            print(f"An error occurred connect to temperature control device: {e}")
            QMessageBox.critical(self, "Error", f"An error occurred connect to temperature control device: {e}")

        if self.temp_worker:
            self.timer_temperature_window.start(self.temp_time_interval)
            self.temp_worker.result_signal.connect(self.handle_result_temp)
            self.temp_worker.program_signal.connect(self.handle_result_pgm)
            self.temp_worker.start()
            self.temp_worker.read_program_settings()
            self.BT_run_a.setEnabled(True)
            self.BT_hold_a.setEnabled(True)
            self.BT_stop_a.setEnabled(True)
            self.BT_run_b.setEnabled(True)
            self.BT_hold_b.setEnabled(True)
            self.BT_stop_b.setEnabled(True)
            self.tree_config.setEnabled(True)
            self.createTempFig()
            self.BT_connect_tempDev.setText("断开")

    def close_temp(self):
        try:
            self.timer_temperature_window.stop()
            self.temp_worker.stop_run()
            self.temp_worker=None
            self.figure_a.clf()
            self.canvas_a.draw()
            self.VLayout_tempDisplay_a.removeWidget(self.canvas_a)
            self.canvas_a = None
            self.figure_b.clf()
            self.canvas_b.draw()
            self.VLayout_tempDisplay_b.removeWidget(self.canvas_b)
            self.canvas_b = None
            self.lbl_pv_a.clear()
            self.lbl_sv_a.clear()
            self.lbl_mv_a.clear()
            self.lbl_step_a.clear()
            self.lbl_time_a.clear()
            self.lbl_pv_b.clear()
            self.lbl_sv_b.clear()
            self.lbl_mv_b.clear()
            self.lbl_step_b.clear()
            self.lbl_time_b.clear()
            self.psbar_a.setValue(0)
            self.psbar_b.setValue(0)
            self.BT_run_a.setEnabled(False)
            self.BT_hold_a.setEnabled(False)
            self.BT_stop_a.setEnabled(False)
            self.BT_run_b.setEnabled(False)
            self.BT_hold_b.setEnabled(False)
            self.BT_stop_b.setEnabled(False)
            self.tree_config.setEnabled(False)
            self.BT_stop_a.setStyleSheet(self.default_color)
            self.BT_hold_a.setStyleSheet(self.default_color)
            self.BT_run_a.setStyleSheet(self.default_color)
            self.BT_stop_b.setStyleSheet(self.default_color)
            self.BT_hold_b.setStyleSheet(self.default_color)
            self.BT_run_b.setStyleSheet(self.default_color)
            self.BT_connect_tempDev.setText("连接")
        except Exception as e:
            print(f'An error occurred when close temp: {e}')

    def set_temp_xlim(self):
        self.total_set_time_a = sum(self.program_a[1][:-1])
        self.total_set_time_b = sum(self.program_b[1][:-1])
        if self.total_set_time_a and self.total_set_time_b:
            self.temp_time_range = max(self.total_set_time_a, self.total_set_time_b) * 60
            ctime = time.time()
            self.ax_a.set_xlim(ctime, ctime + self.temp_time_range - 1)
            xticks = [ctime + i * self.temp_time_range / 4 for i in range(5)]
            xlabels = [datetime.fromtimestamp(ts).strftime('%H:%M:%S') for ts in xticks]
            self.ax_a.set_xticks(xticks, xlabels)

            self.ax_b.set_xlim(ctime, ctime + self.temp_time_range - 1)
            xticks = [ctime + i * self.temp_time_range / 4 for i in range(5)]
            xlabels = [datetime.fromtimestamp(ts).strftime('%H:%M:%S') for ts in xticks]
            self.ax_b.set_xticks(xticks, xlabels)

    def onSetTempThreshold(self):
        if self.IsThresholdSet:
            self.cancel_threshold()
        else:
            self.set_threshold()

    def set_threshold(self):
        try:
            temp_threshold_low = self.SB_temp_threshold_low.text()
            temp_threshold_high = self.SB_temp_threshold_high.text()
            if temp_threshold_low and temp_threshold_high:
                self.temp_threshold_low = int(temp_threshold_low)
                self.temp_threshold_high = int(temp_threshold_high)
                print(f'set temp threshold: {self.temp_threshold_low} - {self.temp_threshold_high}')
            self.BT_set_temp_threshold.setChecked(True)
            self.BT_set_temp_threshold.setText("取消设定")
            self.IsThresholdSet = True
        except Exception as e:
            print(f'An error occurred when set temp threshold: {e}')

    def cancel_threshold(self):
        self.BT_set_temp_threshold.setChecked(False)
        self.BT_set_temp_threshold.setText("设定")
        self.temp_threshold_low = None
        self.temp_threshol_high = None
        self.SB_temp_threshold_low.clear()
        self.SB_temp_threshold_high.clear()
        self.IsThresholdSet = False

    def onConnectSignalComm(self):
        if self.rtu_server:
            self.close_signalcomm()
        else:
            self.start_signalcomm()

    def start_signalcomm(self):
        try:
            self.signal_comm = serial.Serial(port=f"{self.CBB_signal_port.currentText()}", baudrate=9600, bytesize=8, parity='N', stopbits=1)
            self.rtu_server = modbus_rtu.RtuServer(self.signal_comm)
        except Exception as e:
            print(f"An error occurred connect to PLC: {e}")
            QMessageBox.critical(self, "Error", f"An error occurred connect to PCL: {e}")
        if self.rtu_server:
            self.rtu_server.start()
            self.slave = self.rtu_server.add_slave(3)
            self.slave.add_block('0', cst.HOLDING_REGISTERS, 0, 1200)
            self.slave.add_block('1', cst.COILS, 0, 1200)
            self.BT_set_temp_threshold.setEnabled(True)
            self.BT_sendSignal.setEnabled(True)
            self.BT_connect_signalComm.setText("断开")

    def close_signalcomm(self):
        self.rtu_server.remove_slave(3)
        self.rtu_server.stop()
        self.rtu_server = None
        self.slave = None
        self.signal_comm = None
        self.cancel_threshold()
        self.BT_set_temp_threshold.setEnabled(False)
        self.BT_sendSignal.setEnabled(False)
        self.SB_temp_threshold_low.clear()
        self.SB_temp_threshold_high.clear()
        self.BT_connect_signalComm.setText("连接")

    def handle_result_pgm(self, result):
        self.program_a, self.program_b = copy.deepcopy(result)
        print(f'program a: {self.program_a}')
        print(f'program b: {self.program_b}')
        # 每次读取新温度程序后都更新一次温度曲线横轴范围
        self.set_temp_xlim()

    def handle_result_temp(self, result):
        self.tempdevData = copy.deepcopy(result)
        # print(f'temp result updated')

    def onRunA(self):
        if self.temp_worker:
            self.is_final_step_a = False
            self.BT_run_a.setChecked(True)
            self.temp_worker.write_data(TempInputData(iParamNo=27, Value=0, iDevAdd=1))
            print(f'runA')

    def onRunB(self):
        if self.temp_worker:
            self.is_final_step_b = False
            self.BT_run_b.setChecked(True)
            self.temp_worker.write_data(TempInputData(iParamNo=27, Value=0, iDevAdd=2))
            print(f'runB')

    def onHoldA(self):
        if self.temp_worker:
            self.BT_hold_a.setChecked(True)
            self.temp_worker.write_data(TempInputData(iParamNo=27, Value=2, iDevAdd=1))
            print(f'holdA')

    def onHoldB(self):
        if self.temp_worker:
            self.BT_hold_b.setChecked(True)
            self.temp_worker.write_data(TempInputData(iParamNo=27, Value=2, iDevAdd=2))
            print(f'holdB')

    def onStopA(self):
        if self.temp_worker:
            self.BT_stop_a.setChecked(True)
            self.temp_worker.write_data(TempInputData(iParamNo=27, Value=1, iDevAdd=1))
            print(f'stopA')

    def onStopB(self):
        if self.temp_worker:
            self.BT_stop_b.setChecked(True)
            self.temp_worker.write_data(TempInputData(iParamNo=27, Value=1, iDevAdd=2))
            print(f'stopB')

    def updateTempData(self):
        # 将温度值显示在QLineEdit中
        ctime = time.time()
        if self.tempdevData[0]:
            self.lbl_pv_a.setText(str(self.tempdevData[0].pv))
            self.lbl_sv_a.setText(str(self.tempdevData[0].sv))
            self.lbl_mv_a.setText(str(self.tempdevData[0].mv))
            self.lbl_step_a.setText(str(self.tempdevData[0].step))
            self.lbl_time_a.setText(str(self.tempdevData[0].tim))
            if self.tempdevData[0].state == 0:
                self.BT_run_a.setChecked(True)
                self.BT_run_a.setStyleSheet(self.selected_color)
                self.BT_hold_a.setStyleSheet(self.default_color)
                self.BT_stop_a.setStyleSheet(self.default_color)
            elif self.tempdevData[0].state == 1:
                self.BT_stop_a.setChecked(True)
                self.BT_stop_a.setStyleSheet(self.selected_color)
                self.BT_hold_a.setStyleSheet(self.default_color)
                self.BT_run_a.setStyleSheet(self.default_color)
            elif self.tempdevData[0].state == 2:
                self.BT_hold_a.setChecked(True)
                self.BT_hold_a.setStyleSheet(self.selected_color)
                self.BT_run_a.setStyleSheet(self.default_color)
                self.BT_stop_a.setStyleSheet(self.default_color)
            else:
                print(f'state_a error')

        if self.tempdevData[1]:
            self.lbl_pv_b.setText(str(self.tempdevData[1].pv))
            self.lbl_sv_b.setText(str(self.tempdevData[1].sv))
            self.lbl_mv_b.setText(str(self.tempdevData[1].mv))
            self.lbl_step_b.setText(str(self.tempdevData[1].step))
            self.lbl_time_b.setText(str(self.tempdevData[1].tim))
            if self.tempdevData[1].state == 0:
                self.BT_run_b.setChecked(True)
                self.BT_run_b.setStyleSheet(self.selected_color)
                self.BT_hold_b.setStyleSheet(self.default_color)
                self.BT_stop_b.setStyleSheet(self.default_color)
            elif self.tempdevData[1].state == 1:
                self.BT_stop_b.setChecked(True)
                self.BT_stop_b.setStyleSheet(self.selected_color)
                self.BT_hold_b.setStyleSheet(self.default_color)
                self.BT_run_b.setStyleSheet(self.default_color)
            elif self.tempdevData[1].state == 2:
                self.BT_hold_b.setChecked(True)
                self.BT_hold_b.setStyleSheet(self.selected_color)
                self.BT_run_b.setStyleSheet(self.default_color)
                self.BT_stop_b.setStyleSheet(self.default_color)
            else:
                print(f'state_b error')

        try:
            self.total_set_time_a = sum(self.program_a[1][:-1])
            self.total_set_time_b = sum(self.program_b[1][:-1])
            if self.tempdevData[0]:
                # 绘制ZoneA温度曲线
                if self.total_set_time_a and self.total_set_time_b:
                    self.temp_time_range = max(self.total_set_time_a, self.total_set_time_b) * 60
                x_data_pv_a, y_data_pv_a = self.line_pv_a.get_data()
                if len(x_data_pv_a) > self.temp_time_range * self.temp_fps:
                    x_data_pv_a = []
                    y_data_pv_a = []
                    self.ax_a.set_xlim(ctime, ctime + self.temp_time_range - 1)
                    xticks = [ctime + i * self.temp_time_range / 4 for i in range(5)]
                    xlabels = [datetime.fromtimestamp(ts).strftime('%H:%M:%S') for ts in xticks]
                    self.ax_a.set_xticks(xticks, xlabels)
                x_data_pv_a = np.append(x_data_pv_a, ctime)
                y_data_pv_a = np.append(y_data_pv_a, self.tempdevData[0].pv)

                x_data_sv_a, y_data_sv_a = self.line_sv_a.get_data()
                if len(x_data_sv_a) > self.temp_time_range * self.temp_fps:
                    x_data_sv_a = []
                    y_data_sv_a = []
                x_data_sv_a = np.append(x_data_sv_a, ctime)
                y_data_sv_a = np.append(y_data_sv_a, self.tempdevData[0].sv)
                # 更新图形
                self.line_pv_a.set_data(x_data_pv_a, y_data_pv_a)
                self.line_sv_a.set_data(x_data_sv_a, y_data_sv_a)
                self.max_temperature_a = max(self.max_temperature_a, max(self.tempdevData[0].pv,
                                                                         self.tempdevData[0].sv) * 1.4)
                self.ax_a.set_ylim(-5, self.max_temperature_a)
                self.ax_a.relim()  # 重新计算坐标轴的界限
                self.ax_a.autoscale_view(True, True, True)  # 自动缩放
                self.canvas_a.draw()  # 重绘画布
            if self.tempdevData[1]:
                # 绘制ZoneB温度曲线
                x_data_pv_b, y_data_pv_b = self.line_pv_b.get_data()
                if len(x_data_pv_b) > self.temp_time_range * self.temp_fps:
                    x_data_pv_b = []
                    y_data_pv_b = []
                    self.ax_b.set_xlim(ctime, ctime + self.temp_time_range - 1)
                    xticks = [ctime + i * self.temp_time_range / 4 for i in range(5)]
                    xlabels = [datetime.fromtimestamp(ts).strftime('%H:%M:%S') for ts in xticks]
                    self.ax_b.set_xticks(xticks, xlabels)
                x_data_pv_b = np.append(x_data_pv_b, ctime)
                y_data_pv_b = np.append(y_data_pv_b, self.tempdevData[1].pv)

                x_data_sv_b, y_data_sv_b = self.line_sv_b.get_data()
                if len(x_data_sv_b) > self.temp_time_range * self.temp_fps:
                    x_data_sv_b = []
                    y_data_sv_b = []
                x_data_sv_b = np.append(x_data_sv_b, ctime)
                y_data_sv_b = np.append(y_data_sv_b, self.tempdevData[1].sv)
                # 更新图形
                self.line_pv_b.set_data(x_data_pv_b, y_data_pv_b)
                self.line_sv_b.set_data(x_data_sv_b, y_data_sv_b)
                self.max_temperature_b = max(self.max_temperature_b, max(self.tempdevData[1].pv,
                                                                         self.tempdevData[1].sv) * 1.4)
                self.ax_b.set_ylim(-5, self.max_temperature_b)
                self.ax_b.relim()  # 重新计算坐标轴的界限
                self.ax_b.autoscale_view(True, True, True)  # 自动缩放
                self.canvas_b.draw()  # 重绘画布

                # 点击记录按钮，开始搜集温度数据
                if self.recordFlag:
                    timestamp = int(time.time())
                    pv_a = self.line_pv_a.get_ydata()[-1]
                    sv_a = self.line_sv_a.get_ydata()[-1]
                    pv_b = self.line_pv_b.get_ydata()[-1]
                    sv_b = self.line_sv_b.get_ydata()[-1]
                    new_row = np.array([[timestamp, pv_a, sv_a, pv_b, sv_b]])
                    self.cacheTempData = np.vstack((self.cacheTempData, new_row))

            # 绘制进度条
            try:
                if self.tempdevData[0]:
                    if self.program_a[1]:
                        if self.is_final_step_a and self.tempdevData[0].step == 1:

                            progress_time_a = self.total_set_time_a
                        else:
                            progress_time_a = sum(self.program_a[1][:self.tempdevData[0].step - 1]) + self.tempdevData[
                                0].tim
                        progress_percent_a = int(progress_time_a / self.total_set_time_a * 100)
                        self.psbar_a.setValue(progress_percent_a)
                if self.tempdevData[1]:
                    if self.program_b[1]:
                        if self.is_final_step_b and self.tempdevData[1].step == 1:
                            progress_time_b = self.total_set_time_b
                        else:
                            progress_time_b = sum(self.program_b[1][:self.tempdevData[1].step - 1]) + self.tempdevData[
                                1].tim
                        progress_percent_b = int(progress_time_b / self.total_set_time_b * 100)
                        self.psbar_b.setValue(progress_percent_b)
                        # 更新任务管理表中当前任务的进度（以温区B的温度曲线进度为准）
                        self.updateTaskTable("progress", f'{progress_percent_b}%')
            except Exception as e:
                print(e)

        except Exception as e:
            print(e)

    def createTempFig(self):
        #创建温度曲线图表
        self.figure_a, self.ax_a = plt.subplots(constrained_layout=True)
        # self.figure_a.subplots_adjust(left=0.1, right=0.9, top=0.95, bottom=0.2)
        self.figure_a.set_facecolor('none')
        self.ax_a.set_facecolor('none')
        self.ax_a.grid(True, linestyle='--', alpha=0.5)
        self.ax_a.tick_params(axis='x', labelsize=8, labelcolor='gray')
        self.ax_a.tick_params(axis='y', labelsize=8, labelcolor='gray')
        self.canvas_a = FigureCanvas(self.figure_a)
        self.line_pv_a, = self.ax_a.plot([], [], 'orangered')  # 'r-' 表示红色线条
        self.line_sv_a, = self.ax_a.plot([], [], 'lightskyblue')
        self.label_date_a = QLabel("date")
        self.VLayout_tempDisplay_a.addWidget(self.canvas_a)

        self.figure_b, self.ax_b = plt.subplots(constrained_layout=True)
        # self.figure_b.subplots_adjust(left=0.1, right=0.9, top=0.95, bottom=0.2)
        self.figure_b.set_facecolor('none')
        self.ax_b.set_facecolor('none')
        self.ax_b.grid(True, linestyle='--', alpha=0.5)
        self.ax_b.tick_params(axis='x', labelsize=8, labelcolor='gray')
        self.ax_b.tick_params(axis='y', labelsize=8, labelcolor='gray')
        self.canvas_b = FigureCanvas(self.figure_b)
        self.canvas_b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.line_pv_b, = self.ax_b.plot([], [], 'orangered')  # 'r-' 表示红色线条
        self.line_sv_b, = self.ax_b.plot([], [], 'lightskyblue')
        self.label_date_b = QLabel("date")
        self.VLayout_tempDisplay_b.addWidget(self.canvas_b)

        # 设置时间轴的刻度和显示
        self.temp_time_range = 1200
        ctime = time.time()
        xticks = [ctime + i * self.temp_time_range / 4 + 1 for i in range(5)]
        xlabels = [datetime.fromtimestamp(ts).strftime('%H:%M:%S') for ts in xticks]
        self.ax_a.set_xlim(ctime + 1, ctime + self.temp_time_range)
        self.ax_a.set_xticks(xticks, xlabels)
        self.ax_a.yaxis.set_major_formatter(FormatStrFormatter('%.1f'))
        self.ax_b.set_xlim(ctime + 1, ctime + self.temp_time_range)
        self.ax_b.set_xticks(xticks, xlabels)
        self.ax_b.yaxis.set_major_formatter(FormatStrFormatter('%.1f'))

    # MICROSCOPE RELATED
    def init_microscope_ui(self):
        self.hcam = None
        self.is_recording = False
        self.out_video_path = None
        self.out_video_path2 = None
        self.video_writer = None
        self.video_writer2 = None
        self.timer_camera = QTimer(self)
        self.imgWidth = 0
        self.imgHeight = 0
        self.pData = None
        self.res = 0
        self.temp = toupcam.TOUPCAM_TEMP_DEF
        self.tint = toupcam.TOUPCAM_TINT_DEF
        self.count = 0

        # self.GB_scopeImage.setMinimumSize(640, 480)
        self.btn_open.clicked.connect(self.onBtnOpen)
        self.btn_snap.clicked.connect(self.onBtnSnap)
        self.btn_save.clicked.connect(self.onBtnSave)
        self.lbl_video = DrawableLabel(self.GB_scopeImage)
        sizePolicy = QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        sizePolicy.setHorizontalStretch(1)
        sizePolicy.setVerticalStretch(1)
        sizePolicy.setHeightForWidth(self.lbl_video.sizePolicy().hasHeightForWidth())
        self.lbl_video.setSizePolicy(sizePolicy)
        self.lbl_video.setMinimumSize(QSize(400, 300))
        self.lbl_video.setMaximumSize(QSize(2592, 1944))
        self.lbl_video.setAlignment(Qt.AlignLeading|Qt.AlignLeft|Qt.AlignVCenter)
        self.lbl_video.setScaledContents(False)
        self.lbl_video.setObjectName("lbl_video")
        self.layout_microscope.addWidget(self.lbl_video)

        self.cmb_res.currentIndexChanged.connect(self.onResolutionChanged)
        self.cmb_magnification.setCurrentIndex(1)
        self.cmb_magnification.currentIndexChanged.connect(self.onMagnificationChanged)
        self.cbox_auto.stateChanged.connect(self.onAutoExpo)
        self.slider_expoTime.valueChanged.connect(self.onExpoTime)
        self.slider_expoGain.valueChanged.connect(self.onExpoGain)
        self.slider_mag.valueChanged.connect(self.onMagScale)
        self.slider_mag.valueChanged.connect(self.onMagnificationChanged)
        self.slider_mag.setRange(10, 100)
        self.slider_mag.setValue(100)
        self.btn_autoWB.clicked.connect(self.onAutoWB)
        self.lbl_temp.setText(str(toupcam.TOUPCAM_TEMP_DEF))
        self.lbl_tint.setText(str(toupcam.TOUPCAM_TINT_DEF))
        self.slider_temp.setRange(toupcam.TOUPCAM_TEMP_MIN, toupcam.TOUPCAM_TEMP_MAX)
        self.slider_temp.setValue(toupcam.TOUPCAM_TEMP_DEF)
        self.slider_tint.setRange(toupcam.TOUPCAM_TINT_MIN, toupcam.TOUPCAM_TINT_MAX)
        self.slider_tint.setValue(toupcam.TOUPCAM_TINT_DEF)
        self.slider_temp.valueChanged.connect(self.onWBTemp)
        self.slider_tint.valueChanged.connect(self.onWBTint)

        self.timer_camera.timeout.connect(self.onTimer)
        self.evtCallback.connect(self.onevtCallback)

    # slot functions for microscope camera
    def onTimer(self):
        if self.hcam:
            try:
                nFrame, nTime, nTotalFrame = self.hcam.get_FrameRate()
                if nTime != 0:
                    self.lbl_frame.setText("{}, fps = {:.1f}".format(nTotalFrame, nFrame * 1000.0 / nTime))
            except Exception as e:
                print(f'An error occurred when set nFrame: {e}')
            self.updateImage()
            # 刷新比例尺和显微图像尺寸
            self.onMagnificationChanged()

    def closeCamera(self):
        try:
            if self.hcam:
                self.stop_recording()
                self.hcam.Close()
                self.hcam = None
                self.pData = None
                self.btn_open.setText("打开")
                self.timer_camera.stop()
                self.lbl_frame.clear()
                self.cmb_res.clear()
                self.cbox_auto.setEnabled(False)
                self.slider_expoGain.setEnabled(False)
                self.slider_expoTime.setEnabled(False)
                self.btn_autoWB.setEnabled(False)
                self.slider_temp.setEnabled(False)
                self.slider_tint.setEnabled(False)
                self.btn_snap.setEnabled(False)
                self.btn_save.setEnabled(False)
                self.cmb_res.setEnabled(False)
                self.GB_camera_res.setEnabled(False)
                self.GB_camera_exposure.setEnabled(False)
                self.GB_camera_wb.setEnabled(False)
        except Exception as e:
            print(f'An error occurred when close camera: {e}')

    def onResolutionChanged(self, index):
        try:
            if self.hcam:  #step 1: stop camera
                self.hcam.Stop()

            self.res = index
            self.imgWidth = self.cur.model.res[index].width
            self.imgHeight = self.cur.model.res[index].height

            if self.hcam:  #step 2: restart camera
                self.hcam.put_eSize(self.res)
                self.startCamera()
        except Exception as e:
            print(f'An error occurred when change resolution: {e}')

    def onMagnificationChanged(self):
        """刷新比例尺和显微图像尺寸"""
        try:
            mag = int(self.cmb_magnification.currentText())
            val = int(self.slider_mag.value())
            self.line_len = mag / 20 * 421 * val / 100
            line_len_cpr = self.line_len * self.lbl_video.width() / 2592
            coefficient = val / line_len_cpr
            self.lbl_video.setCoefficient(coefficient)
            self.line_mag.setFixedWidth(int(line_len_cpr))
            self.lbl_mag.setText(f'{val}μm')
        except Exception as e:
            print(f'An error occurred when Magnification Changed: {e}')

    def onAutoExpo(self, state):
        if self.hcam:
            self.hcam.put_AutoExpoEnable(1 if state else 0)
            self.slider_expoTime.setEnabled(not state)
            self.slider_expoGain.setEnabled(not state)

    def onExpoTime(self, value):
        if self.hcam:
            self.lbl_expoTime.setText(str(value))
            if not self.cbox_auto.isChecked():
                self.hcam.put_ExpoTime(value)

    def onExpoGain(self, value):
        if self.hcam:
            self.lbl_expoGain.setText(str(value))
            if not self.cbox_auto.isChecked():
                self.hcam.put_ExpoAGain(value)

    def onMagScale(self, value):
        self.lbl_magScale.setText(str(value))

    def onAutoWB(self):
        if self.hcam:
            self.hcam.AwbOnce()

    def wbCallback(nTemp, nTint, self):
        self.slider_temp.setValue(nTemp)
        self.slider_tint.setValue(nTint)

    def onWBTemp(self, value):
        if self.hcam:
            self.temp = value
            self.hcam.put_TempTint(self.temp, self.tint)
            self.lbl_temp.setText(str(value))

    def onWBTint(self, value):
        if self.hcam:
            self.tint = value
            self.hcam.put_TempTint(self.temp, self.tint)
            self.lbl_tint.setText(str(value))

    def startCamera(self):
        try:
            self.pData = bytes(toupcam.TDIBWIDTHBYTES(self.imgWidth * 24) * self.imgHeight)
            uimin, uimax, uidef = self.hcam.get_ExpTimeRange()
            self.slider_expoTime.setRange(uimin, uimax)
            self.slider_expoTime.setValue(uidef)
            usmin, usmax, usdef = self.hcam.get_ExpoAGainRange()
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
                self.GB_camera_res.setEnabled(True)
                self.GB_camera_exposure.setEnabled(True)
                self.GB_camera_wb.setEnabled(True)
                self.cmb_res.setEnabled(True)
                self.cbox_auto.setEnabled(True)
                self.btn_autoWB.setEnabled(self.cur.model.flag & toupcam.TOUPCAM_FLAG_MONO == 0)
                self.slider_temp.setEnabled(self.cur.model.flag & toupcam.TOUPCAM_FLAG_MONO == 0)
                self.slider_tint.setEnabled(self.cur.model.flag & toupcam.TOUPCAM_FLAG_MONO == 0)
                self.btn_open.setText("关闭")
                self.btn_snap.setEnabled(True)
                self.btn_save.setEnabled(True)
                bAuto = self.hcam.get_AutoExpoEnable()
                self.cbox_auto.setChecked(1 == bAuto)
                self.timer_camera.start(100)
        except Exception as e:
            print(f'An error occurred when start camera: {e}')

    def openCamera(self):
        try:
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
                self.hcam.put_Option(toupcam.TOUPCAM_OPTION_BYTEORDER, 0)  # Qimage use RGB byte order
                self.hcam.put_AutoExpoEnable(1)
                self.startCamera()
        except Exception as e:
            print(f'An error occurred when open camera: {e}')

    # 打开摄像头
    def onBtnOpen(self):
        if self.hcam:
            self.closeCamera()
        else:
            self.widget_mag.show()
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

    # 拍摄快照
    def onBtnSnap(self):
        if self.hcam:
            try:
                self.autoFocusFlag = False
                if 0 == self.cur.model.still:    # not support still image capture
                    if self.pData is not None:
                        image = QImage(self.pData, self.imgWidth, self.imgHeight, QImage.Format_RGB888)
                        self.count += 1
                        dtime = datetime.fromtimestamp(time.time()).strftime('%H%M%S')
                        out_image_path = os.path.join(image_directory_path, f'{self.exp_id}_{self.order}_{dtime}_{self.count}.jpg')
                        image.save(f'{out_image_path}')
                        print(f'save image to {out_image_path}')
                        mag = int(self.cmb_magnification.currentText())
                        val = int(self.slider_mag.value())
                        self.line_len = mag / 20 * 421 * val / 100
                        text = f'{val}μm'
                        qimage = self.add_text_to_image(image, text,
                                                        QPoint(image.width() - int(self.line_len) - 50, image.height() - 30),
                                                        20)
                        qimage = self.draw_line_with_arrows(qimage, QPoint(image.width() - int(self.line_len) - 50,
                                                                           image.height() - 10),
                                                            QPoint(image.width() - 50, image.height() - 10))
                        out_image_path2 = os.path.join(image_directory_path, f'{self.exp_id}_{self.order}_{dtime}_{self.count}_scale.jpg')
                        qimage.save(f'{out_image_path2}')
                        print(f'save image to {out_image_path2}')
                else:
                    # 手动操作时显示分辨率选择菜单
                    menu = QMenu()
                    for i in range(0, self.cur.model.still):
                        action = QAction("{}*{}".format(self.cur.model.res[i].width, self.cur.model.res[i].height),
                                         self)
                        action.setData(i)
                        menu.addAction(action)
                    action = menu.exec(self.btn_snap.mapToGlobal(QPoint(0, self.btn_snap.height())))
                    if action:  # 确保用户选择了分辨率
                        self.hcam.Snap(action.data())
                self.autoFocusFlag =True
            except Exception as e:
                print(f'{e}')

    def onBtnSnapAuto(self, target_width=2592, target_height=1944):
        """自动对焦时使用的拍照方法，默认使用指定分辨率"""
        if self.hcam:
            try:
                self.autoFocusFlag = True
                if 0 == self.cur.model.still:  # not support still image capture
                    if self.pData is not None:
                        image = QImage(self.pData, self.imgWidth, self.imgHeight, QImage.Format_RGB888)
                        self.count += 1
                        dtime = datetime.fromtimestamp(time.time()).strftime('%H%M%S')
                        out_image_path = os.path.join(image_directory_path,
                                                      f'{self.exp_id}_{self.order}_{dtime}_{self.count}.jpg')
                        image.save(f'{out_image_path}')
                        print(f'save image to {out_image_path}')
                        mag = int(self.cmb_magnification.currentText())
                        val = int(self.slider_mag.value())
                        self.line_len = mag / 20 * 421 * val / 100
                        text = f'{val}μm'
                        qimage = self.add_text_to_image(image, text,
                                                        QPoint(image.width() - int(self.line_len) - 50,
                                                               image.height() - 30),
                                                        20)
                        qimage = self.draw_line_with_arrows(qimage, QPoint(image.width() - int(self.line_len) - 50,
                                                                           image.height() - 10),
                                                            QPoint(image.width() - 50, image.height() - 10))
                        out_image_path2 = os.path.join(image_directory_path,
                                                       f'{self.exp_id}_{self.order}_{dtime}_{self.count}_scale.jpg')
                        qimage.save(f'{out_image_path2}')
                        print(f'save image to {out_image_path2}')
                else:
                    # 自动对焦时使用默认分辨率，不显示菜单
                    default_resolution_index = -1

                    # 查找匹配的分辨率索引
                    for i in range(0, self.cur.model.still):
                        if (self.cur.model.res[i].width == target_width and
                                self.cur.model.res[i].height == target_height):
                            default_resolution_index = i
                            break

                    # 如果找到了目标分辨率，使用它；否则使用第一个可用分辨率
                    if default_resolution_index != -1:
                        # print(f'自动对焦使用分辨率: {target_width}*{target_height}')
                        self.hcam.Snap(default_resolution_index)
                    else:
                        # 如果没有找到目标分辨率，打印可用分辨率并使用第一个
                        print(f'未找到分辨率 {target_width}*{target_height}，可用分辨率:')
                        for i in range(0, self.cur.model.still):
                            print(f'  {i}: {self.cur.model.res[i].width}*{self.cur.model.res[i].height}')
                        print(
                            f'自动对焦使用第一个可用分辨率: {self.cur.model.res[0].width}*{self.cur.model.res[0].height}')
                        self.hcam.Snap(0)
            except Exception as e:
                print(f'自动拍照时出错: {e}')

    def onBtnSnap2(self):
        try:
            if self.hcam:
                if self.pData is not None:
                    image = QImage(self.pData, self.imgWidth, self.imgHeight, QImage.Format_RGB888)
                    self.count += 1
                    painter = QPainter(image)
                    # 设置笔刷颜色和字体
                    painter.setPen(QPen(Qt.black))
                    font = QFont()
                    font.setPointSize(70)
                    painter.setFont(font)
                    # 获取当前日期和时间
                    if self.tempdevData[0] and self.tempdevData[1]:
                        info = (f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} '
                                f'\n'
                                f'ZoneA: {self.tempdevData[0].pv} °C'
                                f'\n'
                                f' ZoneB: {self.tempdevData[1].pv} °C')
                    else:
                        info = (f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} '
                                f'\n'
                                f'ZoneA: Unknown'
                                f'\n'
                                f'ZoneB: Unknown')
                    # 绘制文本
                    painter.drawText(image.rect(), Qt.AlignTop | Qt.AlignLeft, info)
                    # 完成绘制
                    painter.end()
                    dtime = datetime.fromtimestamp(time.time()).strftime('%H%M%S')
                    out_image_path = os.path.join(image_directory_path, f'{self.exp_id}_{self.order}_{dtime}_{self.count}_mix.jpg')
                    image.save(out_image_path)
                    return out_image_path
        except Exception as e:
            print(f'An error occurred when snap: {e}')

    def saveToVideo(self, cv_img):
        try:
            if self.figure_a and self.figure_b:
                frame_a = np.frombuffer(self.canvas_a.buffer_rgba(), dtype=np.uint8).reshape(self.canvas_a.height(), self.canvas_a.width(), 4)
                frame_b = np.frombuffer(self.canvas_b.buffer_rgba(), dtype=np.uint8).reshape(self.canvas_b.height(), self.canvas_b.width(), 4)
                frame_c = cv_img
                height1, width1 = frame_a.shape[:2]
                height2, width2 = frame_b.shape[:2]
                height3, width3 = frame_c.shape[:2]
                # scale_factor_a = int(0.5*width3/width1)
                # scale_factor_b = int(0.5*width3/width2)
                scale_factor_a = 0.5*width3/width1
                scale_factor_b = 0.5*width3/width2
                frame_a = cv2.resize(frame_a, None, fx=scale_factor_a, fy=scale_factor_a)
                frame_b = cv2.resize(frame_b, None, fx=scale_factor_b, fy=scale_factor_b)
                height1, width1 = frame_a.shape[:2]
                height2, width2 = frame_b.shape[:2]
                # 定义小图要覆盖到大图的位置
                big_image = self.overlay_image(frame_c, frame_a, (width3-width1-width2, 30))
                big_image = self.overlay_image(big_image, frame_b, (width3-width2, 30))
                self.video_writer2.write(big_image)
        except Exception as e:
            self.video_writer2.release()
            print(f'An error occurred when save video: {e}')
            traceback.print_exc()

    def overlay_image(self, big_image, small_image, position):
        """
        将小图覆盖到大图的指定位置，考虑透明度。

        :param big_image: 大图，numpy数组
        :param small_image: 小图，numpy数组
        :param position: 元组，表示小图左上角在大图上的位置(x, y)
        :return: 覆盖后的大图，numpy数组
        """
        x, y = position
        # 获取小图的尺寸
        small_height, small_width = small_image.shape[:2]

        # 检查小图是否具有透明度通道
        if len(small_image.shape) == 3 and small_image.shape[2] == 4:
            # 分离透明度通道
            alpha_s = small_image[:, :, 3] / 255.0
            alpha_l = 1 - alpha_s

            # 提取小图的RGB通道
            small_image_rgb = small_image[:, :, :3]

            # 提取大图的覆盖区域
            big_image_roi = big_image[y:y + small_height, x:x + small_width]

            # 根据透明度合并图像
            for c in range(3):
                big_image_roi[:, :, c] = (alpha_s * small_image_rgb[:, :, c] +
                                          alpha_l * big_image_roi[:, :, c])

            # 将合并后的区域放回大图
            big_image[y:y + small_height, x:x + small_width] = big_image_roi
        else:
            # 如果小图没有透明度通道，直接覆盖
            big_image[y:y + small_height, x:x + small_width] = small_image
        return big_image

    def onBtnSave(self):
        if self.is_recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        if self.hcam:
            if not self.is_recording:
                self.is_recording = True
                self.btn_save.setChecked(True)
                self.btn_save.setFlat(True)
                self.btn_save.setStyleSheet(self.selected_color)
                today_folder = datetime.now().strftime("%Y-%m-%d")  # 创建当日日期目录
                video_directory_path = os.path.join(BASE_DIR, 'video', today_folder)  # 构建完整存储路径
                os.makedirs(video_directory_path, exist_ok=True)  # 自动创建目录
                dtime = datetime.fromtimestamp(time.time()).strftime('%H%M%S')
                self.out_video_path = os.path.join(video_directory_path, f'{self.exp_id}_{self.order}_{dtime}.mp4')
                self.out_video_path2 = os.path.join(video_directory_path, f'{self.exp_id}_{self.order}_{dtime}_mix.mp4')

                # x264供平台和大模型侧使用，日常使用mp4v格式
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                # fourcc = cv2.VideoWriter_fourcc(*'X264')  # 改为H264格式
                nFrame, nTime, nTotalFrame = self.hcam.get_FrameRate()
                frame_rate = nFrame * 1000.0 / nTime
                resolution = (self.imgWidth, self.imgHeight)
                self.video_writer = cv2.VideoWriter(self.out_video_path, fourcc, frame_rate, resolution)
                self.video_writer2 = cv2.VideoWriter(self.out_video_path2, fourcc, frame_rate, resolution)
                # 开启自动对焦
                self.startAutoFocus()
                self.autoFocusFlag = True

    def stop_recording(self):
        if self.hcam:
            if self.is_recording:
                self.is_recording = False
                self.btn_save.setChecked(False)
                self.btn_save.setFlat(False)
                self.btn_save.setStyleSheet(self.default_color)
                self.video_writer.release()
                self.video_writer2.release()

                # 停止记录后导出温度和流量excel
                self.recordFlag = False
                max_rows = max(self.cacheTempData.shape[0], self.cacheMFCData.shape[0])
                # 填充行数不足的数组
                padded_temp = np.pad(self.cacheTempData, ((0, max_rows - self.cacheTempData.shape[0]), (0, 0)),
                                     mode='constant')
                padded_mfc = np.pad(self.cacheMFCData, ((0, max_rows - self.cacheMFCData.shape[0]), (0, 0)),
                                    mode='constant')
                self.combinedData = np.hstack((padded_temp, padded_mfc))  # 结果形状为 (max_rows, 8)
                self.exportExcel()
                self.cacheTempData = np.empty((0, 5))
                self.cacheMFCData = np.empty((0, 3))
                self.combinedData = None
                # 关闭自动对焦
                self.stopAutoFocus()
                self.autoFocusFlag = False

    def exportExcel(self):
        try:
            timestamps_temp = self.combinedData[:, 0]
            abs_time_temp = [pd.Timestamp(ts, unit='s').strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                        for ts in timestamps_temp]
            rel_time_temp = [round(ts - timestamps_temp[0], 3) for ts in timestamps_temp]

            timestamps_mfc = self.combinedData[:, 5]
            abs_time_mfc = [pd.Timestamp(ts, unit='s').strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                        for ts in timestamps_mfc]
            rel_time_mfc = [round(ts - timestamps_mfc[0], 3) for ts in timestamps_mfc]

            pv_a = self.combinedData[:, 1]
            sv_a = self.combinedData[:, 2]
            pv_b = self.combinedData[:, 3]
            sv_b = self.combinedData[:, 4]
            mfc_pv = self.combinedData[:, 6]
            mfc_sv = self.combinedData[:, 7]
            df = pd.DataFrame({
                "温度绝对时间": abs_time_temp,
                "温度相对时间(s)": rel_time_temp,
                "PV_ZoneA": pv_a,
                "SV_ZoneA": sv_a,
                "PV_ZoneB": pv_b,
                "SV_ZoneB": sv_b,
                "流量绝对时间": abs_time_mfc,
                "流量相对时间(s)": rel_time_mfc,
                "mfc_pv": mfc_pv,
                "mfc_sv": mfc_sv
            })

            # 路径管理（参考网页1的目录结构）
            today = pd.Timestamp.now().strftime("%Y-%m-%d")
            save_dir = os.path.join(BASE_DIR, 'export', today)
            os.makedirs(save_dir, exist_ok=True)

            # 生成文件名
            filename = f"温区流量_{pd.Timestamp.now().strftime('%H%M%S')}.xlsx"
            excel_path = os.path.join(save_dir, filename)

            # 使用openpyxl引擎导出
            with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='双区温度', index=False)

                # 获取工作表对象
                workbook = writer.book
                worksheet = writer.sheets['双区温度']

                # 设置标题格式（参考网页5的样式配置）
                header_font = Font(bold=True, color="FFFFFF")
                header_fill = PatternFill(start_color='4F81BD', end_color='4F81BD', fill_type='solid')
                for cell in worksheet[1]:
                    cell.font = header_font
                    cell.fill = header_fill
                    cell.alignment = Alignment(horizontal='center')

                # 设置列宽（参考网页4的列宽配置）
                worksheet.column_dimensions['A'].width = 25
                worksheet.column_dimensions['B'].width = 15

            print(f"数据已导出至：{excel_path}")
        except Exception as e:
            print(f"导出异常：{str(e)}")
            print(traceback.format_exc())

    @staticmethod
    def eventCallBack(nEvent, self):
        """callbacks come from toupcam.dll/so internal threads, so we use qt signal to post this event to the UI
        thread"""
        self.evtCallback.emit(nEvent)

    def onevtCallback(self, nEvent):
        """this run in the UI thread"""
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

    def updateImage(self):
        image = QImage(self.pData, self.imgWidth, self.imgHeight, QImage.Format_RGB888)
        newimage = image.scaled(self.lbl_video.width(), self.lbl_video.height(), Qt.KeepAspectRatio,
                                Qt.FastTransformation)
        self.lbl_video.setPixmap(QPixmap.fromImage(newimage))
        if self.is_recording:
            try:
                qimage = image.convertToFormat(QImage.Format_RGB888)
                # 获取当前日期和时间
                if self.tempdevData[0] and self.tempdevData[1]:
                    info = (f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} '
                            f'ZoneA: {self.tempdevData[0].pv} °C, ZoneB: {self.tempdevData[1].pv} °C')
                else:
                    info = (f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} '
                            f'ZoneA: Unknown, ZoneB: Unknown')
                qimage = self.add_text_to_image(qimage, info, QPoint(30, 30), 20)
                cv_image = cv2.cvtColor(np.frombuffer(qimage.bits().asstring(qimage.byteCount()),
                                                      dtype=np.uint8).reshape((self.imgHeight, self.imgWidth, 3)),
                                        cv2.COLOR_BGR2RGB)
                self.video_writer.write(cv_image)
                self.saveToVideo(cv_image)
            except Exception as e:
                print(f'An error occurred when save video: {e}')
                self.video_writer.release()

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
            self.hcam.PullImageV3(None, 1, 24, 0, info)  # peek
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
                    dtime = datetime.fromtimestamp(time.time()).strftime('%H%M%S')
                    # out_image_path = os.path.join(image_directory_path, f'{self.exp_id}_{self.order}_{dtime}_{self.count}.jpg')
                    # image.save(f'{out_image_path}')
                    # print(f'save image to {out_image_path}')

                    #新建当日文件夹
                    dtime = datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d")
                    today_folder = datetime.now().strftime("%Y-%m-%d")  # 创建当日日期目录

                    target_dir = os.path.join(image_directory_path, today_folder)  # 构建完整存储路径
                    os.makedirs(target_dir, exist_ok=True)  # 自动创建目录
                    if not self.autoFocusFlag:
                        image.save(os.path.join(target_dir, f'{self.exp_id}_{self.order}_{dtime}_{self.count}.jpg'))
                    mag = int(self.cmb_magnification.currentText())
                    val = int(self.slider_mag.value())
                    self.line_len = mag / 20 * 421 * val / 100
                    text = f'{val}μm'
                    qimage = self.add_text_to_image(image, text,
                                                    QPoint(image.width() - int(self.line_len) - 50, image.height() - 30),
                                                    20)
                    qimage = self.draw_line_with_arrows(qimage, QPoint(image.width() - int(self.line_len) - 50,
                                                                       image.height() - 10),
                                                        QPoint(image.width() - 50, image.height() - 10))

                    # out_image_path2 = os.path.join(image_directory_path, f'{self.exp_id}_{self.order}_{dtime}_{self.count}_mix.jpg')
                    # qimage.save(f'{out_image_path2}')
                    # print(f'save image to {out_image_path2}')
                    if not self.autoFocusFlag :
                        image.save(os.path.join(target_dir, f'{self.exp_id}_{self.order}_{dtime}_{self.count}_mix.jpg'))
                        print(f'save image to {target_dir}')
                    else:
                        image.save(os.path.join(target_dir, 'auto_focus.jpg'))
                    self.target_dir = target_dir

    def add_text_to_image(self, image, text, position, size):
        # 创建一个新的QImage对象，内容是原始图像的副本
        new_image = image.copy()
        # 创建QPainter对象用于在图像上绘制
        painter = QPainter(new_image)
        painter.setPen(QColor(0, 0, 0))  # 设置文字颜色，这里使用白色
        font = QFont("Arial", size)  # 设置字体和大小
        painter.setFont(font)
        # 在指定位置绘制文字
        painter.drawText(position, text)
        # 完成绘制
        painter.end()
        return new_image

    def draw_line_with_arrows(self, image, start_point, end_point):
        # 设置默认的线段颜色、宽度和箭头长度
        default_color = QColor(0, 0, 0)  # 黑色
        default_width = 5  # 线段宽度
        default_arrow_length = 10  # 箭头长度
        # 创建 QPainter 对象
        painter = QPainter(image)
        painter.setPen(QPen(default_color, default_width))  # 设置线段颜色和宽度
        # 创建 QLineF 对象表示线段
        line = QLineF(start_point, end_point)
        # 绘制主线段
        painter.drawLine(line)
        # 计算线段的方向向量
        dx = end_point.x() - start_point.x()
        dy = end_point.y() - start_point.y()
        length = (dx ** 2 + dy ** 2) ** 0.5
        if length == 0:
            return image  # 避免除以零
        ux = -dy / length
        uy = dx / length
        # 计算箭头端点
        arrow1_start = QPoint(end_point.x() + int(ux * default_arrow_length),
                              end_point.y() + int(uy * default_arrow_length))
        arrow1_end = end_point
        arrow2_start = QPoint(end_point.x() - int(ux * default_arrow_length),
                              end_point.y() - int(uy * default_arrow_length))
        arrow2_end = end_point
        # 绘制箭头
        # painter.drawLine(QLineF(arrow1_start, arrow1_end))
        painter.drawLine(QLineF(arrow2_start, arrow2_end))
        # 计算并绘制起始点的小线段
        # painter.drawLine(QLineF(start_point, QPoint(start_point.x() + int(ux * default_arrow_length),
        #                                             start_point.y() + int(uy * default_arrow_length))))
        painter.drawLine(QLineF(start_point, QPoint(start_point.x() - int(ux * default_arrow_length),
                                                    start_point.y() - int(uy * default_arrow_length))))
        # 结束绘制
        painter.end()
        return image

    def cvimage_to_qimage(self, cv_image):
        """将OpenCV的RGBA图像转换为QImage"""
        # 检查图像是否为8位
        if cv_image.dtype != np.uint8:
            raise ValueError("OpenCV图像必须是8位的")
        # 确保图像具有4个通道
        if cv_image.shape[2] != 4:
            raise ValueError("图像必须有4个通道")
        # 将OpenCV图像数据转换为QImage
        q_image = QImage(cv_image.data, cv_image.shape[1], cv_image.shape[0], QImage.Format_RGBA8888)
        return q_image

    def init_focus_ui(self):
        self.BT_focus_connect.clicked.connect(self.onConnectFocus)
        self.BT_focus_up.clicked.connect(self.onFocusUp)
        self.BT_focus_down.clicked.connect(self.onFocusDown)
        self.BT_focus_setZero.clicked.connect(self.onSetZero)
        self.BT_focus_setSpeed.clicked.connect(self.onSetSpeed)
        self.BT_focus_setUpLimit.clicked.connect(self.onSetUpLimit)
        self.BT_focus_setDownLimit.clicked.connect(self.onSetDownLimit)
        self.BT_focus_ems.clicked.connect(self.onFocusEMS)
        ports_list = list(list_ports.comports())
        ports_name = [port.name for port in ports_list]
        self.CBB_focus_port.clear()
        self.CBB_focus_port.addItems(ports_name)

        speed_list = ["0.05μm", "0.1μm", "1μm", "10μm", "100μm", "1000μm", "10000μm"]
        self.CBB_focus_speed.clear()
        self.CBB_focus_speed.addItems(speed_list)

        self.timer_focus_window = QTimer(self)
        self.timer_focus_window.timeout.connect(self.updateFocusData)

    def updateFocusData(self):
        if self.focusData:
            self.lbl_focus_position.setText(f'{self.focusData} μm')

    # ROBOT RELATED
    def init_robot_ui(self):
        self.browser_view = WebEngineView()
        self.VLayout_robot.addWidget(self.browser_view, stretch=1)

        self.create_navigation_bar()
        self.browser_view.load(QUrl("http://192.168.0.10/dist/#/login"))

        self.browser_view.loadFinished.connect(self.on_load_finished)

    def create_navigation_bar(self):
        self.nav_bar = QToolBar()
        self.addToolBar(Qt.TopToolBarArea, self.nav_bar)

        self.back_button = QPushButton("Back")
        self.back_button.clicked.connect(self.browser_view.back)
        self.nav_bar.addWidget(self.back_button)

        self.forward_button = QPushButton("Forward")
        self.forward_button.clicked.connect(self.browser_view.forward)
        self.nav_bar.addWidget(self.forward_button)

        self.url_bar = QLineEdit()
        self.url_bar.returnPressed.connect(self.load_url)
        self.nav_bar.addWidget(self.url_bar)

    def update_url_bar(self, url):
        self.url_bar.setText(url)

    def load_url(self):
        url_text = self.url_bar.text()
        if url_text:
            self.browser_view.setUrl(QUrl(url_text))

    def on_load_finished(self, result):
        # 确保页面加载完成后，按钮状态正确
        if result:
            try:
                js_code = """
                 // 使用类名和类型属性选择器来获取输入框
                 document.querySelector('.el-input__inner[type="text"]').value = 'admin';
                 document.querySelector('.el-input__inner[type="password"]').value = 'admin';
                 var inputEvent = new Event('input', {bubbles: true});
                 document.querySelector('.el-input__inner[type="text"]').dispatchEvent(inputEvent);
                 document.querySelector('.el-input__inner[type="password"]').dispatchEvent(inputEvent);
                 """
                # 在页面中执行JavaScript代码
                self.browser_view.page().runJavaScript(js_code)
                self.browser_view.page().runJavaScript("document.querySelector('.el-button.el-button--primary.el-button--large').click()")
                self.back_button.setEnabled(self.browser_view.history().canGoBack())
                self.forward_button.setEnabled(self.browser_view.history().canGoForward())
            except Exception as e:
                print(e)

    def onSettings(self):
        if self.showSettings == True:
            self.widget_settings.hide()
            self.showSettings = False
            self.BT_settings.setText(">")
        else:
            self.widget_settings.show()
            self.showSettings = True
            self.BT_settings.setText("<")

    def cleanMFC(self):
        # 清洗self.default_clean_time秒
        self.counter = self.default_clean_time
        self.onSwitchClean()
        self.startCounting = True

    def onSendSignal(self):
        if not self.start_sending:
            self.start_send()
        else:
            self.stop_send()

    def start_send(self):
        self.start_sending = True
        self.BT_sendSignal.setChecked(True)
        self.BT_sendSignal.setStyleSheet(self.selected_color)

    def stop_send(self):
        self.start_sending = False
        self.BT_sendSignal.setChecked(False)
        self.BT_sendSignal.setStyleSheet(self.default_color)

    def send_signal(self):
        """ 发送开炉信号 """
        if self.slave:
            self.slave.set_values('0', 0, [121])
            print(f"send signal: {'0', 0, [121]}")

    def send_default_signal(self):
        if self.slave:
            self.slave.set_values('0', 0, [120])
            print(f"send signal: {'0', 0, [120]}")

    def send_rerun_signal(self):
        if self.slave:
            self.slave.set_values('0', 0, [63])
            print(f"send signal: {'0', 0, [63]}")

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
        file_path, _ = QFileDialog.getOpenFileName(self, "Open File", f'{config_directory_path}', "CSV Files (*.csv);;All Files (*)")
        filename, _ = os.path.splitext(os.path.basename(file_path))
        if filename:
            # 这里可以添加代码来处理选中的文件42
            self.dialog = TempProgramTableDialog(self, filename)
            self.dialog.loadTable(filename)
            print(f"Selected file: {filename}")
            if self.dialog.exec_() == QDialog.Accepted:
                print("Dialog was accepted.")

    def closeEvent(self, event):
        print(f'窗口即将关闭')
        if self.rtu_server:
            self.rtu_server.stop()
            self.rtu_server = None
        if self.video_writer2:
            self.video_writer2.release()
            self.video_writer2 = None
        if self.video_writer:
            self.video_writer.release()
            self.video_writer = None
        if self.hcam:
            self.closeCamera()
        if self.api_thread:
            self.api_thread.stop()
            self.api_thread = None
        if self.focus_worker:
            self.focus_worker.stop_run()
            self.focus_worker = None
        super().closeEvent(event)

    def startAutoFocus(self):
        """开始自动对焦"""
        self.auto_focus_worker.start_auto_focus()

    def stopAutoFocus(self):
        """停止自动对焦"""
        self.auto_focus_worker.stop_auto_focus()

    def on_auto_focus_progress(self, message):
        """处理自动对焦进度信息"""
        print(f"自动对焦: {message}")
        start = time.time()
        self.focus_worker.move_up(10)
        end = time.time()
        print('Focus once time: {}.'.format(end-start))
        time.sleep(5)

        # 可以在这里更新UI显示进度

    def on_sharpness_calculated(self, sharpness):
        """处理清晰度计算结果"""
        # print(f"当前清晰度: {sharpness:.2f}")
        # 可以在这里更新UI显示清晰度

    def on_auto_focus_finished(self):
        """自动对焦完成"""
        print("自动对焦完成")
        # 可以在这里更新UI状态

    def main_loop(self):
        # 实验前先清洗MFC设备{self.counter}秒
        if self.IsLaunched:
            if self.startCounting:
                self.counter = self.counter - 1
                print(f'清洗倒计时：{self.counter}')
            if self.counter <= 0:
                self.startCounting = False
                self.counter = self.default_clean_time
                # 清洗完后先关闭所有流量计阀门
                if self.mfc_worker:
                    self.mfc_worker.write_data('switch',
                                               MFCInputData(value=True, id=self.button_group.checkedId(), addr=0))
                # 再启动所有设备
                self.onRunAll()

        # 判断实验是否结束，发送信号
        if self.tempdevData[0]:
            if self.tempdevData[0].step == len(self.program_a[0]) - 1:
                self.is_final_step_a = True
        if self.tempdevData[1]:
            if self.tempdevData[1].step == len(self.program_b[0]) - 1:
                self.is_final_step_b = True
            if self.temp_threshold_low and self.temp_threshold_high:
                if (self.is_final_step_b and self.temp_threshold_low < self.tempdevData[1].pv < self.temp_threshold_high
                        and self.restartFlag is False):
                    self.signal_mode = 1
                    self.IsExpEnd = True
                elif self.restartFlag is True:
                    self.signal_mode = 2
                else:
                    self.signal_mode = 0
        # 如果手动点击发送信号按钮,先停止实验，再强制为模式1，发送开炉信号。
        if self.start_sending:
            self.stop_experiment()
            self.signal_mode = 1
        if self.signal_mode == 1:
            self.send_signal()
        if self.signal_mode == 2:
            self.send_rerun_signal()
        if self.signal_mode == 0:
            self.send_default_signal()

        if self.IsExpEnd and not self.IsResultSaved:
            # 保存结果
            self.out_image_path = self.onBtnSnap2()
            self.onSaveResult()
            self.IsResultSaved = True
            # 停止本轮实验
            self.stop_experiment()

        if self.slave and self.tempdevData[0] and self.tempdevData[1]:
            try:
                plc_signal = self.slave.get_values('1', 0, 10)
            except Exception as e:
                print(f'报错{e}')
            if plc_signal == (1, 0, 0, 0, 1, 1, 1, 1, 0, 0) and self.restartFlag is False:
                print(f'收到PLC信号: 241 ！开启新一轮实验！')
                self.restartFlag = True
                # 在这里解决显微镜图像卡住的bug, 切换分辨率，再切换回来。
                self.cmb_res.setCurrentIndex(2)
            if plc_signal == (0, 0, 0, 0, 1, 1, 1, 1, 0, 0):
                self.restartFlag = False
        if self.IsExpEnd and self.restartFlag:
            self.start_experiment()


class AutoFocusWorker(QObject):
    """自动对焦工作类，使用信号槽机制避免线程阻塞"""
    finished = pyqtSignal()
    progress = pyqtSignal(str)
    sharpness_calculated = pyqtSignal(float)

    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.running = False
        self.current_step = 0
        self.max_steps = 15  # 减少最大步数
        self.best_sharpness = 0
        self.best_position = 0
        self.current_direction = 1
        self.improvement_threshold = 0.01  # 降低阈值
        self.max_no_improvement = 20

        # 使用定时器控制执行节奏
        self.timer = QTimer()
        self.timer.timeout.connect(self.process_step)
        self.timer.setSingleShot(True)

    def calculate_sharpness(self, image_path):
        """计算图片清晰度，增加错误处理"""
        try:
            if not os.path.exists(image_path):
                self.progress.emit(f"图片文件不存在: {image_path}")
                return 0

            # 等待文件完全写入
            time.sleep(1)

            image = cv2.imread(image_path)
            if image is None:
                self.progress.emit(f"无法读取图片: {image_path}")
                return 0

            # 转换为灰度图
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # 应用拉普拉斯算子
            laplacian = cv2.Laplacian(gray, cv2.CV_64F)

            # 计算方差作为清晰度分数
            sharpness = laplacian.var()

            return sharpness

        except Exception as e:
            self.progress.emit(f"计算清晰度时出错: {e}")
            return 0

    def start_auto_focus(self):
        """开始自动对焦"""
        if self.running:
            self.progress.emit("自动对焦已在运行中")
            return

        self.running = True
        self.current_step = 0
        self.best_sharpness = 0
        self.best_position = 0
        self.current_direction = 1

        self.progress.emit("开始自动对焦...")
        self.timer.start(1000)  # 1s后开始第一步

    def stop_auto_focus(self):
        """停止自动对焦"""
        self.running = False
        self.timer.stop()
        self.progress.emit("自动对焦已停止")
        self.finished.emit()

    def process_step(self):
        """处理单步对焦"""
        if not self.running:
            self.stop_auto_focus()
            return

        try:
            # 步骤1：拍摄快照（使用自动对焦专用方法）
            # self.progress.emit(f"步骤 {self.current_step + 1}: 拍摄快照...")

            # 使用自动对焦专用的拍照信号
            self.parent.snap_auto_signal.emit()

            # 等待快照完成后继续
            QTimer.singleShot(1000, self.analyze_snapshot)

        except Exception as e:
            self.progress.emit(f"处理步骤时出错: {e}")
            self.stop_auto_focus()

    def analyze_snapshot(self):
        """分析快照清晰度"""
        try:
            image_dir = os.path.join(self.parent.target_dir, "auto_focus.jpg")

            # 计算清晰度
            sharpness = self.calculate_sharpness(image_dir)
            self.sharpness_calculated.emit(sharpness)
            # self.progress.emit(f"清晰度: {sharpness:.3f}")

            # 分析清晰度变化
            self.analyze_sharpness_change(sharpness)

        except Exception as e:
            self.progress.emit(f"分析快照时出错: {e}")
            self.stop_auto_focus()

    def analyze_sharpness_change(self, sharpness):
        """分析清晰度变化并决定下一步动作"""
        try:
            print(f'当前精度：{sharpness}')
            print(f'最佳精度：{self.best_sharpness}')
            if self.current_step == 0:
                self.best_sharpness = sharpness
                self.best_position = self.current_step
            elif sharpness > self.best_sharpness + self.improvement_threshold:
                self.best_sharpness = sharpness
                self.best_position = self.current_step
                self.progress.emit("清晰度改善")
            elif sharpness < self.best_sharpness - self.improvement_threshold:
                self.current_direction *= -1
                self.progress.emit("清晰度下降，改变方向")

            # 执行对焦调整
            self.adjust_focus()

        except Exception as e:
            self.progress.emit(f"分析清晰度变化时出错: {e}")
            self.stop_auto_focus()

    def adjust_focus(self):
        """调整对焦"""
        try:
            if self.current_direction > 0:
                self.parent.focus_up_signal.emit()
                self.progress.emit("向上调整对焦")
            else:
                self.parent.focus_down_signal.emit()
                self.progress.emit("向下调整对焦")

            self.current_step += 1

            # 等待对焦调整完成后继续下一步
            QTimer.singleShot(2000, self.process_step)  # 增加等待时间

        except Exception as e:
            self.progress.emit(f"调整对焦时出错: {e}")
            self.stop_auto_focus()


if __name__ == '__main__':
    QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    toupcam.Toupcam.GigeEnable(None, None)
    qdarktheme.enable_hi_dpi()
    app = QApplication(sys.argv)
    qss = """
    QLabel {
        border-width: 0px;
    }
    QToolTip { 
        color: black;       /* 文字颜色为深灰色 */
        background-color: #F0F0F0; /* 背景颜色为浅灰色 */
    }
    """
    qdarktheme.setup_theme("dark", additional_qss=qss)
    mw = AICVD()
    mw.show()
    sys.exit(app.exec_())


