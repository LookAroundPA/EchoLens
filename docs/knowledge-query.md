# EchoLens 知识查询

当前知识查询层直接读取 MySQL 中已经完成全链路处理的数据：

```text
videos.status = done
+ transcripts
+ analyses
```

它是只读功能，不会修改视频状态、转写结果或分析结果。

## 查看创作者

```powershell
docker compose run --rm echolens knowledge creators
```

输出每个创作者的：

- 平台；
- `sec_uid`；
- 昵称；
- 视频总数；
- 已完成分析数量。

JSON 输出：

```powershell
docker compose run --rm echolens knowledge creators --format json
```

## 列出知识条目

```powershell
docker compose run --rm echolens knowledge list --limit 20
```

按创作者筛选：

```powershell
docker compose run --rm echolens knowledge list --creator "<sec_uid>"
```

按 DeepSeek 生成的精确标签筛选：

```powershell
docker compose run --rm echolens knowledge list --tag "人工智能"
```

支持 `text`、`markdown` 和 `json` 输出：

```powershell
docker compose run --rm echolens knowledge list --format markdown
docker compose run --rm echolens knowledge list --format json
```

## 关键词搜索

```powershell
docker compose run --rm echolens knowledge search "关键词"
```

搜索范围包括：

- 视频描述；
- 完整转写；
- 摘要；
- 标签；
- 关键观点。

可以同时限制创作者和标签：

```powershell
docker compose run --rm echolens knowledge search "大模型" `
  --creator "<sec_uid>" `
  --tag "人工智能" `
  --limit 20
```

当前搜索使用 MySQL `LIKE`，目标是先打通知识读取链路，不是语义向量搜索。

## 查看单条完整知识

```powershell
docker compose run --rm echolens knowledge show "<video_id>"
```

默认 Markdown 输出包含：

- 创作者和视频身份；
- 视频描述；
- DeepSeek 摘要；
- 标签；
- 关键观点；
- 完整 Faster-Whisper 转写。

JSON 输出：

```powershell
docker compose run --rm echolens knowledge show "<video_id>" --format json
```

如果不同创作者下存在相同 `video_id`，命令会要求显式提供：

```powershell
docker compose run --rm echolens knowledge show "<video_id>" --creator "<sec_uid>"
```

## 当前边界

当前阶段没有实现：

- Web UI；
- 向量数据库；
- 语义相似度搜索；
- 自动问答；
- 跨视频综合结论生成。

这些能力应在真实知识数据持续积累后继续建设。
