# EchoLens 本地内容源扫描设计

## 1. 背景与边界

抖音视频采集由外部服务负责。EchoLens 不直接访问抖音平台，不维护采集服务，也不把自身定位为下载器。

本地扫描只是内容进入 EchoLens 的入口。后续核心价值来自音频处理、语音转写、内容理解和长期知识沉淀。

默认输入根目录：

```text
D:\BaiduNetdiskDownload\dy src
```

正式字段协议见：

```text
docs/integrations/local-source-provider-protocol.md
```

## 2. 输入目录约定

```text
D:\BaiduNetdiskDownload\dy src\
├── 提供方作者目录A\
│   ├── douyin.wtf_douyin_7103469551442038030.mp4
│   └── douyin.wtf_douyin_7103469551442038030.mp4.json
└── 提供方作者目录B\
    ├── douyin.wtf_douyin_740xxxx.mp4
    └── douyin.wtf_douyin_740xxxx.mp4.json
```

每个视频必须存在同名 sidecar metadata：

```text
<video_file>.mp4.json
```

## 3. 路径权威性

metadata 内的 `file_path` 可能是外部采集服务的容器路径，例如：

```text
/app/download/作者目录/video.mp4
```

EchoLens 不使用该字段定位本地文件。

路径优先级：

1. Scanner 实际发现的 `.mp4` 路径；
2. 数据库中保存的实际扫描路径；
3. Docker Worker 根据配置把历史 Windows 路径映射到运行时挂载目录。

## 4. 创作者身份规范化

外部 metadata 可能同时包含：

```text
顶层 author_id
author.uid
author.nickname
author.sec_uid
```

EchoLens 的稳定创作者标识只能使用：

```text
author.sec_uid
```

字段映射：

```text
creator_sec_uid    <- author.sec_uid
provider_author_id <- 顶层 author_id
author_uid         <- author.uid
creator_name       <- author.nickname
```

规则：

- `author.sec_uid` 必须存在且为非空字符串；
- 缺失时跳过文件并记录 `metadata_protocol_error`；
- 不允许回退到 `author.uid`；
- 不允许回退到顶层 `author_id`；
- 昵称和目录名称不参与身份判断。

## 5. 去重策略

### 5.1 创作者唯一键

```text
platform + creator_sec_uid
```

### 5.2 视频唯一键

```text
platform + creator_sec_uid + video_id
```

辅助字段：

```text
provider_author_id
author_uid
source_path
metadata_path
file_name
file_size
file_mtime
```

辅助字段用于追踪数据来源、迁移和排障，不作为主去重键。

## 6. 扫描流程

```text
读取 DOUYIN_SOURCE_DIR
        ↓
递归发现 .mp4
        ↓
检查视频稳定时间
        ↓
定位同名 .mp4.json
        ↓
读取并解析 JSON
        ↓
使用 Pydantic 校验提供方协议
        ↓
要求 author.sec_uid 非空
        ↓
规范化 LocalVideoItem
        ↓
dry-run 输出结果与问题
        ↓
可选：写入 MySQL 并推送 Redis
```

Scanner 始终以实际文件状态覆盖 metadata 中的以下字段：

```text
source_path
file_name
file_size
file_mtime
```

这样可以避免依赖采集服务容器路径或陈旧的文件属性。

## 7. 文件稳定性

为避免处理仍在写入的视频，当前使用：

```text
当前时间 - 视频 mtime >= SCAN_STABILITY_SECONDS
```

默认稳定时间为 30 秒。

当前实现不依赖提供方的原子写入保证。缺失 sidecar 或暂时不稳定的文件会在后续扫描中重新检查。

后续可增加：

- 视频与 metadata 双文件稳定性检查；
- 间隔采样文件大小；
- 提供方完成标记；
- 文件系统事件监听作为轮询补充。

## 8. 协议错误记录

Scanner 不再静默丢弃错误文件，而是产生结构化 `ScanIssue`：

```text
code
message
video_path
metadata_path
```

当前错误码：

| 错误码 | 含义 |
| --- | --- |
| `metadata_missing` | 缺少 sidecar metadata |
| `metadata_read_failed` | metadata 无法读取 |
| `metadata_parse_failed` | JSON 解析失败 |
| `metadata_protocol_error` | 字段不符合提供方协议 |

`echolens scan` 会输出：

```text
Discovered valid video items: N
Skipped source items: M
```

并逐条打印问题。协议错误不写入 MySQL，也不进入 Redis 队列。

## 9. 元数据保留

规范化对象保存：

```text
creator_sec_uid
provider_author_id
author_uid
creator_name
video_id
desc
create_time
downloaded_at
statistics
raw_metadata
```

写入数据库时保存：

- 身份规范化字段；
- `statistics_json`；
- 完整 `metadata_json` 快照。

保留原始快照用于：

- 审计数据提供方输出；
- 后续补充新字段；
- 协议升级；
- 排查身份变化和统计数据异常。

## 10. MySQL 写入与旧数据迁移

新数据库直接使用 `scripts/mysql_schema.sql`。

已有数据库需要先执行：

```text
scripts/mysql_creator_identity_migration.sql
```

迁移脚本会：

1. 把旧 `author_id` 重命名为 `provider_author_id`；
2. 增加 `sec_uid`、`creator_sec_uid` 和 `author_uid`；
3. 把唯一约束切换到 `sec_uid`；
4. 增加 statistics 和完整 metadata JSON 字段。

迁移后旧记录的 `sec_uid` 暂时为空。下一次执行：

```powershell
echolens scan --enqueue
```

Repository 会根据 sidecar metadata 回填旧 creator/video 记录。已存在的视频只更新身份字段，不重新入队。

## 11. Redis 任务内容

新任务至少包含：

```json
{
  "video_db_id": 1,
  "creator_db_id": 1,
  "platform": "douyin",
  "creator_sec_uid": "MS4wLjAB...",
  "provider_author_id": "昵称_数字UID",
  "video_id": "7103469551442038030",
  "source_path": "D:\\BaiduNetdiskDownload\\dy src\\...mp4",
  "metadata_path": "D:\\BaiduNetdiskDownload\\dy src\\...mp4.json"
}
```

Worker 的权威输入仍是 `video_db_id` 对应的 MySQL 记录，Redis payload 中的其他字段主要用于诊断。

## 12. 当前验收标准

扫描模块必须满足：

1. 能递归发现 `.mp4`；
2. 能读取同名 `.mp4.json`；
3. 能接受提供方额外字段；
4. 能从 `author.sec_uid` 取得稳定创作者身份；
5. 缺少 `author.sec_uid` 时跳过并记录协议错误；
6. 能以实际扫描路径覆盖 metadata 容器路径；
7. 能用 `platform + sec_uid + video_id` 去重；
8. 能安全回填旧数据库身份字段；
9. dry-run 不写数据库和 Redis；
10. `--enqueue` 只为新增视频创建任务。
