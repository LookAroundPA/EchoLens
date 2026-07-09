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

> 用户指定抖音创作者，EchoLens 自动获取其公开作品，并持续完成语音分析和知识沉淀。

核心闭环：

```text
指定创作者
    ↓
自动同步作品
    ↓
获取媒体资源
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
                 Creator
                    |
                    ↓
          Collector Adapter
                    |
                    ↓
          Media Metadata
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

## 6.1 Collector（采集层）

职责：

负责获取创作者内容。

能力：

- 添加创作者
- 同步作品列表
- 获取视频信息
- 判断新增内容

设计原则：

Collector 必须独立，可替换。

参考方向：

- Douyin_TikTok_Download_API
- 自定义平台 Adapter

原因：

平台接口、Cookie、风控策略可能变化，不能让核心 AI Pipeline 依赖单一采集实现。

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

初期：

- SQLite
- 文件存储

后续：

- PostgreSQL
- Vector Database

---

# 7. 开发阶段

## Phase 0：工程基础

状态：进行中

目标：

建立长期维护能力。

---

## Phase 1：自动采集 MVP

目标：

打通创作者到内容的自动化流程。

功能：

- 添加创作者
- 同步作品
- 去重
- 获取媒体资源

风险：

- 平台变化
- Cookie 管理
- 风控限制

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

- Douyin Collector Adapter
- Douyin_TikTok_Download_API（参考）

语音：

- Faster-Whisper

AI：

- LLM
- Embedding

存储：

- SQLite
- PostgreSQL
- Vector Database

---

# 9. 非目标

当前不做：

- 视频画面理解
- 视频编辑
- 社交运营
- 推荐算法
- 多平台支持

EchoLens 的核心价值：

> 从声音中提取知识。

---

# 10. MVP 验收标准

用户完成：

1. 添加一个抖音创作者
2. 系统自动发现新作品
3. 自动获取可访问媒体内容
4. 自动生成转录文本
5. 自动生成摘要和标签
6. 可以查询该创作者历史内容

---

# 11. 风险与边界

## 数据采集风险

采集依赖公开内容和技术适配，可能受到：

- 平台策略调整
- Cookie 变化
- 接口变化
- 访问限制

影响。

因此 Collector 必须保持独立。

## 产品边界

EchoLens 不是下载工具。

下载只是入口。

真正价值是：

> 理解创作者长期输出的思想和趋势。
