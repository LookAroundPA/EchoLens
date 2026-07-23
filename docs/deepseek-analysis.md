# DeepSeek 内容分析

EchoLens 当前使用 DeepSeek 完成转写文本的结构化分析。

## 配置

在 `.env` 中填写：

```text
LLM_PROVIDER=deepseek
LLM_API_KEY=<your-api-key>
LLM_MODEL=deepseek-v4-flash
LLM_BASE_URL=https://api.deepseek.com
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=8192
```

API Key 只保存在本地 `.env`，不得提交到仓库。

## 分析结果

每条转写会生成：

```json
{
  "summary": "内容摘要",
  "tags": ["主题标签"],
  "key_points": ["关键观点"]
}
```

结果写入 MySQL `analyses` 表：

- `summary`
- `tags_json`
- `key_points_json`
- `model_name`

状态流：

```text
transcribed → analyzing → done
```

失败时：

```text
analysis_failed
```

具体原因写入 `videos.error_message`。当前不做自动重试。

## 单独运行分析

先处理一条：

```powershell
docker compose run --rm echolens analyze --once
```

批量处理：

```powershell
docker compose run --rm echolens analyze --max-tasks 40
```

## 一键运行现有处理阶段

在视频已经通过 `scan --enqueue` 入库和入队后，可执行：

```powershell
docker compose run --rm echolens pipeline --max-tasks 40
```

该命令依次执行：

```text
Redis 音频任务
→ FFmpeg WAV
→ Faster-Whisper 转写
→ DeepSeek 分析
→ videos.status = done
```

`--max-tasks` 分别限制每个阶段本次最多处理的数量。省略该参数时，会处理完当前所有可用任务。

## 验证

```sql
SELECT status, COUNT(*)
FROM videos
GROUP BY status;

SELECT COUNT(*) AS transcript_count
FROM transcripts;

SELECT COUNT(*) AS analysis_count
FROM analyses;

SELECT
    v.video_id,
    v.status,
    a.model_name,
    CHAR_LENGTH(a.summary) AS summary_length,
    JSON_LENGTH(a.tags_json) AS tag_count,
    JSON_LENGTH(a.key_points_json) AS key_point_count
FROM videos AS v
LEFT JOIN analyses AS a ON a.video_id = v.id
ORDER BY v.id;
```

完整成功时，目标视频状态应为 `done`，并且每条记录都存在对应的 `transcripts` 和 `analyses` 数据。
