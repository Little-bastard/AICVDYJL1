import time

import serial


class PLCSignal:
    def __init__(self, port, baudrate=9600, dataBits=serial.EIGHTBITS, parity=serial.PARITY_NONE,
                 stopBits=serial.STOPBITS_ONE):
        self.MyCom = serial.Serial(port=port, baudrate=baudrate, bytesize=dataBits, parity=parity,
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

    def write_signal(self, value):
        print(f'send signal')
        try:
            data= bytearray(5)
            data[0] = 11
            data[1] = 3
            data[2] = value
            data[3], data[4] = self.calc_crc16(data[:3])
            write_len = self.MyCom.write(data)
            time.sleep(0.05)
            buffer = bytearray(5)
            self.MyCom.readinto(buffer)
            if self.CheckResult(buffer):
                return buffer[2]
            return None
        except Exception as e:
            print(e)

    def read_signal(self):
        if self.MyCom is None:
            return None
        buffer = bytearray(5)
        self.MyCom.readinto(buffer)
        if self.CheckResult(buffer):
            return buffer[2]
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
        if result is not None and len(result) == 5:
            b = self.calc_crc16(result[:-2])
            return b[0] == result[-2] and b[1] == result[-1]
        return False