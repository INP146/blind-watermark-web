# blind-watermark-web

盲水印网页工作台。开发时前后端可以分开跑，生产/简单部署时前端构建产物会直接放进 Python 后端，由一个 Python 服务同时提供页面和 API。

## 本地开发

启动后端：

```bash
cd backend
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

启动前端开发服务器：

```bash
cd frontend
npm install
npm run dev
```

开发访问：<http://localhost:5173>

## 单端口运行

先构建前端：

```bash
cd frontend
npm install
npm run build
```

`npm run build` 会把前端构建产物输出到 `backend/static/`。

然后只启动 Python 后端：

```bash
cd backend
pip install -r requirements.txt
python app.py
```

访问：<http://localhost:8000>

这个端口会同时提供：

- `/`：前端页面
- `/assets/*`：前端静态资源
- `/api/*`：后端接口

如果刷新前端路由，后端会回退返回 `index.html`，适合单页应用部署。

## Docker Compose 部署

项目提供的是单容器应用镜像：构建阶段先打包前端，运行阶段只启动 FastAPI，由 FastAPI 同时提供前端静态文件和 `/api/*` 接口。宿主机已有 nginx 时，不需要在容器里再跑 nginx。

先复制环境变量示例，按需修改端口：

```bash
cp .env.example .env
```

### 方式一：服务器本地构建

服务器上有完整源码时，可以直接构建并启动：

```bash
docker compose up -d --build
```

### 方式二：直接部署预构建镜像

推送 `v*` tag 后，GitHub Actions 会构建并发布镜像到 GHCR：

```text
ghcr.io/inp146/blind-watermark-web:latest
```

部署机不需要 Node/Python 构建环境，也不需要执行 `docker compose build`：

```bash
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

默认监听宿主机本机地址：

```text
127.0.0.1:8000
```

这样容器不会直接暴露到公网，适合交给宿主机 nginx 反代。查看日志：

```bash
docker compose logs -f app
```

停止：

```bash
docker compose down
```

如需改端口，编辑 `.env`：

```env
APP_BIND=127.0.0.1
APP_PORT=8000
WEB_CONCURRENCY=2
TZ=Asia/Shanghai
```
