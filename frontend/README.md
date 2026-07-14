# EchoLens Frontend

React + TypeScript 前端，直接连接 EchoLens FastAPI。

前端完全使用本机 Node.js 启动，不需要 Docker，也不需要 Nginx。

## 准备

需要安装 Node.js 20 或更高版本。

首次进入前端目录后安装依赖：

```powershell
cd frontend
npm install
```

后端 API 需要先运行在：

```text
http://localhost:8000
```

可以继续使用后端 Docker：

```powershell
docker compose up api
```

## 开发模式

```powershell
cd frontend
npm run dev
```

访问：

```text
http://localhost:5173
```

该模式支持热更新。

## 构建后启动

```powershell
cd frontend
npm run serve
```

`serve` 会先执行 TypeScript 检查和生产构建，再启动本地预览服务。

访问：

```text
http://localhost:3000
```

## API 连接

`npm run dev` 和 `npm run serve` 都会把：

```text
/api/*
/health
```

代理到：

```text
http://localhost:8000
```

前端代码使用相对 API 路径，因此本地启动不需要配置额外环境变量。

确实需要连接其他 API 地址时，可以在 `frontend/.env.local` 中设置：

```text
VITE_API_BASE_URL=http://其他地址:8000
```

侧边栏会每 10 秒检查一次 `/health`，并显示 API 在线、检查中或离线状态。

## 已实现页面

- 总览：统计、状态、标签和最近视频；
- 运行操作：可配置扫描是否入队、pipeline 是否先扫描以及每阶段最大任务数；
- 视频：按关键词、创作者、状态和标签筛选，支持分页、当前页多选、批量继续处理、批量重新转写和批量重新分析；
- 视频详情：摘要、观点、完整转写、时间戳、音频播放和阶段重跑；
- 创作者：列表、统计、标签、视频时间线和创作者内搜索入口；
- 搜索：同时按关键词、创作者和标签检索知识内容；
- 任务：按状态和类型筛选，自动轮询单个任务，展示阶段统计、批量处理统计、错误和原始结果；
- 失败任务可保留原记录并创建新的重试任务；
- 任务成功后会自动刷新总览、视频、创作者、标签和搜索缓存。

## 批量处理说明

视频列表中的批量选择仅作用于当前页。切换筛选条件或分页时会清空已选内容。

- 批量继续处理：根据每个视频当前状态继续执行到 `done`；
- 批量重新转写：清除旧转写和分析结果，保留 WAV，重新转写并继续分析；
- 批量重新分析：保留当前转写，替换已有分析结果；
- 每次批量操作只创建一个任务，任务结果会分别记录每个视频的成功状态或失败原因。

## 单独构建检查

```powershell
npm run build
```
