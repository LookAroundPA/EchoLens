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
              Scanner Layer
                     |
                     ↓
            MySQL 去重 / 状态
                     |
                     ↓
              Redis Queue
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
            MySQL Knowledge Storage
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
│   ├── douyin.wtf_douyin_738xxxx.mp4
│   └── douyin.wtf_douyin_739xxxx.mp4
│
└── creator_b\
    ├── douyin.wtf_douyin_740xxxx.mp4
    └── douyin.wtf_douyin_741xxxx.mp4
```

每个博主对应一个子目录，视频文件存放在对应博主目录下。

---

# 4. 模块边界

## Scanner / Collector

职责：

只负责从本地目录发现内容，并生成待处理任务。

输入：

- 本地根目录
- 博主子目录
- 视频文件

输出：

```json
{
  "creator_id": "creator_a",
  "video_id": "738xxxx",
  "source_path": "D:\\BaiduNetdiskDownload\\dy src\\creator_a\\douyin.wtf_douyin_738xxxx.mp4",
  "file_name": "douyin.wtf_douyin_738xxxx.mp4",
  "file_size": 12345678,
  "file_mtime": "2026-07-10T12:00:00"
}
```

注意：

Scanner 不负责 AI 分析，也不直接调用抖音平台。

---

## MySQL

职责：

负责持久化状态和结果。

主要保存：

- 创作者信息
- 视频元数据
- 文件扫描记录
- 处理状态
- 转录文本
- AI 分析结果

---

## Redis

职责：

负责运行时任务队列和临时状态。

主要用于：

- 待处理队列
- Worker 消费任务
- 任务锁
- 重试计数

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

# 5. 数据流

```text
Local Source Directory
   |
   ↓
Scanner
   |
   ↓
MySQL videos 去重
   |
   ↓
Redis Queue
   |
   ↓
Worker
   |
   ↓
Audio
   |
   ↓
Transcript
   |
   ↓
Analysis Result
   |
   ↓
MySQL Storage
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

echolens worker

echolens analyze

echolens search "AI创业"
```

---

# 8. 成功标准

完成以下流程：

1. 外部采集服务将视频落盘到固定目录
2. EchoLens 扫描本地视频目录
3. 按博主子目录识别内容来源
4. 使用 MySQL 完成视频去重和状态记录
5. 使用 Redis 派发处理任务
6. 自动生成文本
7. 自动生成摘要
8. 保存历史记录
9. 查询过去内容

达到后，进入下一阶段：知识系统建设。
