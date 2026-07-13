# EchoLens Frontend

React + TypeScript 前端，直接连接 EchoLens FastAPI。

## 本地开发

先启动后端 API：

```powershell
docker compose up api
```

再启动前端开发服务器：

```powershell
cd frontend
npm install
npm run dev
```

访问：

```text
http://localhost:5173
```

Vite 会把 `/api` 和 `/health` 代理到 `http://localhost:8000`。

## Docker 联调

在仓库根目录运行：

```powershell
docker compose up --build api frontend
```

访问：

```text
http://localhost:3000
```

Nginx 会把浏览器的 `/api/*` 请求转发到 Compose 中的 `api:8000`。

## 已实现页面

- 总览：统计、状态、标签、最近视频、扫描和 pipeline 操作；
- 视频：所有状态列表、关键词/状态/标签筛选、分页；
- 视频详情：摘要、观点、完整转写、时间戳、音频播放和阶段重跑；
- 创作者：列表、统计、标签和视频时间线；
- 搜索：描述、摘要、转写、标签和关键观点；
- 任务：扫描、pipeline、单视频任务的轮询、错误和结果查看。

## 构建检查

```powershell
npm run build
```

该命令先执行 TypeScript 类型检查，再生成生产构建。
