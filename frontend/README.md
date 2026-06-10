# 盲水印前端

Vite + Vue 3 + Naive UI 写的盲水印工作台，提供嵌入水印和提取水印两个流程。

## 启动

```bash
npm install
npm run dev
```

默认访问 `http://localhost:5173`。

## 后端接口约定

开发环境已在 `vite.config.ts` 中把 `/api` 代理到 `http://127.0.0.1:8000`。

### `GET /api/health`

返回 2xx 表示后端可用。

### `POST /api/embed`

`multipart/form-data` 字段：

- `image`: 原图文件
- `watermark`: 水印图文件
- `password_img`: 图片密码
- `password_wm`: 水印密码
- `output_format`: `png` 或 `jpg`

响应：嵌入水印后的图片二进制。

### `POST /api/extract`

`multipart/form-data` 字段：

- `image`: 已嵌入水印的图片
- `password_img`: 图片密码
- `password_wm`: 水印密码
- `wm_width`: 水印宽度
- `wm_height`: 水印高度

响应：提取出的水印图片二进制。
