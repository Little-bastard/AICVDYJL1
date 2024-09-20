import serial

ser = serial.Serial(port="COM4", baudrate=9600)  # 打开 COM4，将波特率配置为9600，其余参数使用默认值
if ser.is_open:  # 判断串口是否成功打开
    print("打开串口成功。")
else:
    print("打开串口失败。")

ser.close()
if ser.is_open:  # 判断串口是否关闭
    print("串口未关闭。")
else:
    print("串口已关闭。")