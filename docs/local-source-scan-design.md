# EchoLens 本地视频目录扫描设计

## 1. 背景

MVP 阶段，抖音视频采集由外部服务负责。

EchoLens 不直接调用抖音平台，只扫描部署机上的本地视频目录。

根目录：

```text
D:\BaiduNetdiskDownload\dy src
```

目录约定：

```text
D:\BaiduNetdiskDownload\dy src\
├── 博主A\
│   ├── douyin.wtf_douyin_738xxxx.mp4
│   └── douyin.wtf_douyin_738xxxx.mp4.json
│
└── 博主B\
    ├── douyin.wtf_douyin_740xxxx.mp4
    └── douyin.wtf_douyin_740xxxx.mp4.json
```

每个视频文件旁边必须有一个同名元数据文件：

```text
<video_file>.json
```

示例：

```text
douyin.wtf_douyin_738xxxx.mp4
douyin.wtf_douyin_738xxxx.mp4.json
```

---

# 2. 设计目标

扫描模块负责：

- 发现本地新增视频
- 读取同名 `.mp4.json` 元数据文件
- 识别创作者与视频唯一 ID
- 避免重复处理
- 避免处理下载中的文件
- 将任务写入 Redis 队列
- 将状态写入 MySQL

---

# 3. 元数据文件协议

每个视频对应一个同名 JSON 元数据文件。

示例：

```json
{
  "video_id": "738xxxx",
  "author_id": "author_xxx",
  "platform": "douyin",
  "type": "video",
  "desc": "视频描述",
  "create_time": 1234567890,
  "with_watermark": false,
  "file_name": "douyin.wtf_douyin_738xxxx.mp4",
  "file_path": "/app/download/博主ID/douyin.wtf_douyin_738xxxx.mp4",
  "file_size": 12345678,
  "file_mtime": 1234567890.123,
  "downloaded_at": "2026-07-10T12:00:00"
}
```

## 必需字段

```text
video_id
author_id
platform
type
file_name
file_size
file_mtime
downloaded_at
```

## 可选字段

```text
desc
create_time
with_watermark
file_path
```

注意：

`file_path` 可能是采集服务容器内路径，不一定等于 EchoLens 在 Windows 部署机上看到的真实路径。

EchoLens 应以扫描到的本地 `.mp4` 路径作为最终 `source_path`。

---

# 4. 去重策略

## 4.1 主去重键

MVP 阶段主去重键：

```text
platform + author_id + video_id
```

原因：

- `video_id` 表示平台内视频唯一标识
- `author_id` 表示创作者来源
- `platform` 保留未来多平台扩展空间

## 4.2 辅助指纹

辅助字段：

```text
source_path
file_name
file_size
file_mtime
```

用途：

- 排查文件变更
- 处理异常元数据
- 辅助定位本地文件

不建议 MVP 阶段默认计算完整文件 hash，因为视频文件较大，成本高。

---

# 5. 扫描策略

## 5.1 mtime 快速过滤

使用 `.mp4` 文件修改时间作为扫描加速手段。

```text
mtime > last_scan_time - buffer
```

注意：

mtime 只用于减少扫描范围，不作为最终去重依据。

## 5.2 JSON 元数据优先

扫描到 `.mp4` 后，优先读取：

```text
<video_file>.json
```

如果元数据存在且合法，则使用其中的：

```text
video_id
author_id
platform
create_time
desc
file_size
file_mtime
downloaded_at
```

如果元数据缺失或解析失败，本轮跳过该视频，并记录错误。

MVP 不再依赖从文件名解析 `video_id` 作为主路径。

---

# 6. 文件稳定性检查

为避免处理正在下载的视频，需要做稳定性检查。

推荐规则：

1. `.mp4` 文件必须存在。
2. `.mp4.json` 文件必须存在。
3. 文件最近修改时间距离当前时间小于 30 秒，跳过。
4. 可选：间隔数秒检查文件大小是否变化。
5. 文件和元数据都稳定后再加入处理队列。

---

# 7. MySQL 表设计草案

## creators

```text
id
platform
author_id
creator_name
source_dir
created_at
updated_at
```

建议：

```text
unique(platform, author_id)
```

## videos

```text
id
platform
video_id
author_id
creator_id
source_path
file_name
file_size
file_mtime
desc
create_time
downloaded_at
status
created_at
updated_at
processed_at
error_message
```

建议：

```text
unique(platform, author_id, video_id)
```

---

# 8. Redis 队列设计

推荐队列：

```text
echolens:queue:video
```

任务内容：

```json
{
  "video_id": "738xxxx",
  "author_id": "author_xxx",
  "platform": "douyin",
  "creator_id": 1,
  "video_db_id": 1001,
  "source_path": "D:\\BaiduNetdiskDownload\\dy src\\博主A\\douyin.wtf_douyin_738xxxx.mp4"
}
```

---

# 9. 状态设计

视频处理状态：

```text
pending
queued
processing
done
failed
skipped
```

含义：

- pending：已发现，等待入队
- queued：已推入 Redis 队列
- processing：处理中
- done：处理完成
- failed：处理失败
- skipped：跳过

---

# 10. 扫描流程

```text
读取 DOUYIN_SOURCE_DIR
        ↓
遍历博主子目录
        ↓
递归查找 .mp4 文件
        ↓
mtime 快速过滤
        ↓
检查 .mp4.json 是否存在
        ↓
读取并校验元数据
        ↓
文件稳定性检查
        ↓
用 platform + author_id + video_id 查询 MySQL
        ↓
不存在则插入 creators / videos
        ↓
推送 Redis 队列
        ↓
更新 videos.status = queued
```

---

# 11. 失败处理

如果 `.mp4.json` 缺失：

- 本轮跳过
- 记录 `metadata_missing`
- 下轮继续扫描

如果 `.mp4.json` 解析失败：

- 本轮跳过
- 记录 `metadata_parse_failed`

如果必需字段缺失：

- 本轮跳过
- 记录 `metadata_invalid`

如果文件正在下载：

- 本轮跳过
- 下轮继续扫描

如果 Redis 推送失败：

- MySQL 保持 pending
- 后续可重新推送

---

# 12. MVP 验收标准

扫描模块满足：

1. 能扫描固定根目录下的博主子目录
2. 能发现 `.mp4` 文件
3. 能读取同名 `.mp4.json` 元数据
4. 能用 `platform + author_id + video_id` 去重
5. 能将新增视频写入 MySQL
6. 能将处理任务推入 Redis
7. 能避免重复入队
8. 能跳过正在下载或元数据不完整的文件
