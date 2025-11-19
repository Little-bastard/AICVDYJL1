import glob
import os
import traceback

import cv2
import numpy as np
from scipy.optimize import curve_fit


class SimulateData:
    def __init__(self):
        # 图像数据路径（相对 code 目录）
        self.data_path = './autoFocus'

        # 收集可用的帧索引（文件名为数字）
        files = glob.glob(os.path.join(self.data_path, '*.jpg'))
        idxs = []
        for f in files:
            name = os.path.splitext(os.path.basename(f))[0]
            try:
                idxs.append(int(name))
            except ValueError:
                pass

        if not idxs:
            raise FileNotFoundError(f'未在路径 {self.data_path} 找到任何 jpg 图像')

        self.min_idx = min(idxs)
        self.max_idx = max(idxs)

        # 在有效范围内选择一个安全初始位置（居中），避免一开始就越界
        self.cur_idx = (self.min_idx + self.max_idx) // 2

    def move(self, distance):
        # 运动后进行钳制，防止越界导致读不到图像
        self.cur_idx = max(self.min_idx, min(self.max_idx, self.cur_idx + distance))


    def get_img(self):
        img_path = '{}/{}.jpg'.format(self.data_path, self.cur_idx)
        gray_img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
        if gray_img is None:
            raise FileNotFoundError(f'读图失败，文件不存在或无法打开: {img_path}')
        return gray_img

def sobel(img):
    # 功能：Sobel算子通过计算图像的水平和垂直梯度来检测边缘，进而评估图像的清晰度，边缘越明显，图像质量越高。
    # 输入：np.array 格式的彩色图像*1
    # 输出：图像对应的Sobel分数
    # img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    sobelx = cv2.Sobel(img, cv2.CV_64F, 1, 0, ksize=3)
    sobely = cv2.Sobel(img, cv2.CV_64F, 0, 1, ksize=3)
    sobel_score = np.mean(sobelx**2 + sobely**2).item()
    print(f"图像评分： {sobel_score}")
    return sobel_score


def gaussian(x, A, B, mu, sigma):
    # 高斯曲线
    return A * np.exp(-((x - mu) ** 2) / (2 * sigma ** 2)) + B


def fit_gaussian_from_focus(focus):
    """
    功能：拟合单峰高斯曲线
    输入: focus （x, y）
    输出: 拟合函数 f(x), 参数 (A, mu, sigma)
    """
    x_data, y_data = focus

    # print(x_data)
    # print(y_data)

    if np.any(y_data <= 0):
        raise ValueError("y值必须为正数")

    # 初始猜测参数：A=max(y), mu=x 对应最大 y, sigma=1
    idx_max = np.argmax(y_data)
    idx_min = np.argmin(y_data)
    A0 = y_data[idx_max]
    B0 = x_data[idx_min]
    mu0 = x_data[idx_max]
    sigma0 = (np.max(x_data) - np.min(x_data)) / 2
    p0 = [A0, B0, mu0, sigma0]

    # 拟合高斯曲线
    weights = 1 / (abs(x_data - mu0) + 1e-3)

    popt, _ = curve_fit(
        gaussian, x_data, y_data, p0=p0,
        bounds=([0, -np.inf, np.min(x_data), 1e-6], [np.inf, np.inf, np.max(x_data), max(x_data) - min(x_data)]),
        maxfev=10000,
    )

    A_fit, B_fit, mu_fit, sigma_fit = popt
    # f = lambda x: gaussian(x, A_fit, B_fit, mu_fit, sigma_fit)

    return mu_fit


def dynamic_focu_search(search_num, step_distance):
    # 功能：给定初始帧，摄像头进行上下移动，搜索初始点附近不同图像对应的图像质量（Sobel）
    # 输入：search_num：上下搜索的点的数量；step_distance；镜头每次移动的步长
    # 输出：搜索到的不同焦距对应点
    # 后续改进：清晰度分数对应索引不应在采集点边缘（保证图像质量特征峰值（最佳焦距）包含在了搜索范围内）

    # distances = [-search_num * step_distance] + [step_distance] * (search_num * 2)
    # focus_x = range(-search_num * step_distance, search_num * step_distance + 1, step_distance)

    distances = [-search_num * step_distance] + [step_distance] * (search_num * 2)
    focus_x = range(-search_num * step_distance, search_num * step_distance + 1, step_distance)

    clarity_score = []
    for distance in distances:
        # move + - 分别表示两个方向
        sd.move(distance)

        # get img 获取当前摄像头对应的图像
        gray_img = sd.get_img()

        # get sobel score
        clarity_score += [sobel(gray_img)]

    focus_x = np.array(focus_x)
    clarity_score = np.array(clarity_score)

    return (focus_x, clarity_score)

    # distances = [0] + [-1 * step_distance] * 2 * search_num
    # focus_x = [-1*i*step_distance for i in range(search_num * 2 + 1)]
    #
    # # print('Distance:' * 10, distances)
    # # print('Focus:' * 10, focus_x)
    #
    # clarity_score = []
    # for distance in distances:
    #     # move + - 分别表示两个方向
    #     sd.move(distance)
    #
    #     # get img 获取当前摄像头对应的图像
    #     gray_img = sd.get_img()
    #
    #     # get sobel score
    #     clarity_score += [sobel(gray_img)]
    #
    # focus_x = np.array(focus_x)
    # clarity_score = np.array(clarity_score)
    #
    # return (focus_x, clarity_score)

def search_once(search_num, step_distance):
    try:
        print(f'search_num: {search_num}')
        print(f'step_distance: {step_distance}')
        global sd
        sd = SimulateData()

        selected_focus = dynamic_focu_search(
            search_num=search_num,
            step_distance=step_distance,
        )

        # 拟合高斯曲线，返回最佳值
        best_focus_x = fit_gaussian_from_focus(selected_focus)
        best_focus_distance = best_focus_x - search_num * step_distance


        # 摄像头当前位置移动best_focus_distance距离（有正负之分，表示两个方向）到达最佳焦距，对焦完成
        sd.move(best_focus_distance)

        print('Best Focus:', sd.cur_idx)
    except Exception as e:
        print(e)
        traceback.print_exc()
    return best_focus_distance + search_num * step_distance * 2

sd = None

if __name__ == '__main__':
    try:
        search_once(3, 24)
    except Exception as e:
        print(f'error: {e}')
        traceback.print_exc()