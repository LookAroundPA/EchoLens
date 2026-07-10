# EchoLens 数据库与任务流设计

## 1. 设计目标

本文定义 EchoLens MVP 阶段的数据存储、任务队列和状态流转。

当前部署环境：

- MySQL：持久化数据
- Redis：任务队列与运行时锁
- Windows 本地视频目录：保存采集侧落盘的视频与元数据

MVP 不再使用 SQLite 作为主存储。

---

# 2. 总体数据流

```text
本地视频目录
    ↓
Scanner
    ↓
MySQL 写入 creators / videos
    ↓
Redis 推送处理任务
    ↓
Worker 消费任务
    ↓
FFmpeg 提取音频
    ↓
Faster-Whisper 转写
    ↓
LLM 分析
    ↓
MySQL 写入 transcripts / analyses
```

---

# 3. 存储职责划分

## MySQL

负责持久化业务数据：

- 创作者信息
- 视频元数据
- 处理状态
- 转写结果
- AI 分析结果
- 错误信息

## Redis

负责运行时任务：

- 视频处理队列
- Worker 消费
- 临时锁
- 重试计数

## Local File Storage

负责保存文件：

- 原始视频
- 提取后的音频
- 可选中间文件

---

# 4. 核心数据表

## 4.1 creators

记录创作者信息。

关键字段：

| 字段 | 说明 |
| --- | --- |
| id | 内部主键 |
| platform | 平台，例如 douyin |
| author_id | 采集侧提供的博主 ID |
| creator_name | 创作者名称，可为空 |
| source_dir | 本地博主目录 |
| created_at | 创建时间 |
| updated_at | 更新时间 |

唯一约束：

```text
platform + author_id
```

---

## 4.2 videos

记录视频元数据和处理状态。

关键字段：

| 字段 | 说明 |
| --- | --- |
| id | 内部主键 |
| platform | 平台，例如 douyin |
| author_id | 创作者 ID |
| video_id | 视频 ID |
| creator_id | creators.id |
| type | 内容类型，默认 video |
| description | 视频描述 |
| create_time | 平台发布时间 |
| source_path | EchoLens 扫描到的本地视频路径 |
| metadata_path | 同名 .mp4.json 路径 |
| file_name | 文件名 |
| file_size | 文件大小 |
| file_mtime | 文件修改时间 |
| downloaded_at | 下载完成时间 |
| status | 视频处理状态 |
| error_message | 错误信息 |
| created_at | 创建时间 |
| updated_at | 更新时间 |
| processed_at | 处理完成时间 |

核心去重约束：

```text
platform + author_id + video_id
```

说明：

- `source_path` 以 EchoLens 实际扫描到的 Windows 本地路径为准。
- `.mp4.json` 中的 `file_path` 可能是采集服务内部路径，不作为 EchoLens 本地路径依据。

---

## 4.3 processing_jobs

记录任务执行过程。

关键字段：

| 字段 | 说明 |
| --- | --- |
| id | 内部主键 |
| video_db_id | videos.id |
| job_type | 任务类型 |
| status | 任务状态 |
| retry_count | 重试次数 |
| started_at | 开始时间 |
| finished_at | 结束时间 |
| error_message | 错误信息 |
| created_at | 创建时间 |
| updated_at | 更新时间 |

任务类型：

```text
extract_audio
transcribe_audio
analyze_text
```

---

## 4.4 transcripts

记录语音转写结果。

关键字段：

| 字段 | 说明 |
| --- | --- |
| id | 内部主键 |
| video_db_id | videos.id |
| language | 识别语言 |
| model_name | 转写模型 |
| text | 完整转写文本 |
| segments_json | 带时间戳的分段结果 |
| audio_path | 提取后的音频路径 |
| created_at | 创建时间 |
| updated_at | 更新时间 |

约束：

```text
一个视频默认只保留一份当前转写结果
```

---

## 4.5 analyses

记录 AI 分析结果。

关键字段：

| 字段 | 说明 |
| --- | --- |
| id | 内部主键 |
| video_db_id | videos.id |
| transcript_id | transcripts.id |
| model_provider | 模型服务商 |
| model_name | 模型名称 |
| summary | 内容摘要 |
| tags_json | 标签数组 |
| key_points_json | 关键观点数组 |
| raw_result_json | 模型原始结构化结果 |
| created_at | 创建时间 |
| updated_at | 更新时间 |

---

# 5. 视频状态设计

`videos.status` 使用以下状态：

```text
pending
queued
processing
done
failed
skipped
```

状态含义：

| 状态 | 含义 |
| --- | --- |
| pending | 已发现，尚未入队 |
| queued | 已推入 Redis 队列 |
| processing | Worker 正在处理 |
| done | 处理完成 |
| failed | 处理失败 |
| skipped | 主动跳过 |

正常流转：

```text
pending → queued → processing → done
```

失败流转：

```text
processing → failed
```

---

# 6. Redis 队列设计

## 6.1 队列命名

```text
echolens:queue:video
```

用于待处理视频任务。

## 6.2 任务内容

任务中至少包含：

```json
{
  "video_db_id": 1,
  "platform": "douyin",
  "author_id": "123456",
  "video_id": "738xxxx",
  "source_path": "D:\\BaiduNetdiskDownload\\dy src\\123456\\douyin.wtf_douyin_738xxxx.mp4",
  "metadata_path": "D:\\BaiduNetdiskDownload\\dy src\\123456\\douyin.wtf_douyin_738xxxx.mp4.json"
}
```

---

# 7. Redis 锁设计

为避免多个 Worker 重复处理同一个视频，使用视频级锁：

```text
echolens:lock:video:{video_db_id}
```

建议：

- 获取锁成功才处理
- 处理完成后释放锁
- 锁必须设置过期时间，避免 Worker 异常退出后永久占用

---

# 8. Scanner 写入流程

```text
扫描 .mp4
    ↓
读取 .mp4.json
    ↓
校验 platform / author_id / video_id
    ↓
检查文件稳定性
    ↓
upsert creators
    ↓
insert videos
    ↓
成功插入新 video 后推送 Redis
    ↓
更新 videos.status = queued
```

规则：

- 如果 `platform + author_id + video_id` 已存在，不重复入队。
- 如果 Redis 推送失败，保留 `pending` 状态，后续可以重新入队。

---

# 9. Worker 处理流程

```text
从 Redis 获取任务
    ↓
获取视频锁
    ↓
更新 videos.status = processing
    ↓
记录 processing_jobs
    ↓
FFmpeg 提取音频
    ↓
Faster-Whisper 转写
    ↓
写入 transcripts
    ↓
LLM 分析
    ↓
写入 analyses
    ↓
更新 videos.status = done
```

失败处理：

```text
记录 error_message
    ↓
增加 retry_count
    ↓
更新状态为 failed
```

---

# 10. 查询能力

MVP 阶段先支持：

- 按创作者查询视频
- 按关键词搜索 transcript
- 按标签查询 analysis
- 查看失败任务

后续扩展：

- Embedding
- 向量检索
- AI 问答
- 趋势分析

---

# 11. MVP 验收标准

数据库与任务流满足：

1. 能保存创作者信息
2. 能保存视频元数据
3. 能用 `platform + author_id + video_id` 去重
4. 能把新视频推入 Redis 队列
5. 能记录处理状态
6. 能保存转写文本
7. 能保存 AI 分析结果
8. 能记录失败原因并支持后续重试
