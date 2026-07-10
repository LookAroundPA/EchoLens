# EchoLens 技术栈设计

## 项目定位

EchoLens 是一个 AI 驱动的语音内容理解与知识沉淀系统。

目标：

> 将视频、音频中的声音转换为结构化知识，并通过 AI 实现搜索、分析和洞察。

整体流程：

```text
本地视频目录
    ↓
目录扫描
    ↓
任务队列
    ↓
音频处理
    ↓
语音识别
    ↓
文本理解
    ↓
知识存储
    ↓
AI 检索与分析
```

## 开发语言

### Python

作为 EchoLens 核心开发语言。

原因：

- AI 生态成熟
- Whisper 支持完善
- LLM 工具丰富
- 数据处理能力强

## 核心技术选型

| 模块 | 技术 |
| --- | --- |
| 本地目录扫描 | Python pathlib / os.stat |
| 去重与状态持久化 | MySQL |
| 任务队列与锁 | Redis |
| 音频处理 | FFmpeg |
| 语音识别 | Whisper / Faster-Whisper |
| AI 分析 | LLM |
| 工作流 | LangChain / LangGraph |
| Embedding | BGE / OpenAI Embedding |
| 向量数据库 | FAISS / Chroma / Milvus |
| 后端 API | FastAPI |

## 模块设计

### Scanner / Collector

负责从本地视频目录发现原始内容。

输入：

- 固定根目录
- 博主子目录
- 视频文件

输出：

- 标准视频元数据
- MySQL 视频记录
- Redis 待处理任务

---

### Storage

负责数据持久化。

MVP 阶段：

- MySQL：视频记录、处理状态、转录文本、AI 分析结果
- Redis：任务队列、任务锁、临时状态、重试计数
- Local File Storage：视频、音频、中间文件

---

### Audio

负责音频预处理。

工具：

- FFmpeg

处理：

- 提取音轨
- 格式转换
- 音频标准化

---

### Speech

负责语音转文字。

工具：

- Whisper
- Faster-Whisper

输出：

- Transcript
- Subtitle
- Timestamp

---

### Analysis

负责 AI 内容理解。

能力：

- 摘要
- 分类
- 关键词提取
- 观点分析

## MVP 实现目标

第一版只完成：

```text
本地视频目录
    ↓
Scanner
    ↓
MySQL 去重
    ↓
Redis Queue
    ↓
FFmpeg
    ↓
Faster-Whisper
    ↓
文本 JSON
    ↓
LLM 摘要
    ↓
MySQL 保存结果
```

先建立完整 Pipeline，再逐步扩展能力。
