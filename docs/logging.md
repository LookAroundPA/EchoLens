# EchoLens 日志规范

## 目标

统一记录系统运行状态，方便调试和生产排查。

## 日志级别

|级别|用途|
|-|-|
|DEBUG|开发调试信息|
|INFO|正常运行记录|
|WARNING|潜在问题|
|ERROR|运行错误|

## 模块日志

建议按照模块划分：

```text
logs/
├── collector.log
├── audio.log
├── speech.log
├── analysis.log
└── storage.log
```

## 原则

- 关键流程必须有 INFO 日志
- 异常必须记录上下文
- 不记录敏感信息
