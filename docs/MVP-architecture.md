# EchoLens MVP 架构设计

## 1. 设计目标

本文定义 EchoLens 第一个可交付版本的技术边界。

MVP 的目标不是构建完整 AI 平台，而是打通：

```text
抖音创作者
    ↓
本地视频目录
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
          External Douyin Collector
                     |
                     ↓
          Local Source Directory
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

# 3. 本地输入源约定

MVP 阶段，抖音采集任务由外部服务负责。

EchoLens 不直接维护抖音采集服务，只读取其输出目录。

固定根目录：

```text
D:\BaiduNetdiskDownload\dy src
```

目录结构：

```text
D:\BaiduNetdiskDownload\dy src\
├── creator_a\
│   ├── video_001.mp4
│   └── video_002.mp4
│
└── creator_b\
    ├── video_001.mp4
    └── video_002.mp4
```

每个博主对应一个子目录，视频文件存放在对应博主目录下。

---

# 4. 模块边界

## Collector

职责：

只负责从本地目录发现内容。

输入：

- 本地根目录
- 博主子目录
- 视频文件

输出：

```json
{
  "creator_id": "creator_a",
  "video_id": "video_001",
  "source_path": "D:\\BaiduNetdiskDownload\\dy src\\creator_a\\video_001.mp4",
  "file_name": "video_001.mp4"
}
```

注意：

Collector 不负责 AI 分析，也不直接调用抖音平台。

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

# 5. 数据流

```text
Local Source Directory
   |
   ↓
Video File
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

# 6. MVP 不包含

第一版不实现：

- Web 前端
- 多用户系统
- 权限管理
- 视频画面理解
- 推荐算法
- 知识图谱
- 多平台接入
- 抖音采集服务部署管理

---

# 7. 第一版 CLI 设计

目标：

先通过 CLI 验证产品闭环。

示例：

```bash
echolens scan

echolens analyze

echolens search "AI创业"
```

---

# 8. 成功标准

完成以下流程：

1. 外部采集服务将视频落盘到固定目录
2. EchoLens 扫描本地视频目录
3. 按博主子目录识别内容来源
4. 自动生成文本
5. 自动生成摘要
6. 保存历史记录
7. 查询过去内容

达到后，进入下一阶段：知识系统建设。
