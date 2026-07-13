# EchoLens

> See beyond the sound.
>
> 穿透声音，洞察思想。

EchoLens 是一个 AI 驱动的语音内容理解与知识沉淀系统。

它将外部服务落盘的视频和 metadata 转换为可阅读、可搜索、可分析的知识内容，并提供完整的 Web 工作台。

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
FastAPI
    ↓
React Web 工作台
```

当前已经实现：

```text
scan → queued → audio_done → transcribed → done → Web 浏览与操作
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
- 查看摘要、关键观点、完整转写和时间戳；
- 在浏览器中播放提取后的 WAV；
- 浏览创作者及其视频时间线；
- 搜索描述、摘要、转写、标签和关键观点；
- 启动扫描和完整 pipeline；
- 对单个视频继续处理或从指定阶段重跑；
- 查看后台任务状态、错误与执行结果。

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
| 前端生产服务 | Nginx |
| HTTP API | FastAPI / Uvicorn |
| 后端 CLI | Python / Typer |
| 音频处理 | FFmpeg |
| 语音识别 | Faster-Whisper |
| AI 分析 | DeepSeek |
| 持久化 | MySQL |
| 任务运行时 | Redis |
| 容器运行 | Docker Compose |

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
API_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
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

项目仍处于早期阶段，不需要保留测试数据时，可以直接删除数据库并使用最新 schema 重建。

## Docker 启动完整产品

构建并启动 API 与前端：

```powershell
docker compose up --build api frontend
```

访问 Web 工作台：

```text
http://localhost:3000
```

API 与 Swagger：

```text
http://localhost:8000/health
http://localhost:8000/docs
```

Compose 会：

- 将宿主机视频目录只读挂载到 `/data/douyin`；
- 将音频输出目录挂载到 `/data/audio`；
- 通过 `host.docker.internal` 连接宿主机 MySQL 和 Redis；
- 使用 Docker volume 缓存 Whisper 模型；
- 通过 Nginx 将前端 `/api/*` 请求转发到 FastAPI。

## 前端本地开发

先启动 API：

```powershell
docker compose up api
```

再启动 Vite：

```powershell
cd frontend
npm install
npm run dev
```

访问：

```text
http://localhost:5173
```

构建检查：

```powershell
npm run build
```

更多说明见 [frontend/README.md](frontend/README.md)。

## 后端命令行

只读扫描：

```powershell
docker compose run --rm echolens scan
```

扫描、入库并入队：

```powershell
docker compose run --rm echolens scan --enqueue
```

分阶段运行：

```powershell
docker compose run --rm echolens worker --max-tasks 40
docker compose run --rm echolens transcribe --max-tasks 40
docker compose run --rm echolens analyze --max-tasks 40
```

一次运行当前可用任务：

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

任务接口：

```text
GET /api/jobs
GET /api/jobs/{jobId}
```

操作接口：

```text
POST /api/actions/scan
POST /api/actions/pipeline
POST /api/videos/{id}/actions/process
```

完整契约见 [前端 HTTP API](docs/frontend-api.md)。

## 当前边界

暂未实现：

- 用户登录、角色与权限；
- 向量数据库和语义搜索；
- 跨视频自然语言问答；
- 创作者长期观点变化分析；
- 完整任务租约、崩溃恢复和死信机制；
- 知识图谱和推荐系统。

这些能力后置，当前产品已经能够使用真实数据完成内容处理、知识浏览和任务操作。

## 开源协议

待定
