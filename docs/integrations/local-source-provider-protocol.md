# 本地内容提供方对接协议

协议版本：`1.0`

## 1. 目的

本文定义外部内容提供方与 EchoLens 之间的本地文件交付协议。

外部服务负责获取视频并落盘。EchoLens 不直接调用抖音，也不维护外部采集服务。EchoLens 只读取本地目录中的视频文件及其同名 metadata JSON，并将其作为语音理解和知识沉淀流程的输入。

## 2. 交付目录

默认根目录：

```text
D:\BaiduNetdiskDownload\dy src
```

目录结构：

```text
<root>\<provider_author_directory>\<video_file>.mp4
<root>\<provider_author_directory>\<video_file>.mp4.json
```

示例：

```text
D:\BaiduNetdiskDownload\dy src\黄士铨看世界_1116730602555796\
├── douyin.wtf_douyin_7103469551442038030.mp4
└── douyin.wtf_douyin_7103469551442038030.mp4.json
```

metadata 文件名必须是完整视频文件名后追加 `.json`。

## 3. 创作者身份规则

EchoLens 使用以下字段作为创作者稳定身份：

```text
author.sec_uid
```

唯一约束：

```text
platform + author.sec_uid
```

视频去重约束：

```text
platform + author.sec_uid + video_id
```

其他创作者字段仅作辅助信息：

| 字段 | 含义 | 是否参与去重 |
| --- | --- | --- |
| `author.sec_uid` | 平台稳定创作者标识 | 是 |
| `author.uid` | 平台数字 UID | 否 |
| `author.nickname` | 当前昵称，可能变化 | 否 |
| 顶层 `author_id` | 内容提供方的作者目录或组合标识，可能变化 | 否 |

`author.sec_uid` 缺失、为空或类型错误时，EchoLens 必须跳过该文件，不允许回退到 `author.uid` 或顶层 `author_id`。

## 4. 必需字段

```json
{
  "video_id": "7103469551442038030",
  "author_id": "黄士铨看世界_1116730602555796",
  "author": {
    "sec_uid": "MS4wLjABAAAARGJtMMMujtgxbnl18CQHeUiTdopr5C--P4I3t80KvumwcZw2di4vfeteEnBhYI-x"
  },
  "platform": "douyin",
  "type": "video",
  "file_name": "douyin.wtf_douyin_7103469551442038030.mp4"
}
```

字段定义：

| 字段 | 类型 | 规则 |
| --- | --- | --- |
| `video_id` | string | 非空 |
| `author_id` | string | 非空，作为提供方原始标识保存 |
| `author` | object | 必须存在 |
| `author.sec_uid` | string | 非空，创作者主标识 |
| `platform` | string | 非空，当前为 `douyin` |
| `type` | string | 当前必须为 `video` |
| `file_name` | string | 非空 |

## 5. 可选字段

```text
author.uid
author.nickname
desc
create_time
statistics
with_watermark
file_path
file_size
file_mtime
downloaded_at
```

`author` 和 metadata 顶层允许出现提供方扩展字段。EchoLens 必须忽略不认识的字段，不得因额外字段拒绝文件。

### statistics

`statistics` 是内容提供方生成 metadata 时的互动数据快照，可包含：

```text
recommend_count
comment_count
digg_count
admire_count
play_count
share_count
collect_count
```

某个统计字段缺失或为 `0` 时，EchoLens 不推断其业务含义，只保存提供方原始值。

## 6. 路径规则

metadata 中的 `file_path` 可能是提供方容器内路径，例如：

```text
/app/download/黄士铨看世界_1116730602555796/video.mp4
```

EchoLens 不使用该字段定位本地视频。最终视频路径必须以 Scanner 实际发现的文件路径为准。

## 7. 文件完整性

EchoLens 只有在以下条件同时满足时才接收视频：

1. `.mp4` 文件存在；
2. 同名 `.mp4.json` 文件存在；
3. 视频文件超过配置的稳定时间窗口；
4. metadata 是合法 JSON；
5. metadata 符合本协议；
6. `author.sec_uid` 是非空字符串。

当前协议不假定提供方具备原子写入能力。EchoLens 通过文件稳定时间和后续重复扫描避免处理尚未完成的文件。

## 8. 协议错误

| 错误码 | 含义 |
| --- | --- |
| `metadata_missing` | 缺少同名 metadata 文件 |
| `metadata_read_failed` | metadata 无法读取 |
| `metadata_parse_failed` | metadata 不是合法 JSON |
| `metadata_protocol_error` | metadata 不符合协议，包括缺少 `author.sec_uid` |

协议错误不会写入处理队列。Scanner 会跳过文件、输出结构化错误，并在下一次扫描时重新检查。

缺少稳定身份时的标准错误信息：

```text
metadata_protocol_error: author.sec_uid is required and must be a non-empty string
```

## 9. 数据保留

EchoLens 规范化保存以下身份字段：

```text
creator_sec_uid      <- author.sec_uid
provider_author_id   <- 顶层 author_id
author_uid           <- author.uid
creator_name         <- author.nickname
```

同时保存 `statistics` 和完整 metadata JSON 快照，以便审计、兼容提供方字段变化和后续数据补充。

## 10. 兼容性规则

- 本协议新增可选字段属于向后兼容变更。
- 删除或修改必需字段属于不兼容变更。
- 改变 `author.sec_uid` 的身份语义属于不兼容变更。
- EchoLens 不从昵称、目录名或顶层 `author_id` 推导稳定身份。
- 协议升级时必须更新本文档、Pydantic 模型和扫描测试。
