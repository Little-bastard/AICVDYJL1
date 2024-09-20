import time
import serial
import modbus_tk
import modbus_tk.defines as cst
from modbus_tk import modbus_rtu
import struct
PORT='COM1' #linux下的串口地址
BAUDRATE=9600 #波特率
BYTESIZE=8 #比特位
PARITY='N' #校验位
STOPBITS=1 #停止位/dev/ttyS0
#连接串口
serial_serial=serial.Serial(port=PORT, baudrate=BAUDRATE, bytesize=BYTESIZE, parity=PARITY, stopbits=STOPBITS)
#建立客户端通讯
rtu_server=modbus_rtu.RtuServer(serial_serial)
rtu_server.start()
#建立总站
slave_1=rtu_server.add_slave(3)
# slave_1.add_block('0',cst.HOLDING_REGISTERS,0,1200)
slave_1.add_block('1',cst.COILS,0,10)
#block_name='0',block_type=cst.HOLDING_REGISTERS,starting_address=0,size=1200
registers_list=[5,2,3,4,5,6]
# slave_1.set_values('0',0,registers_list)
res=slave_1.get_values('1', 0, 10)
print(f'5555')
print(f'{res}')
#将数据存入寄存器,block_name='0',address=0,values=registers_list