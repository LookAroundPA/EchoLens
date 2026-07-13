# EchoLens

> See beyond the sound.
>
> 穿透声音，洞察思想。

EchoLens 是一个 AI 驱动的语音内容理解与知识沉淀系统。

它将视频、播客、访谈、课程等音频内容转换为可搜索、可分析、可持续积累的知识资产。

EchoLens 不直接调用抖音，也不维护外部采集服务。外部服务负责把视频和 metadata 落盘，EchoLens 从本地目录开始完成音频处理、语音理解和知识沉淀。

## 项目愿景

互联网每天产生大量有价值的声音内容，但这些内容通常：

- 难以快速阅读
- 难以长期保存
- 难以关联分析
- 容易被时间淹没

EchoLens 希望构建一个从 **内容接入 → 声音理解 → 知识沉淀 → 智能洞察** 的 AI 内容基础设施。

## 核心流程

```text
本地内容源
    |
    v
音频提取
    |
    v
语音识别
    |
    v
文本理解
    |
    v
知识存储
    |
    v
AI 洞察
```

## 核心能力

### 内容源接入

- 扫描外部服务落盘的视频和同名 metadata
- 使用稳定创作者身份和视频 ID 去重
- 记录协议错误和文件状态
- 不依赖采集服务容器内路径

### 音频处理

- 从视频源提取音频
- 音频格式标准化
- 批量处理支持

### 语音识别

- Faster-Whisper 自动语音转文字
- 自动语言识别或指定语言
- 分段时间戳
- 转写文本和模型配置落库

### AI 内容理解

- 内容摘要
- 主题分类
- 关键观点提取
- 语义搜索

### 知识系统

将分散的声音内容沉淀为长期知识库。

你可以询问：

- 某个创作者长期关注哪些主题？
- 他的观点随着时间如何变化？
- 大量视频中有哪些共同观点？

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

完整协议见：

- [本地内容提供方对接协议](docs/integrations/local-source-provider-protocol.md)
- [本地内容源扫描设计](docs/local-source-scan-design.md)

## 技术路线

| 模块 | 技术 |
| --- | --- |
| 音频处理 | FFmpeg |
| 语音识别 | Faster-Whisper |
| AI 分析 | Large Language Models |
| 持久化 | MySQL |
| 任务运行时 | Redis |
| 后端 | Python |

向量检索方案将在转写、分析和查询模型稳定后确定，不在早期提前绑定。

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
- [x] 转写版本和模型配置记录
- [ ] 转写失败恢复

### 第三阶段：内容理解

- [ ] AI 摘要
- [ ] 主题标签
- [ ] 关键观点提取
- [ ] 分析结果版本化

### 第四阶段：知识查询

- [ ] 创作者与视频查询
- [ ] 全文搜索
- [ ] 语义搜索
- [ ] 长期观点与主题分析

Web UI 在核心链路、数据模型和查询 API 稳定并积累足够真实数据后开始建设。当前不优先实现多用户、知识图谱和复杂推荐。

## Docker 运行

项目通过 `.env` 读取 MySQL、Redis 和 Faster-Whisper 配置。Compose 会将宿主机视频目录只读挂载到容器，通过 `host.docker.internal` 连接宿主机服务，并使用 Docker volume 缓存 Whisper 模型。

构建镜像并执行只读扫描：

```powershell
docker compose build
docker compose run --rm echolens scan
```

扫描输出会同时列出合法视频和被跳过的协议问题。

确认扫描结果正确后，显式写入 MySQL 并推送 Redis 任务：

```powershell
docker compose run --rm echolens scan --enqueue
```

### 已有数据库迁移

已有数据库如果尚未增加音频字段，先执行：

```text
scripts/mysql_audio_migration.sql
```

然后执行稳定创作者身份迁移：

```text
scripts/mysql_creator_identity_migration.sql
```

迁移后再次运行：

```powershell
docker compose run --rm echolens scan --enqueue
```

已有 creator 和 video 会根据 sidecar metadata 回填 `author.sec_uid`，不会重新入队。回填完成后检查：

```sql
SELECT COUNT(*) FROM creators WHERE sec_uid IS NULL;
SELECT COUNT(*) FROM videos WHERE creator_sec_uid IS NULL;
```

两项都应为 `0`。

提取队列中的 WAV 音频：

```powershell
docker compose run --rm echolens worker --max-tasks 40
```

转写所有 `audio_done` 视频：

```powershell
docker compose run --rm echolens transcribe --max-tasks 40
```

首次转写会下载配置的 Whisper 模型，后续运行会复用 `echolens_model_cache` volume。默认 CPU 配置为：

```text
WHISPER_MODEL=large-v3
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
WHISPER_LANGUAGE=
WHISPER_BEAM_SIZE=5
WHISPER_VAD_FILTER=true
```

转写状态流：

```text
audio_done → transcribing → transcribed
```

失败时视频状态为 `transcription_failed`，具体原因写入 `videos.error_message`。当前不做自动重试。

验证结果：

```sql
SELECT status, COUNT(*) FROM videos GROUP BY status;
SELECT COUNT(*) FROM transcripts;
SELECT video_id, language, model_name, CHAR_LENGTH(transcript_text)
FROM transcripts
ORDER BY video_id;
```

直接执行 `docker compose up` 时默认只运行 `echolens scan`，不会入库、入队或转写。

## 参与贡献

欢迎提交 Issue 和 Pull Request。

EchoLens 希望探索如何让隐藏在声音中的人类知识，更容易被发现、理解和复用。

## 开源协议

待定
