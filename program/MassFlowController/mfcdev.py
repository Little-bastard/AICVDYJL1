import struct
import sys
import time

import serial

# factor = 500/4095

class MFCComm:
    def __init__(self, portName, baudRate=9600, dataBits=serial.EIGHTBITS, parity=serial.PARITY_NONE,
                 stopBits=serial.STOPBITS_TWO):
        self.MyCom = serial.Serial(port=portName, baudrate=baudRate, bytesize=dataBits, parity=parity,
                                   stopbits=stopBits, timeout=0.15)
        self.fss = [self.read_fs(i) for i in range(16)]
        print(f'fss: {self.fss}')
        self.factors = [fs / 4095 if fs else None for fs in self.fss]
        print(f'factors: {self.factors}')

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

    def read_pv(self, id):
        """
        01 03 00 10 00 01 85 CF
        """
        if self.MyCom is None:
            return None
        if self.factors[id] is None:
            return None
        data = bytearray(8)
        data[0] = id
        data[1] = 3
        data[2] = 0
        data[3] = 16
        data[4] = 0
        data[5] = 1
        data[6], data[7] = self.calc_crc16(data[:6])
        write_len = self.MyCom.write(data)
        time.sleep(0.05)
        buffer = bytearray(7)
        self.MyCom.readinto(buffer)
        if self.CheckResult(buffer):
            print(f'({buffer[3]} * 256 + {buffer[4]})*{self.factors[id]}={round((buffer[3] * 256 + buffer[4]) * self.factors[id], 1)}')
            return round((buffer[3] * 256 + buffer[4]) * self.factors[id], 1)
        return None

    def write_sv(self, value, id):
        """
        01 06 00 11 02 00 D8 AF
        """
        if self.MyCom is None:
            return None
        if self.factors[id]:
            value = int(value / self.factors[id])
        else:
            return None
        data = bytearray(8)
        data[0] = id
        data[1] = 6
        data[2] = 0
        data[3] = 17
        # 让b[0]始终为最低字节，对32位系统，int类型的value有四个字节,
        # 按下面的方法可将b[0],b[1],b[2],b[3]对应value的最低字节，次低字节，次高字节，最高字节
        if sys.byteorder == 'little':
            b = struct.pack('<i', value)
        else:
            b = struct.pack('>i', value)
        data[4] = b[1]
        data[5] = b[0]
        data[6], data[7] = self.calc_crc16(data[:6])
        write_len = self.MyCom.write(data)
        time.sleep(0.05)
        buffer = bytearray(8)
        self.MyCom.readinto(buffer)
        if self.CheckResult(buffer):
            return (buffer[4] * 256 + buffer[5]) * self.factors[id]
        return None

    def read_sv(self, id):
        if self.MyCom is None:
            return None
        if self.factors[id] is None:
            return None
        data = bytearray(8)
        data[0] = id
        data[1] = 3
        data[2] = 0
        data[3] = 17
        data[4] = 0
        data[5] = 1
        data[6], data[7] = self.calc_crc16(data[:6])
        write_len = self.MyCom.write(data)
        time.sleep(0.05)
        buffer = bytearray(7)
        self.MyCom.readinto(buffer)
        if self.CheckResult(buffer):
            return round((buffer[3] * 256 + buffer[4]) * self.factors[id], 1)
        return None

    def read_id(self, id):
        if self.MyCom is None:
            return None
        data = bytearray(8)
        data[0] = id
        data[1] = 3
        data[2] = 0
        data[3] = 51
        data[4] = 0
        data[5] = 1
        data[6], data[7] = self.calc_crc16(data[:6])
        write_len = self.MyCom.write(data)
        time.sleep(0.05)
        buffer = bytearray(7)
        self.MyCom.readinto(buffer)
        if self.CheckResult(buffer):
            return buffer[3] * 256 + buffer[4]
        return None

    def read_switch_single(self, id, addr):
        if self.MyCom is None:
            return None
        data = bytearray(8)
        data[0] = id
        data[1] = 1
        data[2] = 0
        data[3] = addr
        data[4] = 0
        data[5] = 1
        data[6], data[7] = self.calc_crc16(data[:6])
        write_len = self.MyCom.write(data)
        time.sleep(0.05)
        buffer = bytearray(6)
        self.MyCom.readinto(buffer)
        if self.CheckResult(buffer):
            return buffer[3]
        return None

    def read_switch_vctrl(self, id):
        if self.MyCom is None:
            return None
        data = bytearray(8)
        data[0] = id
        data[1] = 1
        data[2] = 0
        data[3] = 0
        data[4] = 0
        data[5] = 3
        data[6], data[7] = self.calc_crc16(data[:6])
        write_len = self.MyCom.write(data)
        time.sleep(0.05)
        buffer = bytearray(6)
        self.MyCom.readinto(buffer)
        if self.CheckResult(buffer):
            return buffer[3]
        return None

    def read_all_state(self, id):
        if self.MyCom is None:
            return None
        data = bytearray(8)
        data[0] = id
        data[1] = 1
        data[2] = 0
        data[3] = 0
        data[4] = 0
        data[5] = 8
        data[6], data[7] = self.calc_crc16(data[:6])
        write_len = self.MyCom.write(data)
        time.sleep(0.05)
        buffer = bytearray(6)
        self.MyCom.readinto(buffer)
        if self.CheckResult(buffer):
            print(f'all switch state: {buffer[3]}')
            return buffer[3]
        return None

    def write_switch(self, value: bool, id, addr):
        if self.MyCom is None:
            return None
        data = bytearray(8)
        data[0] = id
        data[1] = 5
        data[2] = 0
        data[3] = addr
        if value:
            b = 255
        else:
            b = 0
        data[4] = b
        data[5] = 0
        data[6], data[7] = self.calc_crc16(data[:6])
        write_len = self.MyCom.write(data)
        time.sleep(0.05)
        buffer = bytearray(8)
        self.MyCom.readinto(buffer)
        if self.CheckResult(buffer):
            return buffer[4] * 256 + buffer[5]
        return None

    def read_unit(self, id):
        if self.MyCom is None:
            return None
        data = bytearray(8)
        data[0] = id
        data[1] = 1
        data[2] = 0
        data[3] = 6
        data[4] = 0
        data[5] = 1
        data[6], data[7] = self.calc_crc16(data[:6])
        write_len = self.MyCom.write(data)
        time.sleep(0.05)
        buffer = bytearray(6)
        self.MyCom.readinto(buffer)
        if self.CheckResult(buffer):
            if buffer[3] == 0:
                return 'mL/min'
            else:
                return 'L/min'
        return None

    def read_fs(self, id):
        if self.MyCom is None:
            return None
        data = bytearray(8)
        data[0] = id
        data[1] = 3
        data[2] = 0
        data[3] = 48
        data[4] = 0
        data[5] = 1
        data[6], data[7] = self.calc_crc16(data[:6])
        write_len = self.MyCom.write(data)
        time.sleep(0.05)
        buffer = bytearray(7)
        self.MyCom.readinto(buffer)
        if self.CheckResult(buffer):
            return round((buffer[3] * 256 + buffer[4]), 1)
        return None

    def calc_crc16(self, data):
        crc = 0xFFFF
        for pos in data:
            crc ^= pos
            for i in range(8):
                if (crc & 1) != 0:
                    crc >>= 1
                    crc ^= 0xA001
                else:
                    crc >>= 1
        a = crc & 0xff
        b = crc >> 8
        return [a, b]

    def CheckResult(self, result):
        if result is not None and len(result) > 5:
            b = self.calc_crc16(result[:-2])
            return b[0] == result[-2] and b[1] == result[-1]
        return False

if __name__ == "__main__":
    mfc = MFCComm(portName="COM3", baudRate=9600, dataBits=serial.EIGHTBITS, parity=serial.PARITY_NONE, stopBits=serial.STOPBITS_TWO)
    # for i in range(16):
    #     fs = mfc.read_fs(i)
    #     print(fs)
    #
    #     pv = mfc.read_pv(i)
    #     sv = mfc.read_sv(i)
    #     print(f"pv: {pv}, sv: {sv}")

    # id = mfc.read_id(0)
    # switch_states = mfc.read_all_state(2)
    # switch_state = []
    # for i in range(8):
    #     switch_state.append(mfc.read_switch_single(2, i))
    # print(f'pv={pv}, sv={sv},id={id}')
    # print(f'states={switch_states}')
    # print(f'state={switch_state}')
    # sv_w = mfc.write_sv(20, 2)
    # print(f'sv_w: {sv_w}')
    pv = mfc.read_pv(2)
    print(f'pv: {pv}')