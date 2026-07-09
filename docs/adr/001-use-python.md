# ADR 001: 使用 Python 作为核心开发语言

## 状态

已确定

## 背景

EchoLens 核心能力包括语音识别、LLM 调用、Embedding 和知识检索。

## 决策

采用 Python 作为核心开发语言。

## 原因

- AI 生态成熟
- Whisper 支持完善
- LLM 工具链丰富
- 数据处理能力强

## 影响

未来如果需要高并发业务服务，可以引入其他语言作为外围服务，但 AI Pipeline 保持 Python。
