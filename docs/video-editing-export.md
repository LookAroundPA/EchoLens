# 视频内容编辑与导出

EchoLens 视频详情页支持小范围使用所需的人工修正，不引入审核流、历史版本或权限体系。

## 编辑转写

接口：

```http
PATCH /api/videos/{id}/transcript
Content-Type: application/json

{
  "transcript": "人工修正后的完整转写"
}
```

行为：

- 修改 `transcripts.transcript_text`；
- 保留已有时间戳分段、识别语言和模型名称；
- 视频状态改为 `transcribed`；
- 旧分析继续显示，但前端明确提示分析需要更新；
- 可选择“保存并重新分析”，直接创建 `stage=analysis` 的任务。

空白转写返回 `422`。

## 编辑分析

接口：

```http
PATCH /api/videos/{id}/analysis
Content-Type: application/json

{
  "summary": "人工修正后的摘要",
  "tags": ["标签一", "标签二"],
  "keyPoints": ["观点一", "观点二"]
}
```

行为：

- 保存摘要、标签和关键观点；
- 自动去除空项和重复项；
- 视频状态恢复为 `done`；
- 没有转写时返回 `409`。

前端编辑框中，标签和关键观点均使用“一行一项”。

## 导出

Markdown：

```http
GET /api/videos/{id}/export/markdown
```

JSON：

```http
GET /api/videos/{id}/export/json
```

下载文件名固定使用数据库视频 ID：

```text
echolens-video-{id}.md
echolens-video-{id}.json
```

导出内容包含：

- 视频和创作者基础信息；
- 处理状态；
- 摘要、标签和关键观点；
- 完整转写和时间戳分段；
- Whisper 与分析模型名称；
- 分析是否需要重新生成。

导出不会包含视频、metadata 或音频的本地绝对路径。

## 本地验收建议

1. 打开一个已有转写和分析的视频；
2. 修改转写并只保存，确认状态变为 `transcribed` 且出现旧分析提示；
3. 点击重新分析，确认跳转到新任务；
4. 修改摘要、标签和关键观点，刷新页面确认数据保留；
5. 分别下载 Markdown 和 JSON，确认中文内容和文件名正常；
6. 确认导出文件中没有 `D:\\`、`/data/` 等本地路径。
