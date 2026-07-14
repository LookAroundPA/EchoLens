# 本地语义搜索与有来源问答

EchoLens 使用本地中文嵌入模型建立轻量语义索引，再由 DeepSeek V4 Pro 仅根据检索到的视频证据生成回答。

## 全链路

```text
已完成视频的转写分段、摘要、标签和关键观点
→ FastEmbed 本地生成向量
→ SQLite 保存向量与时间来源
→ 语义相似度 + 关键词混合排序
→ DeepSeek V4 Pro 整理证据
→ 回答中的 [S1] 引用可跳回视频和音频时间点
```

搜索和索引不调用 DeepSeek。只有提交问答时才会调用 `QA_MODEL`。

## 配置

```text
QA_MODEL=deepseek-v4-pro
QA_TEMPERATURE=0.1
QA_MAX_TOKENS=4096
QA_DEFAULT_SOURCES=8

SEMANTIC_MODEL=BAAI/bge-small-zh-v1.5
SEMANTIC_MODEL_CACHE_DIR=data/models/fastembed
SEMANTIC_INDEX_PATH=data/semantic/echolens.sqlite3
SEMANTIC_AUTO_SYNC=true
SEMANTIC_CHUNK_MAX_CHARS=420
SEMANTIC_CHUNK_MAX_SEGMENTS=3
SEMANTIC_MAX_CHUNKS_PER_VIDEO=2
SEMANTIC_MIN_SCORE=0.18
```

Docker Compose 会将模型缓存保存在 `echolens_model_cache`，将 SQLite 索引保存在 `echolens_semantic_data`。API 和 Worker 共享这两个 volume。

## 首次使用

重新构建后端镜像：

```powershell
docker compose up --build api job-worker
```

首次建立索引可以在“搜索”或“问答”页面点击“同步语义索引”，也可以执行：

```powershell
echolens knowledge semantic-sync
```

完全重建：

```powershell
echolens knowledge semantic-sync --rebuild
```

首次运行会下载本地嵌入模型。以后启动会复用缓存。

## 增量同步

每个视频的索引指纹包含：

- 嵌入模型与分块配置；
- 转写和分析更新时间；
- 时间戳分段；
- 摘要、标签和关键观点。

同步时只重新计算新增或修改的视频，并删除已经不再满足 `done` 条件的视频索引。默认 `SEMANTIC_AUTO_SYNC=true`，每次搜索或问答前会检查指纹，但未变化的视频不会重复生成向量。

## HTTP API

### 索引状态

```text
GET /api/semantic/status
```

### 混合语义搜索

```text
GET /api/semantic/search?q=<问题>&creator=<sec_uid>&tag=<标签>&limit=20
```

每个结果包含：

- 综合相关度；
- 语义相关度；
- 关键词相关度；
- 视频和创作者；
- 原始片段；
- `start/end/segmentIndex` 时间来源。

### 同步索引

```http
POST /api/semantic/actions/sync
Content-Type: application/json

{
  "rebuild": false
}
```

该接口创建 `semantic_index` 后台任务，由 `job-worker` 执行。

### 跨视频问答

```http
POST /api/ask
Content-Type: application/json

{
  "question": "这些视频对提高工作效率有哪些建议？",
  "creatorSecUid": null,
  "tag": null,
  "maxSources": 8,
  "thinking": false
}
```

`thinking=false` 使用 V4 Pro 非思考模式；复杂比较和综合问题可以设为 `true`。

回答正文使用 `[S1]`、`[S2]` 引用。后端会拒绝不存在的引用，也会拒绝没有来源标记但声称证据充分的回答。

## CLI

本地混合搜索：

```powershell
echolens knowledge semantic-search "怎样减少重复工作"
```

问答：

```powershell
echolens knowledge ask "这些视频有哪些共同建议？"
```

限定创作者并开启深度思考：

```powershell
echolens knowledge ask "总结他的核心观点" --creator <sec_uid> --thinking
```

## 当前边界

- SQLite 向量扫描适合个人或小范围内容库，不针对大规模并发；
- 第一次搜索可能需要等待模型下载和首次索引；
- 语义召回质量依赖现有转写分段；
- 问答只使用召回证据，不联网补充事实；
- 没有足够证据时会明确拒答；
- 暂不保存问答历史和多轮会话。
