# EchoLens 产品需求文档（PRD）

## 1. 产品定位

### 产品名称

EchoLens

### 一句话定义

EchoLens 是一个 AI 驱动的语音内容理解与知识沉淀系统。

它自动追踪用户关注的信息源，将视频中的声音转换为结构化知识，并帮助用户理解长期观点变化。

核心理念：

> 穿透声音，洞察思想。

---

# 2. 产品目标

## 长期目标

构建一个个人 AI 信息分析助手：

- 自动追踪关注的创作者
- 自动理解大量语音内容
- 建立个人知识库
- 发现趋势和观点变化
- 与历史内容进行智能对话

---

# 3. MVP 定义

## 3.1 核心目标

MVP 不做“上传视频分析工具”。

真实目标：

> 用户指定抖音创作者，外部采集服务将视频落盘到本地目录，EchoLens 自动扫描、转写、分析并沉淀知识。

核心闭环：

```text
外部采集服务
    ↓
本地视频目录
    ↓
EchoLens 扫描
    ↓
MySQL 去重 / 状态记录
    ↓
Redis 任务队列
    ↓
提取原声
    ↓
语音转文字
    ↓
AI 内容分析
    ↓
知识归档
```

---

# 4. 用户场景

## 4.1 创作者追踪

用户关注某个博主。

EchoLens 自动生成：

- 发布记录
- 内容主题
- 高频关键词
- 核心观点
- 历史变化

---

## 4.2 信息研究

用户希望长期观察：

- AI 行业专家
- 投资观点
- 技术趋势
- 创业方向

---

# 5. 系统架构

```text
          External Douyin Collector
                     |
                     ↓
          Local Source Directory
                     |
                     ↓
              Scanner Layer
                     |
                     ↓
              MySQL Storage
                     |
                     ↓
               Redis Queue
                     |
                     ↓
              Media Pipeline
                     |
                     ↓
          Speech Recognition
                     |
                     ↓
              AI Analysis
                     |
                     ↓
          Knowledge Storage
                     |
                     ↓
              Query System
```

---

# 6. 核心模块

## 6.1 Scanner / Collector（本地扫描层）

职责：

负责从本地视频目录发现新内容。

能力：

- 扫描博主子目录
- 识别视频文件
- 解析 video_id
- 判断新增内容
- 写入 MySQL
- 推送 Redis 任务

设计原则：

Scanner 只读取本地文件，不直接调用抖音平台。

外部采集服务由用户单独维护。

---

## 6.2 Media Pipeline（媒体处理）

职责：

处理视频和音频。

流程：

```text
Video
 ↓
FFmpeg
 ↓
Audio
```

能力：

- 提取音频
- 格式转换
- 音频标准化

---

## 6.3 Speech Pipeline（语音识别）

技术：

- Whisper
- Faster-Whisper

输出：

- Transcript
- Timestamp
- Subtitle

---

## 6.4 AI Analysis（内容理解）

MVP 输出：

### Summary

内容摘要。

### Tags

主题标签。

### Key Points

关键观点。

后续：

- 观点演变分析
- 内容关联
- 趋势分析

---

## 6.5 Knowledge Storage（知识存储）

MVP 阶段使用：

- MySQL：持久化视频、任务状态、转录文本、AI 分析结果
- Redis：任务队列、锁、临时状态、重试计数
- Local File Storage：原始视频、音频、中间文件

后续阶段增加：

- Vector Database

---

# 7. 开发阶段

## Phase 0：工程基础

状态：进行中

目标：

建立长期维护能力。

---

## Phase 1：本地目录扫描 MVP

目标：

打通本地视频目录到处理队列的自动化流程。

功能：

- 扫描固定根目录
- 按博主子目录识别来源
- 根据 video_id 去重
- 使用 mtime 加速扫描
- 使用 MySQL 记录状态
- 使用 Redis 推送处理任务

风险：

- 文件下载中被提前扫描
- 文件名格式变化
- 重复文件
- 视频 ID 解析失败

---

## Phase 2：语音智能 Pipeline

功能：

- FFmpeg 音频处理
- Faster-Whisper 转录
- LLM 摘要

---

## Phase 3：知识系统

功能：

- 全文搜索
- 语义搜索
- AI 问答

---

## Phase 4：智能助手

功能：

- 自动日报/周报
- 趋势发现
- 创作者画像

---

# 8. 技术路线

核心语言：

Python

音视频：

- FFmpeg

采集：

- 外部 Douyin 采集服务
- 本地目录 Scanner
- Douyin_TikTok_Download_API（参考）

语音：

- Faster-Whisper

AI：

- LLM
- Embedding

存储：

- MySQL
- Redis
- Local File Storage
- Vector Database（后续）

---

# 9. 非目标

当前不做：

- 视频画面理解
- 视频编辑
- 社交运营
- 推荐算法
- 多平台支持
- 抖音采集服务部署管理

EchoLens 的核心价值：

> 从声音中提取知识。

---

# 10. MVP 验收标准

用户完成：

1. 外部采集服务将视频保存到固定目录
2. EchoLens 扫描本地视频目录
3. 系统识别新增视频
4. 使用 MySQL 完成去重和状态记录
5. 使用 Redis 分发处理任务
6. 自动生成转录文本
7. 自动生成摘要和标签
8. 可以查询该创作者历史内容

---

# 11. 风险与边界

## 数据采集风险

采集由外部服务负责，EchoLens 不保证抖音平台采集稳定性。

EchoLens 只处理已经落盘的视频文件。

## 文件扫描风险

本地文件可能存在：

- 下载未完成
- 文件重复
- 文件名格式变化
- 文件时间异常

因此扫描层必须使用：

- mtime 快速过滤
- video_id 去重
- 文件稳定性检查
- MySQL 状态记录

## 产品边界

EchoLens 不是下载工具。

下载只是入口。

真正价值是：

> 理解创作者长期输出的思想和趋势。
