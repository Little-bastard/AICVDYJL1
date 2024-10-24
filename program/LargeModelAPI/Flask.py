import json
import os

import pandas as pd
from flask import Flask, jsonify, request, send_file
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtCore import pyqtSignal, QThread
import sys

BASE_DIR = os.path.dirname(os.path.realpath(sys.argv[0]))
task_management_path = os.path.join(BASE_DIR, 'TaskManagement')
exp_config_path = os.path.join(BASE_DIR, 'config', 'exp_config')
app = Flask(__name__)


class FlaskThread(QThread):
    start_experiment_signal = pyqtSignal()
    stop_experiment_signal = pyqtSignal()
    set_parameters_signal = pyqtSignal(str)

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
            exp_id = request.args.get('experiment_id')
            data = request.json
            print(f'Received data:', data)
            df = pd.DataFrame(data)
            filepath = os.path.join(exp_config_path, f'{exp_id}.xlsx')
            df.to_excel(filepath, index=False)
            self.set_parameters_signal.emit(exp_id)
            return jsonify({"message": "参数已设定"}), 200

        @app.route('/get_status', methods=['GET'])
        def get_status_api():
            # 读取本地的 CSV 文件
            filepath = os.path.join(task_management_path, "实验任务进度管理表.csv")
            df = pd.read_csv(filepath)
            # 将 DataFrame 转换为 JSON 格式
            data = df.to_json(orient='records', force_ascii=False)
            data = json.loads(data)
            print(type(data))
            print(data)
            # 返回 JSON 数据
            return jsonify({"data": data, "message": "状态已返回"}), 200

        @app.route('/download_image', methods=['GET'])
        def download_image_api():
            try:
                exp_id = request.args.get('experiment_id')
                task_id = int(request.args.get('task_id'))
                filepath = os.path.join(task_management_path, "实验任务进度管理表.csv")
                df = pd.read_csv(filepath, na_filter=False)
                print(f'df: {df}')
                filtered_df = df[(df['实验id'] == exp_id) & (df['任务id'] == task_id)]
                print(f'filtered_df: {filtered_df}')
                if not filtered_df.empty:
                    filepath = filtered_df['图像结果'].values[0]
                    print(f"图像结果: {filepath}")
                    if filepath:
                        return send_file(filepath, as_attachment=True)
                else:
                    print("没有找到匹配的行。")
            except Exception as e:
                print(f'An error occurred when request task result: {e}')
            return jsonify({"message": "No image available"})

        @app.route('/download_video', methods=['GET'])
        def download_video_api():
            try:
                exp_id = request.args.get('experiment_id')
                task_id = int(request.args.get('task_id'))
                filepath = os.path.join(task_management_path, "实验任务进度管理表.csv")
                df = pd.read_csv(filepath, na_filter=False)
                print(f'df: {df}')
                filtered_df = df[(df['实验id'] == exp_id) & (df['任务id'] == task_id)]
                print(f'filtered_df: {filtered_df}')
                if not filtered_df.empty:
                    filepath = filtered_df['视频结果'].values[0]
                    print(f"视频结果: {filepath}")
                    if filepath:
                        return send_file(filepath, as_attachment=True)
                else:
                    print("没有找到匹配的行。")
            except Exception as e:
                print(f'An error occurred when request task result: {e}')
            return jsonify({"message": "No video available"})

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