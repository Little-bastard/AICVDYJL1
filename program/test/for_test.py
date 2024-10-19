import pandas as pd

# 读取Excel文件
df = pd.read_excel(r'D:\pythonproject\AICVD\program\config\total_config\工艺参数包1-1.xlsx')

# 将DataFrame转换为JSON
json_data = df.to_json(orient='records')

print(json_data)
