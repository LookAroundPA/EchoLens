# EchoLens 技术栈设计

## 项目定位

EchoLens 是一个 AI 驱动的语音内容理解与知识沉淀系统。

目标：

> 将视频、音频中的声音转换为结构化知识，并通过 AI 实现搜索、分析和洞察。

整体流程：

```text
内容采集
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
| 内容采集 | yt-dlp / 自定义 Collector |
| 音频处理 | FFmpeg |
| 语音识别 | Whisper / Faster-Whisper |
| AI 分析 | LLM |
| 工作流 | LangChain / LangGraph |
| Embedding | BGE / OpenAI Embedding |
| 向量数据库 | FAISS / Chroma / Milvus |
| 后端 API | FastAPI |

## 模块设计

### Collector

负责获取原始内容。

输入：

- 视频 URL
- 本地视频文件
- 音频文件

输出：

- 原始媒体文件
- 元数据

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

---

### Storage

负责数据持久化。

存储：

- 原始文件
- 文本数据
- Embedding
- 向量索引

## MVP 实现目标

第一版只完成：

```text
视频文件
    ↓
FFmpeg
    ↓
音频文件
    ↓
Faster-Whisper
    ↓
文本 JSON
    ↓
LLM 摘要
```

先建立完整 Pipeline，再逐步扩展能力。
