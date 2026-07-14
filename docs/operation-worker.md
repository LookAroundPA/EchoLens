# 独立操作 Worker

EchoLens 的网页操作任务不再由 FastAPI `BackgroundTasks` 执行。

当前流程：

```text
浏览器提交操作
→ FastAPI 在 MySQL 创建 processing_jobs 记录
→ FastAPI 将 jobId、jobType、payload 推送到 Redis
→ FastAPI 立即返回 202
→ 独立 job-worker 串行消费
→ 复用现有任务执行与阶段进度逻辑
→ MySQL 更新 succeeded / failed
```

## Redis 队列

默认键名：

```text
echolens:queue:operations
echolens:queue:operations:processing
```

使用 Redis List 和 `BRPOPLPUSH`，兼容 Redis 3.0.504。

原有扫描入库视频队列保持不变：

```text
echolens:queue:video
echolens:queue:video:processing
```

两类队列用途不同，不要合并。

## Docker 启动

API 和操作 Worker 一起启动：

```powershell
docker compose up --build api job-worker
```

前端仍在本机运行：

```powershell
cd frontend
npm run dev
```

`job-worker` 使用与 API 相同的 MySQL、Redis、视频目录、音频目录和模型缓存配置。

## 命令行启动

直接运行常驻 Worker：

```powershell
echolens job-worker
```

只处理一个任务并退出：

```powershell
echolens job-worker --once
```

最多处理十个任务：

```powershell
echolens job-worker --max-tasks 10
```

## 当前恢复行为

- API 重启不会中断正在运行的独立 Worker；
- Worker 启动时会把 processing 列表中遗留的消息放回 ready 列表；
- MySQL 中已经是 `succeeded` 或 `failed` 的重复消息会直接确认并跳过；
- Redis 无法接收新任务时，API 将对应 MySQL job 标记为失败，并返回 `503`；
- 任务阶段进度继续写入 `processing_jobs.result_json`。

## 使用限制

当前按本地、小范围使用设计：

- 默认只运行一个 `job-worker` 实例；
- 没有多 Worker 租约、心跳和抢占；
- 没有延迟重试和死信队列；
- Worker 如果在 FFmpeg、Whisper 或 DeepSeek 执行中被强制终止，消息会在下次启动时恢复，但视频可能停留在中间状态；这种情况可在任务中心查看错误后手工重试；
- 不要同时启动多个 `job-worker`，否则任务可能并行执行并争用本机 CPU、内存或模型资源。
