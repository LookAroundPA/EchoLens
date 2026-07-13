# EchoLens 前端 HTTP API

该 API 供 EchoLens Web 前端浏览内容并触发当前已实现的处理流程。

它包含：

- 总览、创作者、视频、标签和搜索接口；
- 扫描与完整 pipeline 触发接口；
- 单视频继续处理或指定阶段重跑接口；
- 后台任务状态和结果查询接口。

## 启动

现有数据库先执行一次：

```text
scripts/mysql_frontend_actions_migration.sql
```

项目早期数据不需要保留时，也可以直接使用最新 `scripts/mysql_schema.sql` 重建数据库。

启动 API：

```powershell
docker compose build
docker compose up api
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

API 允许前端使用 `GET` 和 `POST`。

## 数据格式

HTTP JSON 字段使用 `camelCase`。时间字段使用 ISO 8601 格式。

视频接口中的：

- `id`：EchoLens MySQL 内部视频 ID，用于详情、音频和操作接口；
- `videoId`：平台提供的视频 ID；
- `creatorSecUid`：创作者稳定身份。

耗时操作不会一直阻塞 HTTP 请求。写接口返回 `202 Accepted` 和一个 job，前端随后轮询：

```text
GET /api/jobs/{jobId}
```

任务状态：

```text
queued → running → succeeded
                 ↘ failed
```

## 浏览接口

### 总览

```http
GET /api/dashboard
```

返回创作者数、视频数、完成数、状态统计、高频标签和最近视频。

### 创作者列表

```http
GET /api/creators?q=<名称或sec_uid>&limit=100
```

### 创作者详情

```http
GET /api/creators/{secUid}?limit=100
```

返回创作者统计、高频标签和视频时间线。

### 视频列表

```http
GET /api/videos?q=<关键词>&creator=<sec_uid>&status=<状态>&tag=<标签>&limit=50&offset=0
```

所有参数均可省略。该接口可展示所有处理状态，不限于 `done`。

### 标签列表

```http
GET /api/tags?creator=<sec_uid>&limit=100
```

返回标签及其使用次数。

### 视频详情

```http
GET /api/videos/{id}
```

返回：

- 视频描述和发布时间；
- 当前处理状态；
- DeepSeek 摘要、标签和关键观点；
- 完整转写及时间戳分段；
- Whisper 与 DeepSeek 模型名称；
- 音频大小和可播放 URL。

### 视频音频

```http
GET /api/videos/{id}/audio
```

返回 `audio/wav`。数据库没有音频路径或宿主机文件不存在时返回 `404`。

### 搜索

```http
GET /api/search?q=<关键词>&creator=<sec_uid>&tag=<精确标签>&limit=20
```

只有 `q` 必填。搜索范围：视频描述、摘要、转写、标签和关键观点。

## 操作接口

### 扫描内容源

```http
POST /api/actions/scan
Content-Type: application/json

{
  "enqueue": true
}
```

- `enqueue=true`：扫描后把新增视频写入 MySQL 并推送 Redis；
- `enqueue=false`：只扫描和校验，不写入。

任务成功结果包含：

```json
{
  "discovered": 40,
  "skipped": 0,
  "issueCounts": {},
  "enqueue": true,
  "inserted": 0,
  "queued": 0,
  "skippedExisting": 40
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

执行顺序：

```text
扫描并入队
→ 音频提取
→ Faster-Whisper 转写
→ DeepSeek 分析
```

- `scan` 默认 `true`；
- `maxTasks` 可省略，省略时处理当前全部可用任务；
- `maxTasks` 是每个阶段的最大处理数量。

### 单视频继续或重跑

```http
POST /api/videos/{id}/actions/process
Content-Type: application/json

{
  "stage": "current",
  "continueToDone": true
}
```

`stage` 可选值：

```text
current
 audio
 transcription
 analysis
```

含义：

- `current`：根据视频当前状态继续；
- `audio`：从音频提取重新开始；
- `transcription`：保留现有 WAV，从转写重新开始；
- `analysis`：保留现有转写，从 DeepSeek 分析重新开始。

`continueToDone=true` 时，会继续执行后续阶段直到 `done`；设置为 `false` 时只执行所选阶段。

从较早阶段重跑时，后续旧结果会删除并重新生成，避免展示旧摘要或旧转写。

## 任务接口

### 任务列表

```http
GET /api/jobs?status=<状态>&job_type=<类型>&video_id=<id>&limit=50
```

过滤参数均可省略。

任务类型：

```text
scan
pipeline
video_process
```

### 任务详情

```http
GET /api/jobs/{jobId}
```

成功任务的 `result` 保存处理统计；失败任务的 `errorMessage` 保存错误原因。

示例：

```json
{
  "id": 12,
  "videoId": null,
  "jobType": "pipeline",
  "status": "succeeded",
  "payload": {
    "scan": true,
    "maxTasks": 40
  },
  "result": {
    "scan": {},
    "audio": {},
    "transcription": {},
    "analysis": {}
  },
  "errorMessage": null
}
```

## 前端开发代理

Vite 可将 `/api` 和 `/health` 代理到：

```text
http://localhost:8000
```

浏览器即可使用相对路径：

```ts
fetch('/api/dashboard')
fetch('/api/videos?status=done')
fetch('/api/actions/pipeline', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ scan: true, maxTasks: 40 }),
})
```

## 当前接口边界

当前前端没有业务需求，因此不提供以下无意义的写操作：

- 删除创作者或原始视频；
- 手工修改平台 metadata；
- 在页面中保存 DeepSeek API Key；
- 用户、角色和权限管理。

这些不是当前前端缺失接口，而是尚未进入产品范围的功能。
