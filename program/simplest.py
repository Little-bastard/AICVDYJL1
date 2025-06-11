# 基于Python的 Touptek 显微镜摄像头（Toupcam）应用程序

from program.MicroscopeDev import toupcam


class App:
    def __init__(self):
        self.hcam = None   # 存储打开的摄像头设备句柄
        self.buf = None    # 用于存储从摄像头拉取的图像数据
        self.total = 0     # 记录成功拉取的图像数量

# the vast majority of callbacks come from toupcam.dll/so/dylib internal threads

    # 静态方法作为摄像头事件的回调入口
    # 如果事件类型为 TOUPCAM_EVENT_IMAGE（表示新图像可用），调用实例方法 CameraCallback。
    # ctx 是传递的上下文对象（即 App 实例本身）。
    @staticmethod
    def cameraCallback(nEvent, ctx):
        if nEvent == toupcam.TOUPCAM_EVENT_IMAGE:
            ctx.CameraCallback(nEvent)

    # 处理摄像头事件，尤其是图像数据
    # 当检测到 TOUPCAM_EVENT_IMAGE 事件时
    # 使用 PullImageV3 方法将图像数据填充到 self.buf 中
    # 增加计数并打印成功信息
    # 捕获可能的异常（如设备断开或资源不足）
    # 对于其他事件类型（如设备断开），仅打印事件码
    def CameraCallback(self, nEvent):
        if nEvent == toupcam.TOUPCAM_EVENT_IMAGE:
            try:
                self.hcam.PullImageV3(self.buf, 0, 24, 0, None)
                self.total += 1
                print('pull image ok, total = {}'.format(self.total))
            except toupcam.HRESULTException as ex:
                print('pull image failed, hr=0x{:x}'.format(ex.hr & 0xffffffff))
        else:
            print('event callback: {}'.format(nEvent))

    # 调用EnumV2枚举所有连接的摄像头设备
    # 打印第一个摄像头的详细信息（名称、功能标志、支持的分辨率）
    # 打开第一个摄像头设备。
    # 获取图像尺寸并计算缓冲区大小（24bpp RGB 格式）
    # 启动摄像头的拉取模式，并注册 cameraCallback 作为回调
    # 阻塞等待用户输入以退出程序
    def run(self):
        a = toupcam.Toupcam.EnumV2()
        if len(a) > 0:
            print('{}: flag = {:#x}, preview = {}, still = {}'.format(a[0].displayname, a[0].model.flag, a[0].model.preview, a[0].model.still))
            for r in a[0].model.res:
                print('\t = [{} x {}]'.format(r.width, r.height))
            self.hcam = toupcam.Toupcam.Open(a[0].id)
            if self.hcam:
                try:
                    width, height = self.hcam.get_Size()
                    bufsize = toupcam.TDIBWIDTHBYTES(width * 24) * height
                    print('image size: {} x {}, bufsize = {}'.format(width, height, bufsize))
                    self.buf = bytes(bufsize)
                    if self.buf:
                        try:
                            self.hcam.StartPullModeWithCallback(self.cameraCallback, self)
                        except toupcam.HRESULTException as ex:
                            print('failed to start camera, hr=0x{:x}'.format(ex.hr & 0xffffffff))
                    input('press ENTER to exit')
                finally:
                    self.hcam.Close()
                    self.hcam = None
                    self.buf = None
            else:
                print('failed to open camera')
        else:
            print('no camera found')

if __name__ == '__main__':
    app = App()
    app.run()