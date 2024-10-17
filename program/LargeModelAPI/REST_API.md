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

## GET 查询任务日志

GET /get_status

> 返回示例

> 200 Response

```json
{
  "data": [
    {
      "任务id": 0,
      "任务状态": "string",
      "任务结果": "string",
      "实验id": "string",
      "开始时间": "string",
      "结束时间": null,
      "进度": "string"
    }
  ],
  "message": "string"
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
|» data|[object]|true|none||none|
|»» 任务id|integer|true|none||none|
|»» 任务状态|string|true|none||none|
|»» 任务结果|string¦null|true|none||none|
|»» 实验id|string|true|none||none|
|»» 开始时间|string¦null|true|none||none|
|»» 结束时间|null|true|none||none|
|»» 进度|string|true|none||none|
|» message|string|true|none||none|

## GET 查询任务结果

GET /download_video

### 请求参数

|名称|位置|类型|必选|说明|
|---|---|---|---|---|
|experiment_id|query|string| 否 |none|
|task_id|query|string| 否 |none|

> 返回示例

> 200 Response

### 返回结果

|状态码|状态码含义|说明|数据模型|
|---|---|---|---|
|200|[OK](https://tools.ietf.org/html/rfc7231#section-6.3.1)|none|Inline|

### 返回数据结构

# 数据模型

