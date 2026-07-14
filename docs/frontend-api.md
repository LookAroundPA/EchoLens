# EchoLens 前端 HTTP API

该 API 供 EchoLens Web 工作台浏览、编辑、导出内容，提交后台任务，并进行本地语义搜索与有来源问答。

## 启动

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

HTTP JSON 字段使用 `camelCase`，时间字段使用 ISO 8601。

## 后台任务

耗时操作统一执行方式：

```text
HTTP 请求
→ MySQL 创建 processing_jobs
→ Redis operation queue
→ 返回 202 Accepted
→ 独立 job-worker 执行
→ 前端轮询任务状态
```

任务状态：

```text
queued → running → succeeded
                 ↘ failed
```

Redis 无法接收任务时，API 返回 `503`，对应任务会被标记为失败。

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

其中：

- `id` 是 EchoLens MySQL 内部视频 ID；
- `videoId` 是平台视频 ID；
- `creatorSecUid` 是创作者稳定身份。

`GET /api/search` 保留为 SQL 关键词搜索。Web 工作台的“搜索”页面默认使用下面的本地混合语义搜索。

## 本地语义索引

### 索引状态

```text
GET /api/semantic/status
```

响应示例：

```json
{
  "ready": true,
  "model": "BAAI/bge-small-zh-v1.5",
  "videoCount": 120,
  "chunkCount": 1830,
  "indexedAt": "2026-07-14T12:00:00+00:00",
  "autoSync": true
}
```

### 混合语义搜索

```text
GET /api/semantic/search?q=<自然语言问题>&creator=<sec_uid>&tag=<标签>&limit=20
```

每个结果包含：

```json
{
  "match": {
    "sourceType": "transcript",
    "text": "对应的原始转写片段",
    "start": 65.2,
    "end": 78.4,
    "segmentIndex": 12,
    "segmentCount": 2,
    "score": 0.86,
    "semanticScore": 0.83,
    "keywordScore": 1.0
  }
}
```

`start/end/segmentIndex` 可直接构造视频时间深链。

### 同步或重建索引

```http
POST /api/semantic/actions/sync
Content-Type: application/json

{
  "rebuild": false
}
```

该接口返回 `semantic_index` 类型的排队任务。`rebuild=false` 只索引新增和修改视频；`true` 会清空 SQLite 索引并重新计算全部本地向量。

## 有来源跨视频问答

```http
POST /api/ask
Content-Type: application/json

{
  "question": "这些视频对提高工作效率有哪些建议？",
  "creatorSecUid": null,
  "tag": null,
  "maxSources": 8,
  "thinking": false
}
```

响应：

```json
{
  "answer": "可以将重复劳动交给人工智能。[S1]",
  "insufficientEvidence": false,
  "model": "deepseek-v4-pro",
  "thinking": false,
  "sources": [
    {
      "sourceId": "S1",
      "videoId": 7,
      "creatorSecUid": "creator-sec-uid",
      "title": "视频标题",
      "start": 65.2,
      "end": 78.4,
      "segmentIndex": 12,
      "text": "原始转写证据",
      "score": 0.86
    }
  ]
}
```

规则：

- DeepSeek 只能根据返回的本地来源回答；
- 每个实质性结论必须包含 `[S1]` 格式引用；
- 不存在的来源编号会被后端拒绝；
- 证据不足时返回 `insufficientEvidence=true`；
- `thinking=true` 开启 V4 Pro 深度思考模式。

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
- 下次语义同步会移除该视频的旧索引，直到重新分析完成。

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

标签和关键观点会去除空白及重复项。保存后状态为 `done`，下一次语义搜索会增量更新该视频索引。

## 导出接口

```text
GET /api/videos/{id}/export/markdown
GET /api/videos/{id}/export/json
```

导出包含视频信息、创作者、摘要、标签、关键观点、来源时间、转写、时间戳分段和模型名称，不包含本地绝对文件路径。

## 操作接口

```text
POST /api/actions/scan
POST /api/actions/pipeline
POST /api/videos/{id}/actions/process
POST /api/videos/actions/batch-process
```

单视频处理请求：

```json
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

## 任务接口

```text
GET  /api/jobs?status=<状态>&job_type=<类型>&video_id=<id>&limit=50
GET  /api/jobs/{jobId}
POST /api/jobs/{jobId}/actions/retry
```

任务类型：

```text
scan
pipeline
video_process
video_batch
semantic_index
```

运行中的 `result.progress` 表示阶段或视频数量进度，不代表 Whisper、DeepSeek 或嵌入模型内部百分比。

## 跨域

通过 `.env` 配置：

```text
API_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

允许 `GET`、`POST` 和 `PATCH`。
