# black_box_tests.py
import requests

BASE_URL = "http://localhost:5000"


def test_start_experiment():
    url = f"{BASE_URL}/get_status"
    try:
        response = requests.get(url)
        if response.status_code == 200 and response.json() == {"message": "实验已启动"}:
            print("测试通过：/start_experiment 正常工作")
        else:
            print(f"测试失败：期望状态码 200 和消息 {{'message': '实验已启动'}}, 但得到状态码 {response.status_code} 和消息 {response.json()}")
    except Exception as e:
        print(f"测试失败：发生异常 - {e}")


if __name__ == "__main__":
    test_start_experiment()
