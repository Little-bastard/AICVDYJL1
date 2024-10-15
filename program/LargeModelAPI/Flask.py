from flask import Flask, jsonify, request
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtCore import pyqtSignal, QThread
import sys

app = Flask(__name__)


class FlaskThread(QThread):
    start_experiment_signal = pyqtSignal()
    stop_experiment_signal = pyqtSignal()
    set_parameters_signal = pyqtSignal()

    def run(self):
        @app.route('/start_experiment', methods=['POST'])
        def start_experiment_api():
            # 发送信号
            self.start_experiment_signal.emit()
            return jsonify({"message": "实验已启动"}), 200

        @app.route('/stop_experiment', methods=['POST'])
        def stop_experiment_api():
            self.stop_experiment_signal.emit()
            return jsonify({"message": "实验已停止"}), 200

        @app.route('/set_parameters', methods=['POST'])
        def set_params_api():
            data = request.json
            print(f'Received data:', data)
            self.set_parameters_signal.emit()
            return jsonify({"message": "参数已设定"}), 200
        app.run(debug=True, port=5000, use_reloader=False)

    def stop(self):
        # Flask 没有提供直接停止服务的方法，这里可以调用 Werkzeug 的 shutdown 方法
        try:
            func = request.environ.get('werkzeug.server.shutdown')
            if func:
                func()
        except Exception as e:
            print(f'error: {e}')
        print(f'stop web server')


if __name__ == '__main__':
    # 运行PyQt应用
    app_qt = QApplication(sys.argv)
    main_window = QMainWindow()
    main_window.show()

    # 在另一个线程中运行Flask应用
    flask_thread = FlaskThread()
    flask_thread.start()

    sys.exit(app_qt.exec_())