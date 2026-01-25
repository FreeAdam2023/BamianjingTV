# Hardcore Player 部署指南

## 目录

- [本地开发](#本地开发)
- [Docker 开发环境](#docker-开发环境)
- [Docker 生产环境 (GPU)](#docker-生产环境-gpu)
- [环境变量配置](#环境变量配置)
- [YouTube OAuth 设置](#youtube-oauth-设置)

---

## 本地开发

### 前置条件

- Python 3.10+
- Node.js 20+
- pnpm
- ffmpeg (带 libass 字幕支持)

### 后端

```bash
# 安装依赖
pip install -r requirements.txt

# 启动开发服务器
make dev
# 或
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 前端

```bash
# 安装依赖
make frontend-install
# 或
cd frontend && pnpm install

# 启动开发服务器
make frontend-dev
# 或
cd frontend && pnpm dev
```

### 同时运行

```bash
make dev-all
```

访问:
- 前端: http://localhost:3000
- API 文档: http://localhost:8000/docs

---

## Docker 开发环境

CPU-only 开发环境，支持热重载。

```bash
# 启动
make docker-dev

# 停止
make docker-dev-down
```

这将启动:
- API 服务 (端口 8000)
- 前端服务 (端口 3000)

---

## Docker 生产环境 (GPU)

### 前置条件

- NVIDIA GPU
- NVIDIA Container Toolkit (`nvidia-docker2`)
- Docker Compose v2

### 构建

```bash
make docker-build
```

### 启动

```bash
# API + 前端
make docker-up

# API + 前端 + n8n 自动化
make docker-up-all
```

### 查看日志

```bash
# 所有服务
make docker-logs

# 仅 API
make docker-logs-api

# 仅前端
make docker-logs-frontend
```

### 停止

```bash
make docker-down
```

### 重新部署（更新后）

```bash
# 拉取最新代码
git pull

# 重新构建并启动
make docker-build
make docker-down
make docker-up
```

---

## Docker 生产环境 (CPU)

没有 NVIDIA GPU 的服务器使用此配置。处理速度较慢，建议使用较小的 Whisper 模型 (base/small)。

### 启动

```bash
# API + 前端
make docker-cpu-up

# API + 前端 + n8n 自动化
make docker-cpu-up-all
```

### 查看日志

```bash
make docker-cpu-logs
```

### 停止

```bash
make docker-cpu-down
```

### 重新部署（更新后）

```bash
# 拉取最新代码
git pull

# 重新构建并启动
make docker-build
make docker-cpu-down
make docker-cpu-up
```

---

## 环境变量配置

复制示例配置:

```bash
cp .env.example .env
```

### 必填配置

| 变量 | 说明 |
|------|------|
| `HF_TOKEN` | HuggingFace token，用于 pyannote.audio 说话人分离 |
| `LLM_API_KEY` | LLM API Key，用于翻译和缩略图生成 |
| `LLM_BASE_URL` | LLM API 基础 URL |
| `LLM_MODEL` | LLM 模型名称 |

### LLM 配置示例

**Grok (推荐 - 无内容审查，便宜)**
```bash
LLM_API_KEY=xai-your-key
LLM_BASE_URL=https://api.x.ai/v1
LLM_MODEL=grok-4-fast-non-reasoning
```

**OpenAI**
```bash
LLM_API_KEY=sk-your-openai-key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

**Azure OpenAI**
```bash
LLM_API_KEY=your-azure-key
LLM_BASE_URL=https://your-resource.openai.azure.com/openai/deployments/your-deployment
LLM_MODEL=gpt-4o-mini
```

### 模型配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `WHISPER_MODEL` | `large-v3` | Whisper 模型大小 |
| `WHISPER_DEVICE` | `cuda` | Whisper 运行设备 |
| `DIARIZATION_DEVICE` | `cuda` | 说话人分离设备 |
| `TTS_DEVICE` | `cuda` | TTS 设备 (仅配音模式) |

### 服务配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `HOST` | `0.0.0.0` | 监听地址 |
| `PORT` | `8000` | API 端口 |
| `DEBUG` | `false` | 调试模式 |
| `FRONTEND_URL` | `http://localhost:3000` | 前端 URL |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | CORS 允许源 |

### 视频配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MAX_VIDEO_DURATION` | `7200` | 最大视频时长 (秒) |
| `FFMPEG_NVENC` | `true` | 使用 GPU 编码 |

---

## YouTube OAuth 设置

如需使用 YouTube 上传功能:

### 1. 创建 Google Cloud 项目

1. 访问 [Google Cloud Console](https://console.cloud.google.com)
2. 创建新项目
3. 启用 **YouTube Data API v3**

### 2. 创建 OAuth 凭据

1. 进入 API 和服务 → 凭据
2. 创建 OAuth 2.0 客户端 ID
3. 应用类型选择 **桌面应用**
4. 下载 JSON 文件

### 3. 配置文件

将下载的 JSON 保存到:

```
credentials/youtube_oauth.json
```

### 4. 首次授权

首次上传时会打开浏览器进行 OAuth 授权，授权后 token 保存到:

```
credentials/youtube_token.json
```

### 环境变量

```bash
YOUTUBE_CREDENTIALS_FILE=credentials/youtube_oauth.json
YOUTUBE_TOKEN_FILE=credentials/youtube_token.json
```

---

## 目录结构

```
├── jobs/                  # 处理任务文件
├── data/
│   ├── timelines/         # Timeline JSON 数据
│   ├── items/             # 内容项数据
│   ├── sources.json       # 来源配置
│   └── pipelines.json     # 流水线配置
├── credentials/           # OAuth 凭据 (不提交到 git)
└── .cache/                # 模型缓存
```

---

## 常见问题

### GPU 不可用

确保安装了 NVIDIA Container Toolkit:

```bash
# Ubuntu
sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker
```

验证:

```bash
docker run --rm --gpus all nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi
```

### 字幕乱码

确保 ffmpeg 编译时包含 libass:

```bash
ffmpeg -filters | grep ass
```

应显示 `ass` 和 `subtitles` 滤镜。

### 前端无法连接后端

检查 `NEXT_PUBLIC_API_URL` 环境变量是否正确设置。开发环境应为 `http://localhost:8000`。
