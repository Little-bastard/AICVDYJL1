import logging
import math
import struct
import sys
import time

import serial


class AIBUSParam:
    def __init__(self, portName, baudRate=9600, dataBits=serial.EIGHTBITS, parity=serial.PARITY_NONE, stopBits=serial.STOPBITS_ONE):
        self.ActualValue = None
        self.SetValue = None
        self.ParamValue = None
        self.HiAL = False
        self.LoAL = False
        self.dHAL = False
        self.dLAL = False
        self.orAL = False
        self.MyCom = serial.Serial(port=portName, baudrate=baudRate, bytesize=dataBits, parity=parity,
                                   stopbits=stopBits, timeout=0.15)

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
        time.sleep(0.08)
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
            self.ActualValue = round((result[1] * 256 + result[0]) / 10, 1)
            self.SetValue = round((result[3] * 256 + result[2]) / 10, 1)
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
            if a == 74 or a == 75 or a == 47:
                self.ParamValue = round((result[7] * 256 + result[6]) / 10, 1)
            elif a == 76:
                self.ParamValue = result[4]
            else:
                self.ParamValue = result[7]*256+result[6]
            return self.ParamValue
        except Exception:
            return

    def GetBitFromByte(self, result, offset):
        if 0 <= offset <= 7:
            a = math.pow(2, offset)
            return result & int(a) != 0
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
        if 80 <= iParamNo <= 179:
            Value = int(Value * 10)
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
    aibusParam = AIBUSParam(portName="COM5", baudRate=9600, dataBits=serial.EIGHTBITS, parity=serial.PARITY_NONE, stopBits=serial.STOPBITS_ONE)
    aibusParam.ReadParam(27, 2)

    aibusParam.SetParam(80, 25, 2)
    aibusParam.SetParam(81, 1, 2)
    aibusParam.SetParam(82, 40, 2)
    aibusParam.SetParam(83, 2, 2)
    aibusParam.SetParam(84, 30, 2)
    aibusParam.SetParam(85, 1, 2)
    aibusParam.SetParam(86, 25, 2)
    aibusParam.SetParam(87, -121, 2)



