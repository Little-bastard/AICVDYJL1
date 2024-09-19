import serial

ser = serial.Serial(port="COM12", baudrate=9600, timeout=1)

try:
    # 读取串口输入信息并输出。
    while True:
        buffer = bytearray(8)
        com_input = ser.readinto(buffer)
        if com_input:  # 如果读取结果非空，则输出
            print(buffer)
            print(buffer[0])
            print(buffer[1])
        else:
            print(f'Got Null')
finally:
    ser.close()