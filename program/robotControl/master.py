import serial
import modbus_tk
import modbus_tk.defines as cst
from modbus_tk import modbus_rtu
PORT = 'COM9'  # linux 下的串口地址
BAUDRATE = 9600  # 波特率
BYTESIZE = 8  # 比特位
PARITY = 'N'  # 校验位
STOPBITS = 1  # 停止位
# 连接串口
serial_serial = serial.Serial(port=PORT, baudrate=BAUDRATE, bytesize=BYTESIZE,
parity=PARITY, stopbits=STOPBITS)
# 建立客户端通讯
master = modbus_rtu.RtuMaster(serial_serial)
# 超时
master.set_timeout(3.0)
# 发送指令
''' READ_COILS H01 读线圈
READ_DISCRETE_INPUTS H02 读离散输入
READ_HOLDING_REGISTERS H03 读寄存器
READ_INPUT_REGISTERS H04 读输入寄存器 D
WRITE_SINGLE_COIL H05 写单一线圈
WRITE_SINGLE_REGISTER H06 写单一寄存器
WRITE_MULTIPLE_COILS H15 写多个线圈
WRITE_MULTIPLE_REGISTERS H16 写多寄存器
'''
# 读取 ： 1 从站 ID，指令，起始地址，长度
result = master.execute(1, cst.READ_HOLDING_REGISTERS, 0, 16)
print(result)
