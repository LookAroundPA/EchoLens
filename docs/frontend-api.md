# EchoLens 前端 HTTP API

该 API 是供 EchoLens Web 前端使用的只读接口。它读取现有 MySQL 数据，不触发扫描、转写或 DeepSeek 分析任务。

## 启动

```powershell
docker compose build
docker compose up api
```

默认地址：

```text
http://localhost:8000
```

健康检查：

```text
GET /health
```

OpenAPI 与 Swagger UI：

```text
GET /openapi.json
GET /docs
```

## 跨域配置

前端开发服务器默认允许：

```text
http://localhost:5173
http://127.0.0.1:5173
```

通过 `.env` 修改：

```text
API_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

多个 origin 使用英文逗号分隔，不要填写路径。

## 数据格式

HTTP JSON 字段使用 `camelCase`。时间字段使用 ISO 8601 UTC 格式。

视频接口中的 `id` 是 EchoLens MySQL 内部视频 ID。前端应使用该值访问视频详情和音频接口；`videoId` 是平台提供的视频 ID。

## 接口

### 总览

```http
GET /api/dashboard
```

返回：

- 创作者总数；
- 视频总数；
- `done` 视频数；
- 各处理状态数量；
- 高频标签；
- 最近更新的视频。

### 创作者列表

```http
GET /api/creators?q=<名称或sec_uid>&limit=100
```

`q` 可省略。

### 创作者详情

```http
GET /api/creators/{secUid}?limit=100
```

返回创作者统计、高频标签和视频时间线。

### 视频详情

```http
GET /api/videos/{id}
```

返回：

- 视频描述和发布时间；
- DeepSeek 摘要、标签和关键观点；
- 完整转写及时间戳分段；
- Whisper 与 DeepSeek 模型名称；
- 音频大小和可播放 URL。

### 视频音频

```http
GET /api/videos/{id}/audio
```

返回 `audio/wav`。数据库中没有音频路径或宿主机文件不存在时返回 `404`。

### 搜索

```http
GET /api/search?q=<关键词>&creator=<sec_uid>&tag=<精确标签>&limit=20
```

只有 `q` 必填。搜索范围：

- 视频描述；
- 分析摘要；
- 完整转写；
- 标签；
- 关键观点。

`creator` 和 `tag` 可省略。

## 前端开发代理

Vite 开发环境可将 `/api` 和 `/health` 代理到：

```text
http://localhost:8000
```

这样浏览器请求可以保持相对路径：

```ts
fetch('/api/dashboard')
fetch('/api/videos/7')
```

## 只读边界

当前 API 不提供：

- 创建、修改或删除数据；
- 启动 pipeline；
- 重试失败任务；
- 修改模型或 API Key；
- 用户登录与权限管理。
