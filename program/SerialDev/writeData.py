import time

import serial

ser = serial.Serial(port="COM5", baudrate=9600)


# 串口发送数据，并输出发送的字节数。
try:
    while True:
        data_to_send = bytearray(8)
        data_to_send[0] = 129
        data_to_send[1] = 129
        data_to_send[2] = 82
        data_to_send[3] = 74
        data_to_send[4] = 10
        data_to_send[5] = 10
        data_to_send[6] = 83
        data_to_send[7] = 1
        # data = '81 81 52 01 00 00 53 01'
        print(f'准备发送{data_to_send}')
        write_len = ser.write(data_to_send)
        time.sleep(0.05)
        print(f'发送成功')
        print("串口发出{}个字节。".format(write_len))
finally:
    ser.close()