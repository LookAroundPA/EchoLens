# EchoLens

> See beyond the sound.
>
> 穿透声音，洞察思想。

EchoLens 是一个 AI 驱动的语音内容理解与知识沉淀系统。

它将外部服务落盘的视频和 metadata 转换为可搜索、可分析、可持续积累的知识资产。

EchoLens 不直接调用抖音，也不维护外部采集服务。外部服务负责把视频和 metadata 落盘，EchoLens 从本地目录开始完成音频处理、语音理解、内容分析和知识查询。

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
MySQL 知识查询
```

当前已真实验证至：

```text
scan → queued → audio_done → transcribed → done
```

## 核心能力

### 内容源接入

- 扫描外部服务落盘的视频和同名 metadata；
- 使用稳定创作者身份和视频 ID 去重；
- 记录协议错误和文件状态；
- 不依赖采集服务 metadata 中的容器路径。

### 音频处理

- 使用 FFmpeg 提取 WAV；
- 输出 `pcm_s16le / 16000 Hz / 单声道`；
- 按 `platform/creator_sec_uid/video_id.wav` 保存。

### 语音识别

- Faster-Whisper 自动语音转文字；
- 自动语言识别或指定语言；
- 保存完整转写和分段时间戳；
- 保存模型名称和识别语言。

### AI 内容理解

- 使用 DeepSeek 生成中文摘要；
- 生成主题标签；
- 提取关键观点；
- 结构化结果写入 MySQL。

### 知识查询

- 查看创作者及其已完成内容数量；
- 按创作者和标签筛选；
- 搜索描述、转写、摘要、标签和关键观点；
- 查看单条视频的完整知识内容；
- 支持文本、Markdown 和 JSON 输出。

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

## 技术路线

| 模块 | 技术 |
| --- | --- |
| 音频处理 | FFmpeg |
| 语音识别 | Faster-Whisper |
| AI 分析 | DeepSeek |
| 持久化 | MySQL |
| 任务运行时 | Redis |
| 后端与 CLI | Python / Typer |

向量检索方案将在真实数据和查询需求稳定后确定，当前不提前绑定。

## 开发路线

### 第一阶段：内容接入与音频基础能力

- [x] 本地视频与 metadata 扫描
- [x] MySQL 去重与 Redis 入队
- [x] FFmpeg 音频提取
- [x] Windows 与 Docker 路径映射
- [x] `author.sec_uid` 稳定身份协议
- [ ] 可靠任务记录、重试和崩溃恢复

### 第二阶段：语音识别

- [x] Faster-Whisper 转写
- [x] 分段时间戳
- [x] 转写模型配置记录
- [ ] 转写失败自动恢复

### 第三阶段：内容理解

- [x] DeepSeek 摘要
- [x] 主题标签
- [x] 关键观点提取
- [ ] 分析结果版本化

### 第四阶段：知识查询

- [x] 创作者与视频查询
- [x] MySQL 关键词搜索
- [ ] 语义搜索
- [ ] 跨视频长期观点与主题分析

Web UI 在核心数据模型和查询能力继续稳定后建设。当前不优先实现多用户、知识图谱和复杂推荐。

## Docker 配置

项目通过 `.env` 读取 MySQL、Redis、Faster-Whisper 和 DeepSeek 配置。

核心配置示例：

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
```

不要把真实 `LLM_API_KEY` 提交到 GitHub。

Compose 会：

- 将宿主机视频目录只读挂载到 `/data/douyin`；
- 将音频输出目录挂载到 `/data/audio`；
- 通过 `host.docker.internal` 连接宿主机 MySQL 和 Redis；
- 使用 Docker volume 缓存 Whisper 模型。

## 运行全链路

构建镜像：

```powershell
docker compose build
```

只读扫描：

```powershell
docker compose run --rm echolens scan
```

入库并入队：

```powershell
docker compose run --rm echolens scan --enqueue
```

分阶段运行：

```powershell
docker compose run --rm echolens worker --max-tasks 40
docker compose run --rm echolens transcribe --max-tasks 40
docker compose run --rm echolens analyze --max-tasks 40
```

也可以依次处理所有当前可用任务：

```powershell
docker compose run --rm echolens pipeline --max-tasks 40
```

状态流：

```text
queued
→ processing
→ audio_done
→ transcribing
→ transcribed
→ analyzing
→ done
```

当前失败状态包括：

```text
transcription_failed
analysis_failed
```

具体错误保存在 `videos.error_message`，当前不做自动重试。

## 查询知识

查看创作者：

```powershell
docker compose run --rm echolens knowledge creators
```

列出已完成内容：

```powershell
docker compose run --rm echolens knowledge list --limit 20
```

按创作者或标签筛选：

```powershell
docker compose run --rm echolens knowledge list --creator "<sec_uid>"
docker compose run --rm echolens knowledge list --tag "人工智能"
```

关键词搜索：

```powershell
docker compose run --rm echolens knowledge search "大模型"
```

查看单条完整知识：

```powershell
docker compose run --rm echolens knowledge show "<video_id>"
```

JSON 输出：

```powershell
docker compose run --rm echolens knowledge show "<video_id>" --format json
```

完整说明见 [知识查询指南](docs/knowledge-query.md)。

## 数据库

新环境直接执行：

```text
scripts/mysql_schema.sql
```

旧环境迁移脚本保留在：

```text
scripts/mysql_audio_migration.sql
scripts/mysql_creator_identity_migration.sql
```

项目早期测试数据可以直接删库后使用最新 schema 重建，无需优先考虑迁移兼容。

## 当前边界

尚未实现：

- Web UI；
- 向量数据库和语义搜索；
- 跨视频 AI 问答；
- 创作者长期观点变化分析；
- 完整任务重试、租约和死信机制。

当前优先级仍是用真实数据完善完整产品链路，而不是提前建设复杂平台能力。

## 参与贡献

欢迎提交 Issue 和 Pull Request。

EchoLens 希望让隐藏在声音中的知识更容易被发现、理解和复用。

## 开源协议

待定
