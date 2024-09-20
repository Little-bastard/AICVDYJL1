import logging
import math
import struct
import sys
import time

import serial


class AlBUSParam:
    def __init__(self, portName, baudRate, dataBits, parity, stopBits):
        self.ActualValue = 0.0
        self.SetValue = 0.0
        self.ParamValue = 0.0
        self.HiAL = False
        self.LoAL = False
        self.dHAL = False
        self.dLAL = False
        self.orAL = False

        self.MyCom = serial.Serial(port=portName, baudrate=baudRate, bytesize=dataBits, parity=parity,
                                   stopbits=stopBits, timeout=0.5)

    def IsConnect(self):

        if self.MyCom.isOpen():  # 判断串口是否成功打开
            print("打开串口成功。")
            print(self.MyCom.name)  # 输出串口号
        else:
            print("打开串口失败。")

    def DisConnect(self):
        if self.MyCom.is_open:
            self.MyCom.close()
        if self.MyCom.is_open:  # 判断串口是否关闭
            print("串口未关闭。")
        else:
            print("串口已关闭。")

    def ReadParam(self, iParamNo, iDevAdd):
        if self.MyCom == None:
            return None
        data = bytearray(8)
        data[0] = 128 + iDevAdd
        data[1] = 128 + iDevAdd
        data[2] = 82
        data[3] = iParamNo
        data[4] = 0
        data[5] = 0
        data[6], data[7] = self.GetReadParity(iParamNo, iDevAdd)

        write_len = self.MyCom.write(data)
        time.sleep(0.05)
        buffer = bytearray(10)
        self.MyCom.readinto(buffer)

        if self.CheckResult(buffer, iDevAdd):
            return self.AnalyseParam(buffer, iParamNo)

        return None

    def CheckResult(self, result, devld):
        if result != None and len(result) == 10:
            res = 0
            for i in range(0, 4):
                res += result[2 * i] + result[2 * i + 1] * 256
            res += devld
            if sys.byteorder == 'little':
                b = struct.pack('<i', res)
            else:
                b = struct.pack('>i', res)
            return b[0] == result[8] and b[1] == result[9]
        return False

    def AnalyseParam(self, result, a):
        try:
            self.ActualValue = result[1] * 256 + result[0]
            self.SetValue = result[3] * 256 + result[2]
            self.HiAL = self.GetBitFromByte(result[5], 0)
            if self.HiAL:
                print(f'上限报警')
            self.LoAL = self.GetBitFromByte(result[5], 1)
            if self.LoAL:
                print(f'下限报警')
            self.dHAL = self.GetBitFromByte(result[5], 2)
            if self.dHAL:
                print(f'正偏差报警')
            self.dLAL = self.GetBitFromByte(result[5], 3)
            if self.dLAL:
                print(f'负偏差报警')
            self.orAL = self.GetBitFromByte(result[5], 4)
            # if self.orAl:
            #     print(f'超量程报警')
            self.ParamValue = result[7] * 256 + result[6]
            if a == 76:
                self.ParamValue = result[4]
            return
        except Exception:
            return

    def GetBitFromByte(self, result, offset):
        if 0 <= offset <= 7:
            return result & math.pow(2, offset) != 0
        else:
            print(f'位索引必须位于0-7')
            raise Exception("位索引必须位于0-7")

    def GetReadParity(self, iParamNo, iDevAdd):
        Res = iParamNo * 256 + 82 + iDevAdd
        sum = [Res % 256, Res // 256]
        return sum

    def GetWriteParity(self, iParamNo, Value, iDevAdd):
        Res = iParamNo * 256 + 67 + Value + iDevAdd
        sum = [Res % 256, Res // 256]
        return sum

    def SetParam(self, iParamNo, Value, iDevAdd):
        if self.MyCom == None:
            return None
        data = bytearray(8)
        data[0] = 128 + iDevAdd
        data[1] = 128 + iDevAdd
        data[2] = 67
        data[3] = iParamNo
        if sys.byteorder == 'little':
            b = struct.pack('<i', Value)
        else:
            b = struct.pack('>i', Value)
        data[4] = b[0]
        data[5] = b[1]
        data[6], data[7] = self.GetWriteParity(iParamNo, Value, iDevAdd)
        self.MyCom.write(data)
        time.sleep(0.05)
        buffer = bytearray(10)
        self.MyCom.readinto(buffer)

        if self.CheckResult(buffer, iDevAdd):
            return self.AnalyseParam(buffer, iParamNo)
        else:
            return None

if __name__ == "__main__":
    albusParam = AlBUSParam(portName="COM5", baudRate=9600, dataBits=serial.EIGHTBITS, parity=serial.PARITY_NONE, stopBits=serial.STOPBITS_ONE)
    # albusParam.ReadParam(75, 1)
    # print(f'ActualValue={albusParam.ActualValue}')
    # print(f'HiAL={albusParam.HiAL}')
    # print(f'LoAL={albusParam.LoAL}')
    # print(f'ParamValue={albusParam.ParamValue}')
    # print(f'SetValue={albusParam.SetValue}')
    # print(f'dHAL={albusParam.dHAL}')
    # print(f'orAl={albusParam.orAL}')

    albusParam.SetParam(80,250,2)
    albusParam.SetParam(81, 1, 2)
    albusParam.SetParam(82, 400, 2)
    albusParam.SetParam(83, 2, 2)
    albusParam.SetParam(84, 300, 2)
    albusParam.SetParam(85, 1, 2)
    albusParam.SetParam(86,250,2)
    albusParam.SetParam(27, 0, 2)
    print(f'ActualValue={albusParam.ActualValue}')
    print(f'HiAL={albusParam.HiAL}')
    print(f'LoAL={albusParam.LoAL}')
    print(f'ParamValue={albusParam.ParamValue}')
    print(f'SetValue={albusParam.SetValue}')
    print(f'dHAL={albusParam.dHAL}')
    print(f'orAl={albusParam.orAL}')

