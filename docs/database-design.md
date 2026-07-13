# EchoLens 数据库与任务流设计

## 1. 设计目标

MySQL 是 EchoLens 业务状态和处理结果的权威存储。Redis 只承担任务投递、领取、锁和短期运行时状态。

数据库设计必须支持：

- 稳定识别同一创作者；
- 防止视频重复处理；
- 保存外部提供方的原始 metadata；
- 记录音频、转写和分析阶段结果；
- 支持失败重试、任务恢复和结果版本演进；
- 不依赖外部采集服务容器路径。

当前已实现链路：

```text
scan → queued → processing → audio_done
```

目标完整链路：

```text
scan
  → audio_queued
  → audio_processing
  → audio_done
  → transcription_queued
  → transcribing
  → transcribed
  → analysis_queued
  → analyzing
  → done
```

目标状态与任务系统会在后续阶段逐步落地。本文明确区分当前字段和后续扩展方向。

## 2. 存储职责

### MySQL

负责持久化：

- 创作者稳定身份；
- 视频和提供方 metadata；
- 处理状态；
- 任务执行历史；
- 转写文本和时间戳；
- AI 分析结果；
- 错误、重试和版本信息。

### Redis

负责运行时能力：

- ready queue；
- processing queue；
- Worker 锁；
- 短期心跳或租约；
- 延迟重试和死信投递。

Redis 不作为业务结果的唯一存储。

### 本地文件系统

负责保存：

- 外部服务交付的原始视频；
- 同名 metadata JSON；
- FFmpeg 提取后的 WAV；
- 后续可能产生的字幕或可重建中间文件。

## 3. 创作者身份

### 3.1 权威身份字段

EchoLens 使用：

```text
author.sec_uid
```

作为抖音创作者稳定标识。

数据库映射：

```text
creators.sec_uid          <- author.sec_uid
creators.platform_uid     <- author.uid
creators.provider_author_id <- 顶层 author_id
creators.creator_name     <- author.nickname
```

唯一约束：

```text
platform + sec_uid
```

以下字段不参与创作者去重：

- 昵称；
- 本地目录名；
- `author.uid`；
- 顶层 `author_id`。

缺少 `author.sec_uid` 的 metadata 不允许入库。

## 4. 核心表

## 4.1 creators

记录创作者当前身份和来源信息。

| 字段 | 类型/含义 |
| --- | --- |
| `id` | EchoLens 内部主键 |
| `platform` | 平台，例如 `douyin` |
| `sec_uid` | 稳定创作者标识 |
| `platform_uid` | 提供方 `author.uid`，辅助字段 |
| `provider_author_id` | 顶层 `author_id`，辅助字段 |
| `creator_name` | 当前昵称，可变化 |
| `source_dir` | 最近一次扫描到的本地目录 |
| `created_at` | 创建时间 |
| `updated_at` | 更新时间 |

唯一索引：

```text
uq_creators_platform_sec_uid(platform, sec_uid)
```

辅助索引：

```text
(platform, platform_uid)
(platform, provider_author_id)
```

## 4.2 videos

记录视频身份、文件位置、提供方 metadata 和总流程状态。

| 字段 | 类型/含义 |
| --- | --- |
| `id` | EchoLens 内部主键 |
| `platform` | 平台 |
| `creator_sec_uid` | 创作者稳定标识 |
| `provider_author_id` | 顶层 `author_id` |
| `author_uid` | `author.uid` |
| `video_id` | 平台视频标识 |
| `creator_id` | `creators.id` |
| `file_path` | EchoLens 实际扫描到的视频路径 |
| `metadata_path` | 同名 sidecar JSON 路径 |
| `file_name` | 实际视频文件名 |
| `file_size` | 实际文件大小 |
| `file_mtime` | 实际文件 mtime |
| `description` | 提供方 `desc` |
| `source_create_time` | 提供方 `create_time` 原值 |
| `downloaded_at` | 提供方下载时间原值 |
| `statistics_json` | 互动统计快照 |
| `metadata_json` | 完整 metadata JSON 快照 |
| `status` | 当前处理状态 |
| `audio_path` | WAV 路径 |
| `audio_size` | WAV 大小 |
| `audio_created_at` | 音频完成时间 |
| `error_message` | 当前错误摘要 |
| `created_at` | 创建时间 |
| `updated_at` | 更新时间 |
| `processed_at` | 现阶段兼容字段，当前在音频完成时写入 |

视频唯一约束：

```text
platform + creator_sec_uid + video_id
```

索引：

```text
uq_videos_platform_creator_video(platform, creator_sec_uid, video_id)
idx_videos_creator_id(creator_id)
idx_videos_provider_author(platform, provider_author_id)
idx_videos_status(status)
```

路径规则：

- `file_path` 以 Scanner 实际发现路径为准；
- metadata 中 `/app/download/...` 一类容器路径不作为本地路径；
- Worker 可以根据配置把历史 Windows 路径映射到 Docker 挂载目录。

### processed_at 的后续处理

`processed_at` 当前由音频阶段写入，语义不够准确。完整链路实现时应迁移为明确字段：

```text
transcribed_at
analyzed_at
completed_at
```

在迁移完成前不得把 `processed_at` 解释为整个知识处理链路已经完成。

## 4.3 processing_jobs

记录每个处理阶段的执行历史。

当前表已存在，但音频 Worker 尚未完整接入。

当前字段：

| 字段 | 含义 |
| --- | --- |
| `id` | 主键 |
| `video_id` | `videos.id` |
| `job_type` | 任务类型 |
| `status` | 执行状态 |
| `retry_count` | 重试次数 |
| `started_at` | 开始时间 |
| `finished_at` | 结束时间 |
| `error_message` | 错误信息 |
| `created_at` | 创建时间 |
| `updated_at` | 更新时间 |

目标任务类型：

```text
extract_audio
transcribe_audio
analyze_text
```

完整任务系统还需要增加或明确：

```text
attempt
max_attempts
reserved_at
heartbeat_at
available_at
worker_id
error_type
result_version
```

这些字段将在任务系统重构时通过独立迁移加入，不在创作者身份迁移中提前修改。

## 4.4 transcripts

记录语音转写结果。

当前字段：

| 字段 | 含义 |
| --- | --- |
| `video_id` | 视频 |
| `transcript_text` | 完整文本 |
| `segments_json` | 时间戳分段 |
| `language` | 检测语言 |
| `model_name` | 模型名称 |
| `created_at` | 创建时间 |
| `updated_at` | 更新时间 |

当前唯一约束为一个视频一份转写：

```text
UNIQUE(video_id)
```

完整系统需要支持重新转写和历史版本，因此后续应演进为：

```text
video_id + version
is_current
model_provider
model_revision
compute_type
transcription_config_json
```

该版本化改造将在 Faster-Whisper 阶段设计并迁移。

## 4.5 analyses

记录 AI 内容理解结果。

当前字段：

```text
video_id
summary
tags_json
key_points_json
model_name
created_at
updated_at
```

完整系统后续需要支持：

- 分析版本；
- Prompt 版本；
- 模型提供商和模型版本；
- 结构化观点；
- 主题和标签规范化；
- 重新分析时保留历史结果。

在转写阶段稳定之前不提前扩展复杂知识图谱或推荐字段。

## 5. metadata 保存策略

数据库同时保存规范化字段和完整 metadata JSON。

规范化字段用于：

- 去重；
- 查询；
- 索引；
- 任务调度。

`metadata_json` 用于：

- 审计提供方输出；
- 保留未知扩展字段；
- 后续补录作者和统计信息；
- 协议升级；
- 排查字段语义变化。

`statistics_json` 是便于独立读取的互动统计快照。统计值只按提供方原值保存，不推断 `0` 或缺失的业务含义。

## 6. 当前入库流程

```text
Scanner 发现合法视频
        ↓
解析 author.sec_uid
        ↓
ensure_creator(platform, sec_uid)
        ↓
检查 platform + sec_uid + video_id
        ↓
写入 videos（pending）
        ↓
推送 Redis
        ↓
更新 videos.status = queued
```

当前 MySQL 与 Redis 不是分布式原子事务。完整任务系统需要增加 reconciliation/outbox 能力，避免数据库与队列状态永久不一致。

## 7. 旧数据迁移

已有数据库先执行：

```text
scripts/mysql_creator_identity_migration.sql
```

迁移动作：

1. `creators.author_id` 重命名为 `provider_author_id`；
2. `videos.author_id` 重命名为 `provider_author_id`；
3. 增加 `creators.sec_uid` 和 `platform_uid`；
4. 增加 `videos.creator_sec_uid` 和 `author_uid`；
5. 增加 `statistics_json` 和 `metadata_json`；
6. 唯一索引切换到 `sec_uid`。

为避免破坏已有 8 条记录，迁移脚本不会伪造 sec_uid。

执行迁移后运行：

```powershell
echolens scan --enqueue
```

Repository 会：

- 根据顶层 `provider_author_id` 将旧 creator 行回填到真实 `sec_uid`；
- 根据同一 `creator_id + video_id` 回填旧 video 行；
- 更新辅助身份和 metadata；
- 把旧视频视为已存在；
- 不重新推送已经存在的视频任务。

回填完成后应检查：

```sql
SELECT COUNT(*) FROM creators WHERE sec_uid IS NULL;
SELECT COUNT(*) FROM videos WHERE creator_sec_uid IS NULL;
```

两项都应为 `0`。如果仍存在空值，说明对应 sidecar 缺失、协议不合法，或旧记录无法与当前提供方身份安全匹配，需要人工处理，不能自动猜测。

## 8. 当前状态流

当前代码使用：

```text
pending → queued → processing → audio_done
```

失败时当前 Worker 会回到：

```text
processing → queued
```

并保留 `error_message`。

该机制尚缺少：

- 最大重试次数；
- 延迟重试；
- 死信任务；
- processing 队列超时恢复；
- 心跳和租约；
- `processing_jobs` 执行记录。

这些是进入完整转写链路前的任务系统重构内容。

## 9. 下一阶段数据库工作

完成创作者身份迁移后，下一阶段按顺序处理：

1. 将 `processing_jobs` 接入音频 Worker；
2. 设计任务租约、重试和死信；
3. 将音频、转写和分析拆成独立阶段任务；
4. 版本化 transcripts；
5. 实现 `audio_done → transcribing → transcribed`；
6. 转写稳定后再设计 analyses 的正式版本模型。
