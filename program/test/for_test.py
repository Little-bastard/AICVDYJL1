import pandas as pd

# 假设这是你已有的DataFrame
data = {
    'Column1': [1],
    'Column2': ['A']
}
df = pd.DataFrame(data)

df["Column3"] = f'vid'

df.to_excel("test.xlsx", index=False)

df = pd.DataFrame(data)
df["Column3"] = f'pdd'
# 使用ExcelWriter以追加模式打开Excel文件
with pd.ExcelWriter("test.xlsx", mode='a', engine='openpyxl', if_sheet_exists='overlay') as writer:
    # 将DataFrame追加到名为'Sheet1'的工作表中，如果不指定sheet_name，默认会创建一个新的工作表
    df.to_excel(writer, sheet_name='Sheet1', index=False)


# 打印新的列名
print(df)

