# EchoLens

> See beyond the sound.  
> 穿透声音，洞察思想。

EchoLens 是一个面向个人和小范围使用的本地语音内容理解与知识沉淀系统。外部服务负责把视频和 metadata 落盘，EchoLens 从本地文件开始完成音频提取、转写、分析、检索和有来源问答。

EchoLens 不下载视频，也不直接访问抖音。

## 当前全链路

```text
本地视频 + metadata
→ 扫描与协议校验
→ MySQL 去重 + Redis 入队
→ FFmpeg 提取 WAV
→ Faster-Whisper 转写与时间戳
→ DeepSeek 摘要 / 标签 / 关键观点
→ 本地中文语义索引
→ 混合搜索与 DeepSeek V4 Pro 有来源问答
→ React Web 工作台
```

目前已经能够完成：

```text
视频进入系统
→ 自动转成知识
→ 按创作者聚合
→ 编辑与导出
→ 关键词和语义搜索
→ 跨视频提问
→ 点击引用回到原音频
```

## 核心能力

### 内容处理

- 扫描外部服务落盘的视频和同名 metadata；
- 严格使用 `author.sec_uid` 作为创作者稳定身份；
- MySQL 保存内容，Redis 负责视频与网页操作队列；
- FFmpeg 输出 `pcm_s16le / 16000 Hz / 单声道` WAV；
- Faster-Whisper 保存完整转写和时间戳分段；
- DeepSeek 保存中文摘要、标签和关键观点。

### Web 工作台

- 查看总览、视频、创作者和任务；
- 编辑完整转写、摘要、标签和关键观点；
- 导出单视频 Markdown 和 JSON；
- 批量继续处理、重新转写和重新分析；
- 查看阶段进度并重试失败任务或批量失败项；
- 点击转写和观点来源跳到音频时间；
- 复制可分享的时间深链；
- 查看创作者总体摘要、主题、聚合观点和代表视频。

### 本地语义搜索

- 使用 FastEmbed 和 `BAAI/bge-small-zh-v1.5` 在本地生成中文向量；
- 使用 SQLite 保存轻量向量索引，不要求额外向量数据库；
- 结合语义相似度与关键词匹配；
- 支持限定创作者和标签；
- 搜索结果返回原始视频、转写片段和时间点；
- 新增或修改视频只做增量索引。

### DeepSeek V4 Pro 有来源问答

- 先从本地索引检索视频证据；
- 再由 `deepseek-v4-pro` 仅根据这些证据组织答案；
- 普通问题默认关闭思考模式；
- 复杂比较和综合问题可开启深度思考；
- 回答使用 `[S1]`、`[S2]` 引用；
- 引用可直接打开视频和音频时间点；
- 没有足够证据时明确拒答；
- 后端拒绝不存在的引用和无来源结论。

详细说明见 [本地语义搜索与有来源问答](docs/semantic-search-and-qa.md)。

### 独立操作 Worker

- FastAPI 只创建任务并推送 Redis；
- `job-worker` 串行执行扫描、FFmpeg、Whisper、DeepSeek 和语义索引任务；
- API 重启不会清空已入队任务；
- Worker 启动时恢复 processing 队列中的遗留消息；
- MySQL `processing_jobs` 保存任务状态、进度、结果和错误。

## 本地内容协议

默认输入目录：

```text
D:\BaiduNetdiskDownload\dy src
```

每个视频必须存在同名 metadata：

```text
video.mp4
video.mp4.json
```

EchoLens 只接受 `author.sec_uid` 作为创作者身份。缺失或无效时跳过文件并记录 `metadata_protocol_error`，不会回退到昵称或其他 ID。

完整协议见：

- [本地内容提供方对接协议](docs/integrations/local-source-provider-protocol.md)
- [本地内容源扫描设计](docs/local-source-scan-design.md)

## 技术栈

| 模块 | 技术 |
| --- | --- |
| 前端 | React / TypeScript / Vite / TanStack Query |
| HTTP API | FastAPI / Uvicorn |
| 后端 CLI | Python / Typer |
| 音频处理 | FFmpeg |
| 语音识别 | Faster-Whisper |
| 内容分析与问答 | DeepSeek |
| 本地嵌入 | FastEmbed / BGE small zh |
| 持久化 | MySQL / SQLite |
| 任务运行时 | Redis |
| 后端运行 | Docker Compose |

## 配置

复制 `.env.example` 并填写 MySQL、Redis 和 DeepSeek 配置。不要把真实 API Key 提交到 GitHub。

主要配置：

```text
LLM_PROVIDER=deepseek
LLM_API_KEY=
LLM_MODEL=deepseek-v4-flash
LLM_BASE_URL=https://api.deepseek.com

QA_MODEL=deepseek-v4-pro
QA_TEMPERATURE=0.1
QA_MAX_TOKENS=4096
QA_DEFAULT_SOURCES=8

SEMANTIC_MODEL=BAAI/bge-small-zh-v1.5
SEMANTIC_MODEL_CACHE_DIR=data/models/fastembed
SEMANTIC_INDEX_PATH=data/semantic/echolens.sqlite3
SEMANTIC_AUTO_SYNC=true
```

Docker Compose 会将模型缓存和语义索引保存在独立 volume 中，API 与 Worker 共享。

## 数据库

新环境执行：

```text
scripts/mysql_schema.sql
```

需要前端任务表迁移的现有环境执行：

```text
scripts/mysql_frontend_actions_migration.sql
```

语义搜索使用独立 SQLite 文件，不需要 MySQL 迁移。

## 启动后端

网页操作需要同时运行 API 和 Worker：

```powershell
docker compose up --build api job-worker
```

访问：

```text
健康检查：http://localhost:8000/health
Swagger：http://localhost:8000/docs
```

Compose 会：

- 挂载本地视频目录和音频目录；
- 通过 `host.docker.internal` 连接宿主机 MySQL 和 Redis；
- 缓存 Whisper 与 FastEmbed 模型；
- 持久化本地 SQLite 语义索引；
- 使用单个 `job-worker` 串行执行网页任务。

## 启动前端

前端在宿主机运行，不使用 Docker 或 Nginx：

```powershell
cd frontend
npm install
npm run dev
```

访问：

```text
http://localhost:5173
```

单独构建检查：

```powershell
npm run build
```

## 首次建立语义索引

可以在“搜索”或“问答”页面点击“同步语义索引”，也可以执行：

```powershell
echolens knowledge semantic-sync
```

完全重建：

```powershell
echolens knowledge semantic-sync --rebuild
```

首次运行需要下载本地中文嵌入模型。之后会复用缓存。默认搜索和问答前会检查增量变化，但未修改的视频不会重复计算向量。

## 常用 CLI

```powershell
echolens job-worker
echolens job-worker --once

echolens knowledge semantic-search "怎样减少重复工作"
echolens knowledge ask "这些视频有哪些共同建议？"
echolens knowledge ask "总结这个创作者的核心观点" --creator <sec_uid> --thinking
```

底层处理命令仍保留用于维护：

```powershell
docker compose run --rm echolens scan --enqueue
docker compose run --rm echolens worker --max-tasks 40
docker compose run --rm echolens transcribe --max-tasks 40
docker compose run --rm echolens analyze --max-tasks 40
docker compose run --rm echolens pipeline --max-tasks 40
```

## HTTP API

浏览与内容：

```text
GET /health
GET /api/dashboard
GET /api/creators
GET /api/creators/{secUid}
GET /api/videos
GET /api/videos/{id}
GET /api/videos/{id}/audio
GET /api/tags
GET /api/search
```

语义搜索与问答：

```text
GET  /api/semantic/status
GET  /api/semantic/search
POST /api/semantic/actions/sync
POST /api/ask
```

编辑与导出：

```text
PATCH /api/videos/{id}/transcript
PATCH /api/videos/{id}/analysis
GET   /api/videos/{id}/export/markdown
GET   /api/videos/{id}/export/json
```

任务与操作：

```text
GET  /api/jobs
GET  /api/jobs/{jobId}
POST /api/jobs/{jobId}/actions/retry
POST /api/actions/scan
POST /api/actions/pipeline
POST /api/videos/{id}/actions/process
POST /api/videos/actions/batch-process
```

所有耗时操作只创建任务并返回 `202 Accepted`，实际执行由 `job-worker` 完成。

## 当前边界

当前版本面向个人和小范围使用，暂不实现：

- 用户登录、角色和权限；
- 大规模向量数据库与高并发检索；
- 多轮长期问答记忆和聊天历史；
- 联网搜索与外部事实补充；
- 多 Worker 租约、心跳、延迟重试和死信队列；
- 知识图谱、推荐系统和复杂趋势预测。

## 开源协议

待定。
