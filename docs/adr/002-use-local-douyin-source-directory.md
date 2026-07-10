# ADR 002: 使用本地目录作为抖音采集结果输入源

## 状态

已确定

## 背景

EchoLens 不直接负责启动和维护抖音采集任务。

抖音视频采集由外部采集服务负责，例如独立部署的 Douyin_TikTok_Download_API。

采集服务将视频文件落盘到部署机本地目录，EchoLens 负责读取该目录并进入后续语音分析流程。

## 决策

MVP 阶段采用本地目录作为 EchoLens 的输入源。

固定根目录：

```text
D:\BaiduNetdiskDownload\dy src
```

目录下按不同博主建立子目录。

示例：

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

## 影响

EchoLens 当前项目不直接调用抖音平台，也不直接内嵌 Douyin_TikTok_Download_API。

EchoLens 只需要实现 Local Directory Collector：

```text
本地目录
   ↓
视频扫描
   ↓
去重
   ↓
媒体处理 Pipeline
```

## 优点

- 降低采集层复杂度
- 避免 EchoLens 与抖音接口强绑定
- 方便在 Windows 部署机上运行
- 后续仍可替换为 HTTP API Collector

## 风险

- 依赖外部采集任务按约定落盘
- 文件命名和目录结构需要稳定
- 需要处理重复文件和未下载完成文件

## 后续

后续可以增加：

- 文件扫描状态记录
- 下载完成检测
- 创作者目录映射配置
- HTTP Collector Adapter
