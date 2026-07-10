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
│   └── douyin.wtf_douyin_739xxxx.mp4
│
└── 博主B\
    ├── douyin.wtf_douyin_740xxxx.mp4
    └── douyin.wtf_douyin_741xxxx.mp4
```

---

# 2. 设计目标

扫描模块负责：

- 发现本地新增视频
- 识别创作者目录
- 从文件名解析 video_id
- 避免重复处理
- 避免处理下载中的文件
- 将任务写入 Redis 队列
- 将状态写入 MySQL

---

# 3. 去重策略

## 3.1 不使用文件名作为唯一依据

文件名可能变化，因此不能仅靠文件名去重。

## 3.2 优先使用 video_id

如果文件名包含稳定视频 ID，则以 video_id 作为主去重依据。

示例：

```text
douyin.wtf_douyin_738xxxx.mp4
```

解析出：

```text
video_id = 738xxxx
```

## 3.3 辅助指纹

辅助字段：

- file_path
- file_size
- file_mtime

不建议 MVP 阶段默认计算完整文件 hash，因为视频文件较大，成本高。

---

# 4. 扫描策略

## 4.1 mtime 快速过滤

使用文件修改时间作为扫描加速手段。

```text
mtime > last_scan_time - buffer
```

注意：

mtime 只用于减少扫描范围，不作为最终去重依据。

## 4.2 MySQL 最终去重

最终是否处理，由 MySQL 中的 videos 表决定。

判断优先级：

```text
video_id
    ↓
file_path + file_size + file_mtime
```

---

# 5. 文件稳定性检查

为避免处理正在下载的视频，需要做稳定性检查。

推荐规则：

1. 文件最近修改时间距离当前时间小于 30 秒，跳过。
2. 可选：间隔数秒检查文件大小是否变化。
3. 文件稳定后再加入处理队列。

---

# 6. MySQL 表设计草案

## creators

```text
id
creator_name
source_dir
created_at
updated_at
```

## videos

```text
id
video_id
creator_id
file_path
file_name
file_size
file_mtime
status
created_at
updated_at
processed_at
error_message
```

建议：

```text
unique(video_id)
```

如果 video_id 解析失败，则使用：

```text
file_path + file_size + file_mtime
```

作为辅助去重依据。

---

# 7. Redis 队列设计

推荐队列：

```text
echolens:queue:video
```

任务内容：

```json
{
  "video_id": "738xxxx",
  "creator_id": 1,
  "file_path": "D:\\BaiduNetdiskDownload\\dy src\\博主A\\douyin.wtf_douyin_738xxxx.mp4"
}
```

---

# 8. 状态设计

视频处理状态：

```text
pending
processing
done
failed
skipped
```

含义：

- pending：已发现，等待处理
- processing：处理中
- done：处理完成
- failed：处理失败
- skipped：跳过

---

# 9. 扫描流程

```text
读取 DOUYIN_SOURCE_DIR
        ↓
遍历博主子目录
        ↓
递归查找 .mp4 文件
        ↓
mtime 快速过滤
        ↓
文件稳定性检查
        ↓
解析 video_id
        ↓
查询 MySQL 是否已存在
        ↓
不存在则插入 videos 表
        ↓
推送 Redis 队列
```

---

# 10. 失败处理

如果 video_id 解析失败：

- 仍然允许入库
- 标记 `video_id_parse_failed`
- 使用文件指纹辅助去重

如果文件正在下载：

- 本轮跳过
- 下轮继续扫描

如果 Redis 推送失败：

- MySQL 保持 pending
- 后续可重新推送

---

# 11. MVP 验收标准

扫描模块满足：

1. 能扫描固定根目录下的博主子目录
2. 能发现 `.mp4` 文件
3. 能解析常见文件名中的 video_id
4. 能将新增视频写入 MySQL
5. 能将处理任务推入 Redis
6. 能避免重复入队
7. 能跳过正在下载的文件
