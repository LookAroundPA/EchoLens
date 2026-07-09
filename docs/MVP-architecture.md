# EchoLens MVP 架构设计

## 1. 设计目标

本文定义 EchoLens 第一个可交付版本的技术边界。

MVP 的目标不是构建完整 AI 平台，而是打通：

```text
抖音创作者
    ↓
内容采集
    ↓
语音理解
    ↓
知识沉淀
```

完整闭环。

---

# 2. MVP 核心架构

```text
                    User
                     |
                     ↓
             Creator Configuration
                     |
                     ↓
              Collector Layer
                     |
                     ↓
              Media Pipeline
                     |
                     ↓
           Speech Recognition Layer
                     |
                     ↓
              AI Analysis Layer
                     |
                     ↓
             Knowledge Storage
```

---

# 3. 模块边界

## Collector

职责：

只负责获取内容。

输入：

- 创作者主页
- 视频链接

输出：

```json
{
  "creator_id": "xxx",
  "video_id": "xxx",
  "title": "xxx",
  "publish_time": "xxx",
  "media_url": "xxx"
}
```

注意：

Collector 不负责 AI 分析。

---

## Media Pipeline

职责：

处理媒体文件。

输入：

Video

输出：

Audio

流程：

```text
Video
 ↓
FFmpeg
 ↓
WAV
```

---

## Speech Pipeline

职责：

音频转文本。

输入：

Audio

输出：

Transcript

示例：

```json
{
  "segments": [
    {
      "start": 0,
      "end": 5,
      "text": "内容"
    }
  ]
}
```

---

## Analysis Pipeline

职责：

理解文本。

MVP 输出：

```json
{
  "summary": "摘要",
  "tags": ["AI", "创业"],
  "key_points": []
}
```

---

## Storage

MVP 使用简单可靠方案。

推荐：

```text
SQLite
 +
Local File Storage
```

数据：

- Creator
- Video
- Transcript
- Analysis

---

# 4. 数据流

```text
Creator
   |
   ↓
Video Metadata
   |
   ↓
Media
   |
   ↓
Audio
   |
   ↓
Transcript
   |
   ↓
Analysis Result
```

---

# 5. MVP 不包含

第一版不实现：

- Web 前端
- 多用户系统
- 权限管理
- 视频画面理解
- 推荐算法
- 知识图谱
- 多平台接入

---

# 6. 第一版 CLI 设计

目标：

先通过 CLI 验证产品闭环。

示例：

```bash
echolens creator add <url>

echolens creator sync

echolens analyze

echolens search "AI创业"
```

---

# 7. 成功标准

完成以下流程：

1. 添加一个抖音创作者
2. 同步其新作品
3. 自动生成文本
4. 自动生成摘要
5. 保存历史记录
6. 查询过去内容

达到后，进入下一阶段：知识系统建设。
