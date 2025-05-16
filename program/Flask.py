import json
import os
import sys
import traceback

import pandas as pd
from PyQt5.QtCore import pyqtSignal, QThread
from PyQt5.QtWidgets import QApplication, QMainWindow
from flask import Flask, jsonify, request, send_file, make_response
from werkzeug.utils  import safe_join
from flask_cors import CORS
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
task_management_path = os.path.join(BASE_DIR, 'TaskManagement')
exp_config_path = os.path.join(BASE_DIR, 'config', 'exp_config')
app = Flask(__name__)
CORS(app, origins=["https://127.0.0.1:8086"])

class FlaskThread(QThread):
    start_experiment_signal = pyqtSignal()
    stop_experiment_signal = pyqtSignal()
    set_parameters_signal = pyqtSignal(str)

    def run(self):
        @app.route('/start_experiment', methods=['POST'])
        def start_experiment_api():
            try:
                # 发送信号
                self.start_experiment_signal.emit()
                return jsonify({"message": "实验已启动", "code": 200}), 200
            except Exception as e:
                return jsonify({"message": "实验启动失败", "code": 500}), 500

        @app.route('/stop_experiment', methods=['POST'])
        def stop_experiment_api():
            try:
                self.stop_experiment_signal.emit()
                return jsonify({"message": "实验已停止"}), 200
            except Exception as e:
                return jsonify({"message": "实验停止失败", "code": 500}), 500

        @app.route('/set_parameters', methods=['POST'])
        def set_params_api():
            try:
                exp_id = request.args.get('experiment_id')
                dataStr = request.json
                print(f'Received data:', dataStr)
                data = json.loads(dataStr)
                df = pd.DataFrame(data)
                filepath = os.path.join(exp_config_path, f'{exp_id}.xlsx')
                df.to_excel(filepath, index=False)
                self.set_parameters_signal.emit(exp_id)
                return jsonify({"message": "参数已设定", "code": 200}), 200
            except Exception as e:
                traceback.print_tb(e)
                return jsonify({"message": "参数设置失败", "code": 500}), 500

        @app.route('/get_status', methods=['GET'])
        def get_status_api():
            # 读取本地的 CSV 文件
            print(f'路径：{BASE_DIR}')
            filepath = os.path.join(task_management_path, "实验任务进度管理表.csv")
            df = pd.read_csv(filepath)
            # 将 DataFrame 转换为 JSON 格式
            data = df.to_json(orient='records', force_ascii=False)
            data = json.loads(data)
            # print(type(data))
            # print(data)
            flag = 200
            message = "实验执行完成"
            for entity in data:
                if entity["task_status"] == "未开始":
                    entity["status_code"] = "01"
                if entity["task_status"] == "进行中":
                    flag = 201
                    message = "实验进行中"
                    entity["status_code"] = "02"
                if entity["task_status"] == "停止中":
                    flag = 201
                    message = "实验进行中"
                    entity["status_code"] = "03"
                if entity["task_status"] == "已完成":
                    entity["status_code"] = "04"
                if entity["task_status"] == "实验执行异常":
                    flag = 500
                    message = "任务id" + str(entity["task_id"]) + "执行失败"
                    entity["status_code"] = "05"
                if entity["start_time"] is None:
                    entity["progress"] = "0%"
                    entity["task_status"] = "未开始"
                    entity["status_code"] = "01"
            # 返回 JSON 数据
            return jsonify({"result": {"data": data, "message": "状态已返回"}, "code": flag, "message": message}), flag

        @app.route('/download_image', methods=['GET'])
        def download_image_api():
            try:
                exp_id = request.args.get('experiment_id')
                task_id = int(request.args.get('task_id'))
                filepath = os.path.join(task_management_path, "实验任务进度管理表.csv")
                df = pd.read_csv(filepath, na_filter=False)
                print(f'df: {df}')
                filtered_df = df[(df['experiment_id'] == int(exp_id)) & (df['task_id'] == task_id)]
                print(f'filtered_df: {filtered_df}')
                if not filtered_df.empty:
                    filepath = filtered_df['image_result'].values[0]
                    print(f"图像结果: {filepath}")
                    if filepath:
                        response = make_response(send_file(filepath, mimetype="image/jpeg", as_attachment=True, conditional=False))
                        # 添加跨域和缓存头
                        response.headers['Access-Control-Allow-Origin'] = '*'
                        response.headers['Cache-Control'] = 'no-store'  # 禁止缓存
                        return response
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
                filtered_df = df[(df['experiment_id'] == int(exp_id)) & (df['task_id'] == task_id)]
                print(f'filtered_df: {filtered_df}')
                if not filtered_df.empty:
                    filepath = filtered_df['video_result'].values[0]
                    print(f"视频结果: {filepath}")
                    if filepath:
                        response = make_response(send_file(filepath, mimetype="video/mp4", as_attachment=True, conditional=False))
                        # 添加跨域和缓存头
                        response.headers['Access-Control-Allow-Origin'] = '*'
                        response.headers['Cache-Control'] = 'no-store'  # 禁止缓存
                        return response
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