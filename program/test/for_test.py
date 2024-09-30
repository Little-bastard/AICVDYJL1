import sys
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QApplication, QMainWindow
from flask import Flask, request, jsonify

app = Flask(__name__)

class RestApiThread(QThread):
    # 创建一个信号，用于通知主线程
    trigger_experiment = pyqtSignal(str)

    def run(self):
        @app.route('/start_experiment', methods=['POST'])
        def start_experiment():
            data = request.json
            print("Received data:", data)
            # 触发主线程的槽函数
            self.trigger_experiment.emit(data['command'])
            return jsonify({"status": "success"}), 200

        # 在线程中启动 Flask 服务
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

    def stop(self):
        # Flask 没有提供直接停止服务的方法，这里可以调用 Werkzeug 的 shutdown 方法
        func = request.environ.get('werkzeug.server.shutdown')
        if func:
            func()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.api_thread = RestApiThread()
        self.api_thread.trigger_experiment.connect(self.handle_experiment)
        self.api_thread.start()

    def handle_experiment(self, command):
        print(f"Triggering experiment with command: {command}")
        # 这里可以添加启动实验的代码

    def closeEvent(self, event):
        # 重写 closeEvent 以确保在关闭窗口时停止 Flask 服务
        self.api_thread.stop()
        self.api_thread.wait()
        super().closeEvent(event)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())