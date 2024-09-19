# 方式1：调用函数接口打开串口时传入配置参数
import serial

ser = serial.Serial(port="COM5",
                    baudrate=9600,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_TWO,
                    timeout=0.5)
if ser.is_open:  # 判断串口是否成功打开
    print("打开串口成功。")
    print(ser.name)  # 输出串口号
else:
    print("打开串口失败。")