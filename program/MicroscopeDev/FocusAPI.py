import time
from ctypes import WinDLL, create_string_buffer
import os
import sys

directory = os.path.dirname(os.path.realpath(__file__))
path = os.path.join(directory, "PriorScientificSDK.dll")

if os.path.exists(path):
    SDKPrior = WinDLL(path)
else:
    raise RuntimeError("DLL could not be loaded.")

rx = create_string_buffer(1000)
realhw = True


class FocusAPI:
    def __init__(self, portNumber):
        ret = SDKPrior.PriorScientificSDK_Initialise()
        if ret:
            print(f"Error initialising {ret}")
            sys.exit()
        else:
            print(f"Ok initialising {ret}")

        ret = SDKPrior.PriorScientificSDK_Version(rx)
        print(f"dll version api ret={ret}, version={rx.value.decode()}")

        self.sessionID = SDKPrior.PriorScientificSDK_OpenNewSession()
        if self.sessionID < 0:
            print(f"Error getting sessionID {ret}")
        else:
            print(f"SessionID = {self.sessionID}")
        self.connect_focus(portNumber)

    def cmd(self, msg):
        # print(msg)
        ret = SDKPrior.PriorScientificSDK_cmd(
            self.sessionID, create_string_buffer(msg.encode()), rx
        )
        return ret, rx.value.decode()

    def connect_focus(self, portName):
        """连接focus控制器"""
        self.cmd(f"controller.connect {portName}")

    def get_focus_status(self):
        """获取Z轴移动状态， busy or idle"""
        ret, res = self.cmd(f'controller.z.busy.get')
        if ret:
            print(f"Api error 获取Z轴移动状态 {ret}")
        else:
            return res

    def disconnect(self):
        """断开通信"""
        self.cmd(f"controller.disconnect")

    def get_cur_position(self):
        """获取当前的Z轴坐标位置"""
        ret, res = self.cmd("controller.z.position.get")
        if ret:
            print(f"Api error 获取当前的Z轴坐标位置 {ret}")
            return None
        else:
            return f"{float(res) / 20: .2f}"

    def set_position(self, position):
        """设置当前位置，若设置为0可将当前位置定义为零位"""
        res = self.get_focus_status()
        if res == "0":
            self.cmd(f"controller.z.position.set {position}")

    def move_relative(self, relative_position):
        """控制Z轴做相对位移"""
        self.cmd(f"controller.z.move-relative {relative_position}")

    def move_to(self, absolute_position):
        """若设置好零位后，绝对位置移动"""
        self.cmd(f'controller.z.goto-position {absolute_position}')

    def move_at_velocity(self, velocity):
        """Z轴连续移动平均速度设置，velocity单位为microns/s, 即微米/秒"""
        self.cmd(f'controller.z.move-at-velocity {velocity}')

    def get_cur_speed(self):
        """获取速度"""
        ret, res = self.cmd(f'controller.z.speed.get')
        if ret:
            print(f"Api error 获取速度 {ret}")
            return None
        else:
            return res

    def set_max_speed(self, max_velocity):
        """Z轴移动最大速度设置，velocity单位为microns/s，即微米/秒"""
        self.cmd(f'controller.z.speed.set {max_velocity}')

    def get_limits(self):
        """获取上下限位值"""
        res = self.cmd(f'controller.z.limits.get')
        return res


    def set_low_limit(self):
        """下限位设置，断电重启后失效，需重新设置"""
        self.cmd(f'controller.z.swlimits.low.set')

    def set_high_limit(self):
        """上限位设置，断电重启后失效，需重新设置"""
        self.cmd(f'controller.z.swlimits.high.set')

    def stop_abruptly(self):
        """急停"""
        self.cmd(f'controller.stop.abruptly')


if __name__ == "__main__":
    focus = FocusAPI("11")
    focus.set_max_speed(20000)



