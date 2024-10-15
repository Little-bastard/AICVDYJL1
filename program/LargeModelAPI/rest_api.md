---
title: 个人项目
language_tabs:
  - shell: Shell
  - http: HTTP
  - javascript: JavaScript
  - ruby: Ruby
  - python: Python
  - php: PHP
  - java: Java
  - go: Go
toc_footers: []
includes: []
search: true
code_clipboard: true
highlight_theme: darkula
headingLevel: 2
generator: "@tarslib/widdershins v4.0.23"

---

# 个人项目

Base URLs:

# Authentication

# LargeModelAPI

## POST 启动实验

POST /start_experiment

> 返回示例

```json
{
  "message": "实验已启动"
}
```

### 返回结果

|状态码|状态码含义|说明|数据模型|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|none|Inline|

### 返回数据结构

状态码 **200**

|名称|类型|必选|约束|中文名|说明|
|---|---|---|---|---|---|
|» message|string|true|none||none|

## POST 停止实验

POST /stop_experiment

> 返回示例

```json
{
  "message": "实验已停止"
}
```

### 返回结果

|状态码|状态码含义|说明|数据模型|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|none|Inline|

### 返回数据结构

状态码 **200**

|名称|类型|必选|约束|中文名|说明|
|---|---|---|---|---|---|
|» message|string|true|none||none|

## POST 传入参数表

POST /set_parameters

> Body 请求参数

```json
{
  "Parameters": {
    "Order": "",
    "A": "",
    "B": "",
    "mass_A": "",
    "mass_B": "",
    "Substrate": "",
    "temperature_A": {
      "temperature": [],
      "time": []
    },
    "temperature_B": {
      "temperature": [],
      "time": []
    },
    "Ar_flow": {
      "time": [],
      "flow": []
    },
    "H2_flow": {
      "time": [],
      "flow": []
    }
  }
}
```

### 请求参数

|名称|位置|类型|必选|说明|
|---|---|---|---|---|
|body|body|object| 否 |none|

> 返回示例

```json
{
  "message": "参数已设定"
}
```

### 返回结果

|状态码|状态码含义|说明|数据模型|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|none|Inline|

### 返回数据结构

状态码 **200**

|名称|类型|必选|约束|中文名|说明|
|---|---|---|---|---|---|
|» message|string|true|none||none|

# 数据模型

