# EchoLens

> See beyond the sound.
>
> 穿透声音，洞察思想。

EchoLens 是一个 AI 驱动的语音内容理解与知识沉淀系统。

它将外部服务落盘的视频和 metadata 转换为可阅读、可搜索、可分析的知识内容，并提供 Web 工作台。

EchoLens 不直接调用抖音，也不维护外部采集服务。外部服务负责把视频和 metadata 落盘，EchoLens 从本地目录开始完成音频处理、语音理解、内容分析和知识浏览。

## 当前全链路

```text
本地视频 + metadata
    ↓
目录扫描与协议校验
    ↓
MySQL 去重 + Redis 入队
    ↓
FFmpeg 提取 WAV
    ↓
Faster-Whisper 转写
    ↓
DeepSeek 摘要 / 标签 / 关键观点
    ↓
FastAPI + Redis 操作队列 + 独立 Worker
    ↓
React Web 工作台
```

当前已经实现：

```text
scan → queued → audio_done → transcribed → done → Web 浏览、编辑、导出与重跑
```

## 核心能力

### 内容源接入

- 扫描外部服务落盘的视频和同名 metadata；
- 使用 `author.sec_uid` 和视频 ID 去重；
- 记录 metadata 协议错误；
- 始终使用实际扫描路径，不依赖 metadata 中的采集容器路径。

### 音频处理

- 使用 FFmpeg 提取 WAV；
- 输出 `pcm_s16le / 16000 Hz / 单声道`；
- 按 `platform/creator_sec_uid/video_id.wav` 保存。

### 语音识别

- Faster-Whisper 自动语音转文字；
- 自动语言识别或指定语言；
- 保存完整转写和分段时间戳；
- 保存识别语言与模型名称。

### AI 内容理解

- 使用 DeepSeek 生成中文摘要；
- 生成主题标签；
- 提取关键观点；
- 将结构化结果写入 MySQL。

### Web 工作台

- 总览创作者、视频、处理状态和高频标签；
- 浏览和筛选所有状态的视频；
- 查看、编辑和保存摘要、标签、关键观点与完整转写；
- 导出单视频 Markdown 和 JSON；
- 在浏览器中播放提取后的 WAV；
- 浏览创作者及其视频时间线；
- 搜索描述、摘要、转写、标签和关键观点；
- 启动扫描和完整 pipeline；
- 对单个或多个视频继续处理或从指定阶段重跑；
- 查看任务阶段进度、错误、结果和失败项重试。

### 独立操作 Worker

- FastAPI 只创建任务并写入 Redis，不执行 FFmpeg、Whisper 或 DeepSeek；
- 一个独立 `job-worker` 串行消费网页提交的操作；
- API 重启不会中断正在运行的 Worker；
- Worker 启动时恢复上次遗留在 processing 队列中的消息；
- 继续使用 MySQL `processing_jobs` 保存状态、进度和结果。

详细说明见 [独立操作 Worker](docs/operation-worker.md)。

## 本地内容提供方协议

默认输入目录：

```text
D:\BaiduNetdiskDownload\dy src
```

每个视频必须存在同名 metadata：

```text
video.mp4
video.mp4.json
```

EchoLens 使用 `author.sec_uid` 作为创作者稳定身份。缺少该字段时，Scanner 会跳过文件并记录 `metadata_protocol_error`，不会回退使用昵称、`author.uid` 或顶层 `author_id`。

完整协议：

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
| AI 分析 | DeepSeek |
| 持久化 | MySQL |
| 任务运行时 | Redis |
| 后端容器运行 | Docker Compose |

## 配置

项目通过 `.env` 读取 MySQL、Redis、Faster-Whisper、DeepSeek 和 API 配置。

```text
LLM_PROVIDER=deepseek
LLM_API_KEY=
LLM_MODEL=deepseek-v4-flash
LLM_BASE_URL=https://api.deepseek.com
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=2048

WHISPER_MODEL=large-v3
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
WHISPER_LANGUAGE=
WHISPER_BEAM_SIZE=5
WHISPER_VAD_FILTER=true

API_HOST=0.0.0.0
API_PORT=8000
API_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000

REDIS_OPERATION_QUEUE=echolens:queue:operations
REDIS_OPERATION_PROCESSING_QUEUE=echolens:queue:operations:processing
```

不要把真实 `LLM_API_KEY` 提交到 GitHub。

## 数据库

新环境直接执行：

```text
scripts/mysql_schema.sql
```

现有数据库若尚未增加前端任务字段，执行一次：

```text
scripts/mysql_frontend_actions_migration.sql
```

本次独立 Worker 改造不需要新的数据库迁移。

项目仍处于早期阶段，不需要保留测试数据时，可以直接删除数据库并使用最新 schema 重建。

## 启动后端 API 与 Worker

网页操作需要同时运行 API 和独立 Worker：

```powershell
docker compose up --build api job-worker
```

访问：

```text
健康检查：http://localhost:8000/health
Swagger：http://localhost:8000/docs
```

Compose 会：

- 将宿主机视频目录只读挂载到 `/data/douyin`；
- 将音频输出目录挂载到 `/data/audio`；
- 通过 `host.docker.internal` 连接宿主机 MySQL 和 Redis；
- 使用 Docker volume 缓存 Whisper 模型；
- 使用单个 `job-worker` 串行执行网页操作任务。

只启动 `api` 时仍可浏览数据，但新提交的操作只会留在 Redis 中等待 Worker。

## 启动前端

前端不使用 Docker，也不需要 Nginx。需要本机安装 Node.js 20 或更高版本。

首次安装依赖：

```powershell
cd frontend
npm install
```

开发模式：

```powershell
npm run dev
```

访问：

```text
http://localhost:5173
```

构建后启动：

```powershell
npm run serve
```

访问：

```text
http://localhost:3000
```

`dev` 和 `serve` 都会将 `/api/*` 与 `/health` 代理到 `http://localhost:8000`。

单独构建检查：

```powershell
npm run build
```

更多说明见 [frontend/README.md](frontend/README.md)。

## 后端命令行

独立运行网页操作 Worker：

```powershell
echolens job-worker
```

只消费一个网页操作任务：

```powershell
echolens job-worker --once
```

只读扫描：

```powershell
docker compose run --rm echolens scan
```

扫描、入库并入队：

```powershell
docker compose run --rm echolens scan --enqueue
```

底层分阶段运行命令仍保留用于维护和排查：

```powershell
docker compose run --rm echolens worker --max-tasks 40
docker compose run --rm echolens transcribe --max-tasks 40
docker compose run --rm echolens analyze --max-tasks 40
```

一次运行当前可用的底层视频队列：

```powershell
docker compose run --rm echolens pipeline --max-tasks 40
```

## HTTP API

浏览接口：

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

内容编辑与导出：

```text
PATCH /api/videos/{id}/transcript
PATCH /api/videos/{id}/analysis
GET /api/videos/{id}/export/markdown
GET /api/videos/{id}/export/json
```

任务接口：

```text
GET /api/jobs
GET /api/jobs/{jobId}
POST /api/jobs/{jobId}/actions/retry
```

操作接口：

```text
POST /api/actions/scan
POST /api/actions/pipeline
POST /api/videos/{id}/actions/process
POST /api/videos/actions/batch-process
```

所有耗时操作接口只创建并入队任务，返回 `202 Accepted`；实际执行由 `job-worker` 完成。

完整契约见 [前端 HTTP API](docs/frontend-api.md)。

## 当前边界

暂未实现：

- 用户登录、角色与权限；
- 向量数据库和语义搜索；
- 跨视频自然语言问答；
- 创作者长期观点变化分析；
- 多 Worker 租约、心跳、延迟重试和死信机制；
- 知识图谱和推荐系统。

这些能力后置，当前产品已经能够使用真实数据完成内容处理、知识浏览、人工编辑、导出和任务操作。

## 开源协议

待定
