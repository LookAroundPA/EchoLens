# EchoLens

> See beyond the sound.
>
> 从声音中发现思想。

EchoLens 是一个 AI 驱动的语音内容理解与知识沉淀系统。

它将视频、播客、访谈、课程等音频内容转换为可搜索、可分析、可持续积累的知识资产。

## Vision

互联网每天产生大量有价值的声音内容，但这些内容通常：

- 难以快速阅读
- 难以长期保存
- 难以关联分析
- 容易被时间淹没

EchoLens 希望构建一个从 **声音采集 → 内容理解 → 知识沉淀 → 智能洞察** 的 AI 内容基础设施。

## Core Pipeline

```text
Content Sources
      |
      v
Audio Extraction
      |
      v
Speech Recognition
      |
      v
Text Understanding
      |
      v
Knowledge Storage
      |
      v
AI Insights
```

## Features

### Audio Intelligence

- Extract audio from video sources
- Normalize audio formats
- Batch processing support

### Speech Recognition

- Automatic transcription
- Multi-language support
- Timestamp generation
- Subtitle generation

### AI Understanding

- Summarization
- Topic classification
- Key insight extraction
- Semantic search

### Knowledge System

Transform scattered conversations into a personal knowledge base.

Example questions:

- What topics does this creator focus on?
- How have their opinions changed over time?
- What are the common ideas across hundreds of videos?

## Planned Tech Stack

| Component | Technology |
| --- | --- |
| Audio Processing | FFmpeg |
| Speech Recognition | Whisper / Faster-Whisper |
| LLM Analysis | Large Language Models |
| Vector Search | FAISS / Chroma / Milvus |
| Backend | Python |

## Roadmap

### Phase 1 - Audio Foundation

- [ ] Audio extraction pipeline
- [ ] Speech-to-text pipeline
- [ ] Transcript storage

### Phase 2 - Content Intelligence

- [ ] AI summaries
- [ ] Topic tagging
- [ ] Key opinion extraction

### Phase 3 - Knowledge Layer

- [ ] Vector database integration
- [ ] Semantic search
- [ ] AI Q&A

### Phase 4 - Automation

- [ ] Scheduled content collection
- [ ] Automatic analysis reports
- [ ] Personal intelligence dashboard

## Contributing

Issues and pull requests are welcome.

Together we explore how human knowledge hidden in audio can become accessible, searchable, and reusable.

## License

TBD
