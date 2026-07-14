# EchoLens 前端 HTTP API

该 API 供 EchoLens Web 工作台浏览、编辑、导出内容，并向独立 Worker 提交处理任务。

## 启动

API 和操作 Worker 一起启动：

```powershell
docker compose up --build api job-worker
```

默认地址：

```text
http://localhost:8000
```

入口：

```text
GET /health
GET /openapi.json
GET /docs
```

## 请求与任务执行

HTTP JSON 字段使用 `camelCase`，时间字段使用 ISO 8601。

耗时操作的执行方式：

```text
HTTP 请求
→ MySQL 创建 processing_jobs
→ Redis operation queue
→ 返回 202 Accepted
→ 独立 job-worker 执行
→ 前端轮询任务状态
```

轮询接口：

```text
GET /api/jobs/{jobId}
```

任务状态：

```text
queued → running → succeeded
                 ↘ failed
```

Redis 无法接收任务时，API 返回 `503`，对应 job 会被标记为 `failed`。

## 跨域

通过 `.env` 配置：

```text
API_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

允许前端使用 `GET`、`POST` 和 `PATCH`。

## 浏览接口

```text
GET /api/dashboard
GET /api/creators?q=<名称或sec_uid>&limit=100
GET /api/creators/{secUid}?limit=100
GET /api/videos?q=<关键词>&creator=<sec_uid>&status=<状态>&tag=<标签>&limit=50&offset=0
GET /api/videos/{id}
GET /api/videos/{id}/audio
GET /api/tags?creator=<sec_uid>&limit=100
GET /api/search?q=<关键词>&creator=<sec_uid>&tag=<标签>&limit=20
```

视频接口中的：

- `id`：EchoLens MySQL 内部视频 ID；
- `videoId`：平台提供的视频 ID；
- `creatorSecUid`：创作者稳定身份。

搜索范围包括描述、摘要、转写、标签和关键观点。

## 编辑接口

### 保存完整转写

```http
PATCH /api/videos/{id}/transcript
Content-Type: application/json

{
  "transcript": "人工修正后的完整转写"
}
```

行为：

- 保留原时间戳分段、语言和 Whisper 模型；
- 视频状态改为 `transcribed`；
- 旧分析继续保留，但前端显示为需要更新；
- 空白转写返回 `422`。

### 保存分析

```http
PATCH /api/videos/{id}/analysis
Content-Type: application/json

{
  "summary": "摘要",
  "tags": ["AI", "学习"],
  "keyPoints": ["观点一", "观点二"]
}
```

标签和关键观点会去除空白项及重复项。没有转写时返回 `409`。保存后视频状态为 `done`。

## 导出接口

```text
GET /api/videos/{id}/export/markdown
GET /api/videos/{id}/export/json
```

导出内容包含视频信息、创作者、摘要、标签、关键观点、转写、时间戳分段和模型名称，不包含本地绝对文件路径。

## 操作接口

### 扫描内容源

```http
POST /api/actions/scan
Content-Type: application/json

{
  "enqueue": true
}
```

### 运行完整 pipeline

```http
POST /api/actions/pipeline
Content-Type: application/json

{
  "scan": true,
  "maxTasks": 40
}
```

执行顺序：扫描与入队、音频提取、Faster-Whisper 转写、DeepSeek 分析。

### 单视频继续或重跑

```http
POST /api/videos/{id}/actions/process
Content-Type: application/json

{
  "stage": "current",
  "continueToDone": true
}
```

`stage` 可选：

```text
current
audio
transcription
analysis
```

### 批量处理视频

```http
POST /api/videos/actions/batch-process
Content-Type: application/json

{
  "videoIds": [3, 7, 9],
  "stage": "analysis",
  "continueToDone": true
}
```

批量任务串行处理所选视频，并在 `result.items` 中保存每个视频的成功或失败结果。

## 任务接口

### 任务列表

```text
GET /api/jobs?status=<状态>&job_type=<类型>&video_id=<id>&limit=50
```

任务类型：

```text
scan
pipeline
video_process
video_batch
```

### 任务详情

```text
GET /api/jobs/{jobId}
```

运行中的 `result.progress` 表示阶段或视频数量进度，不代表 Whisper 或 DeepSeek 内部执行百分比。

### 重试失败任务

```text
POST /api/jobs/{jobId}/actions/retry
```

只允许重试状态为 `failed` 的任务。原任务保留，新建任务会增加 `retryCount` 并重新入 Redis。

批量任务内部部分视频失败时，前端会提取失败视频 ID，重新创建一个只包含这些视频的 `video_batch` 任务。

## Redis 操作队列

默认键名：

```text
echolens:queue:operations
echolens:queue:operations:processing
```

使用 Redis List 与 `BRPOPLPUSH`，兼容 Redis 3.0.504。当前默认只运行一个 `job-worker`。

更多运行说明见 [独立操作 Worker](operation-worker.md)。

## 当前边界

当前不提供：

- 删除创作者或原始视频；
- 修改平台 metadata；
- 在页面保存 DeepSeek API Key；
- 用户、角色与权限管理；
- 多 Worker 租约、心跳、延迟重试和死信机制。
