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

## 已实现页面

- 总览：统计、状态、标签、最近视频、扫描和 pipeline 操作；
- 视频：所有状态列表、关键词/状态/标签筛选、分页；
- 视频详情：摘要、观点、完整转写、时间戳、音频播放和阶段重跑；
- 创作者：列表、统计、标签和视频时间线；
- 搜索：描述、摘要、转写、标签和关键观点；
- 任务：扫描、pipeline、单视频任务的轮询、错误和结果查看。

## 单独构建检查

```powershell
npm run build
```
