import time

from CPS import CPSClient
cps = CPSClient()
result = []
IP = '192.168.0.10'
port = 10003

#连接机器人（测试成功）
ret = cps.HRIF_Connect(0, IP, port)
print(ret)

#判断是否连接（测试成功）
ret1=cps.HRIF_IsConnected(0)
print(ret1)
time.sleep(2)

# 关机（测试成功）
# ret3 = cps.HRIF_ShutdownRobot(0)
# print(ret3)

#连接控制箱（测试失败）
# ret4 = cps.HRIF_Connect2Box(0)
# print(ret4)

# #上电（测试失败）
# ret5 = cps.HRIF_Electrify(0)
# print(ret5)

#断电（无此函数）
# ret6= cps.HRIF_Blackout(0)
# print(ret6)

#连接控制器（测试成功）
# ret7 = cps.HRIF_Connect2Controller(0)
# print(ret)

#判断是否是仿真机器人（测试失败）
# nSimulateRobot = 1
# nRet = cps.HRIF_IsSimulateRobot(0, nSimulateRobot)
# print(nRet)

# 判断控制器是否启动（测试成功）
# result = []
# nRet = cps.HRIF_IsControllerStarted(0, result)
# print(nRet)
# print(result)

#读版本号(测试成功)
# result = []
# nRet = cps.HRIF_ReadVersion(0,0, result)
# print(nRet)
# print(result)

#读机器人类型(测试成功)
# result =[]
# nRet = cps.HRIF_ReadRobotModel (0,0, result)
# print(nRet)
# print(result)

#使能（测试成功）
# nRet = cps.HRIF_GrpEnable(0, 0)
# print(nRet)

#去使能(测试成功)
# nRet = cps.HRIF_GrpDisable(0,0)
# print(nRet)

#复位（测试成功，函数调用成功，具体复位情况没测）
# nRet = cps.HRIF_GrpReset(0,0)
# print(nRet)

#停止运动(测试成功,对应的是结束按钮)
# nRet = cps.HRIF_GrpStop(0,0)
# print(nRet)
# time.sleep(2)

#暂停运动（无此函数）
# nRet = cps.HRIF_Grpinterrupt(0,0)
# print(nRet)

#继续运动（测试失败，返回39500）
# nRet = cps.HRIF_GrpContinue(0,0)
# print(nRet)

#打开自由驱动(测试成功)
# nRet = cps.HRIF_GrpOpenFreeDriver(0,0)
# print(nRet)

#关闭自由驱动(测试成功)
# nRet = cps.HRIF_GrpCloseFreeDriver(0,0)
# print(nRet)

#调用脚本函数
# nRet = cps.HRIF_StartScript(0)
# print(nRet)

strFuncName = 'Func_1'
param = []

resul = []
nRet = cps.HRIF_RunFunc(0, strFuncName, param, resul)
print(resul)
print(nRet)

