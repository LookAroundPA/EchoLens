# EchoLens

> See beyond the sound.
>
> 穿透声音，洞察思想。

EchoLens 是一个 AI 驱动的语音内容理解与知识沉淀系统。

它将视频、播客、访谈、课程等音频内容转换为可搜索、可分析、可持续积累的知识资产。

## 项目愿景

互联网每天产生大量有价值的声音内容，但这些内容通常：

- 难以快速阅读
- 难以长期保存
- 难以关联分析
- 容易被时间淹没

EchoLens 希望构建一个从 **声音采集 → 内容理解 → 知识沉淀 → 智能洞察** 的 AI 内容基础设施。

## 核心流程

```text
内容来源
    |
    v
音频提取
    |
    v
语音识别
    |
    v
文本理解
    |
    v
知识存储
    |
    v
AI 洞察
```

## 核心能力

### 音频处理

- 从视频源提取音频
- 音频格式标准化
- 批量处理支持

### 语音识别

- 自动语音转文字
- 多语言支持
- 时间戳生成
- 字幕生成

### AI 内容理解

- 内容摘要
- 主题分类
- 关键观点提取
- 语义搜索

### 知识系统

将分散的声音内容沉淀为个人知识库。

你可以询问：

- 某个创作者长期关注哪些主题？
- 他的观点随着时间如何变化？
- 大量视频中有哪些共同观点？

## 技术路线

| 模块 | 技术 |
| --- | --- |
| 音频处理 | FFmpeg |
| 语音识别 | Whisper / Faster-Whisper |
| AI 分析 | Large Language Models |
| 向量检索 | FAISS / Chroma / Milvus |
| 后端 | Python |

## 开发路线

### 第一阶段：音频基础能力

- [ ] 视频/音频输入处理
- [ ] 音频提取流程
- [ ] 语音转文字流程
- [ ] 文本存储

### 第二阶段：内容理解能力

- [ ] AI 摘要
- [ ] 主题标签
- [ ] 关键观点提取

### 第三阶段：知识系统

- [ ] 向量数据库接入
- [ ] 语义搜索
- [ ] AI 问答

### 第四阶段：智能自动化

- [ ] 自动内容采集
- [ ] 定时分析任务
- [ ] 趋势发现
- [ ] 智能报告生成

## 参与贡献

欢迎提交 Issue 和 Pull Request。

EchoLens 希望探索如何让隐藏在声音中的人类知识，更容易被发现、理解和复用。

## Docker 运行

项目通过 `.env` 读取 MySQL 和 Redis 凭据。Compose 会将宿主机视频目录只读挂载到容器，并通过 `host.docker.internal` 连接宿主机服务。

构建镜像并执行只读扫描：

```powershell
docker compose build
docker compose run --rm echolens scan
```

确认扫描结果正确后，显式写入 MySQL 并推送 Redis 任务：

```powershell
docker compose run --rm echolens scan --enqueue
```

已有数据库在首次运行 Worker 前，需要执行 [mysql_audio_migration.sql](scripts/mysql_audio_migration.sql) 中的迁移，为 `videos` 添加音频输出字段。

提取队列中的 WAV 音频（保存到 `D:\BaiduNetdiskDownload\dy out`）：

```powershell
docker compose run --rm echolens worker --max-tasks 8
```

直接执行 `docker compose up` 时默认只运行 `echolens scan`，不会入库或入队。

## 开源协议

待定
