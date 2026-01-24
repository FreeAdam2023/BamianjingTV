# MirrorFlow 部署指南

本文档介绍如何部署 MirrorFlow 视频语言转换系统。

## 目录

- [系统要求](#系统要求)
- [部署方式](#部署方式)
  - [方式一：本地开发部署](#方式一本地开发部署)
  - [方式二：Docker 生产部署](#方式二docker-生产部署)
  - [方式三：CPU 开发模式](#方式三cpu-开发模式)
- [环境变量配置](#环境变量配置)
- [API Keys 获取](#api-keys-获取)
- [YouTube 上传配置](#youtube-上传配置)
- [验证部署](#验证部署)
- [常见问题](#常见问题)

---

## 系统要求

### 硬件要求

| 组件 | 最低配置 | 推荐配置 |
|------|----------|----------|
| GPU | GTX 1080 (8GB) | RTX 3080+ (12GB+) |
| CPU | 8 核 | 16 核 |
| 内存 | 16GB | 32GB+ |
| 存储 | 100GB SSD | 500GB NVMe SSD |

> **注意**：无 GPU 时可使用 CPU 模式，但处理速度会显著降低。

### 软件要求

- Python 3.10+
- FFmpeg（支持 NVENC 用于 GPU 编码）
- Docker + Docker Compose（可选）
- NVIDIA Driver 535+（GPU 部署）
- NVIDIA Container Toolkit（Docker GPU 部署）

---

## 部署方式

### 方式一：本地开发部署

适用于开发调试和小规模使用。

#### 1. 克隆项目

```bash
git clone <repository_url>
cd BamianjingTV
```

#### 2. 创建虚拟环境

```bash
python3.10 -m venv venv
source venv/bin/activate  # Linux/macOS
# 或 .\venv\Scripts\activate  # Windows
```

#### 3. 安装依赖

```bash
pip install -r requirements.txt
```

#### 4. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，填写必要的 API Keys：

```env
HF_TOKEN=your_huggingface_token
OPENAI_API_KEY=your_openai_api_key
```

#### 5. 启动服务

```bash
# 使用 Make
make dev

# 或直接运行
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 6. 访问服务

- API 服务：http://localhost:8000
- API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

---

### 方式二：Docker 生产部署

适用于生产环境，包含完整的服务栈。

#### 前置要求

安装 NVIDIA Container Toolkit：

```bash
# Ubuntu/Debian
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

#### 1. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填写 API keys
```

#### 2. 构建并启动服务

```bash
# 构建镜像
make docker-build

# 启动所有服务
make docker-up
# 或
docker-compose up -d
```

#### 3. 查看服务状态

```bash
# 查看运行状态
docker-compose ps

# 查看日志
docker-compose logs -f mirrorflow

# 查看所有日志
make docker-logs
```

#### 4. 服务地址

| 服务 | 地址 | 说明 |
|------|------|------|
| MirrorFlow API | http://localhost:8000 | 主 API 服务 |
| Swagger 文档 | http://localhost:8000/docs | API 交互文档 |
| n8n | http://localhost:5678 | 工作流编排 |
| Redis | localhost:6379 | 缓存服务（内部） |

n8n 默认登录凭据：
- 用户名：`admin`
- 密码：`mirrorflow`

#### 5. 停止服务

```bash
make docker-down
# 或
docker-compose down
```

---

### 方式三：CPU 开发模式

无 GPU 时的开发部署方式。

```bash
# 使用 CPU 配置启动
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up

# 或修改 .env
WHISPER_DEVICE=cpu
TTS_DEVICE=cpu
FFMPEG_NVENC=false
```

> **注意**：CPU 模式下处理 10 分钟视频可能需要 1-2 小时。

---

## 环境变量配置

### 必需变量

| 变量 | 说明 | 获取方式 |
|------|------|----------|
| `HF_TOKEN` | HuggingFace 访问令牌 | [获取方法](#huggingface-token) |
| `OPENAI_API_KEY` | OpenAI API 密钥 | [获取方法](#openai-api-key) |

### 可选变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `WHISPER_MODEL` | `large-v3` | Whisper 模型版本 |
| `WHISPER_DEVICE` | `cuda` | ASR 设备 (cuda/cpu) |
| `TTS_DEVICE` | `cuda` | TTS 设备 (cuda/cpu) |
| `FFMPEG_NVENC` | `true` | 是否使用 GPU 视频编码 |
| `MAX_VIDEO_DURATION` | `7200` | 最大视频时长（秒） |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | OpenAI API 地址 |

### 完整 .env 示例

```env
# 必需
HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxx
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx

# 模型设置
WHISPER_MODEL=large-v3
WHISPER_DEVICE=cuda
TTS_DEVICE=cuda

# 服务设置
HOST=0.0.0.0
PORT=8000
DEBUG=false

# 视频设置
MAX_VIDEO_DURATION=7200
FFMPEG_NVENC=true

# YouTube（可选）
YOUTUBE_CREDENTIALS_FILE=credentials/youtube_oauth.json
YOUTUBE_TOKEN_FILE=credentials/youtube_token.json
```

---

## API Keys 获取

### HuggingFace Token

pyannote.audio 说话人分离模型需要 HuggingFace 授权。

1. 注册 [HuggingFace](https://huggingface.co/join) 账号

2. 访问模型页面并接受使用协议：
   - https://huggingface.co/pyannote/speaker-diarization-3.1
   - https://huggingface.co/pyannote/segmentation-3.0

3. 生成访问令牌：
   - 访问 https://huggingface.co/settings/tokens
   - 点击 "New token"
   - 选择 "Read" 权限
   - 复制生成的 token

### OpenAI API Key

用于翻译和内容生成。

1. 注册 [OpenAI](https://platform.openai.com/signup) 账号

2. 访问 https://platform.openai.com/api-keys

3. 点击 "Create new secret key"

4. 复制生成的 API Key

> **提示**：也可使用兼容 OpenAI API 的其他服务，修改 `OPENAI_BASE_URL` 即可。

---

## YouTube 上传配置

如需自动上传到 YouTube，需配置 Google Cloud OAuth。

### 1. 创建 Google Cloud 项目

1. 访问 [Google Cloud Console](https://console.cloud.google.com/)
2. 创建新项目或选择已有项目
3. 启用 **YouTube Data API v3**：
   - 进入 "APIs & Services" → "Library"
   - 搜索 "YouTube Data API v3"
   - 点击 "Enable"

### 2. 配置 OAuth 同意屏幕

1. 进入 "APIs & Services" → "OAuth consent screen"
2. 选择 "External" 用户类型
3. 填写应用信息（名称、邮箱等）
4. 添加范围：`https://www.googleapis.com/auth/youtube.upload`
5. 添加测试用户（你的 Google 账号邮箱）

### 3. 创建 OAuth 凭据

1. 进入 "APIs & Services" → "Credentials"
2. 点击 "Create Credentials" → "OAuth client ID"
3. 应用类型选择 "Desktop app"
4. 下载 JSON 文件

### 4. 配置凭据

```bash
# 创建凭据目录
mkdir -p credentials

# 将下载的 JSON 重命名并移动
mv ~/Downloads/client_secret_xxx.json credentials/youtube_oauth.json
```

### 5. 首次授权

首次使用 YouTube 上传功能时，系统会：
1. 自动打开浏览器
2. 要求登录 Google 账号
3. 授权应用访问 YouTube
4. 自动保存 token 到 `credentials/youtube_token.json`

---

## 验证部署

### 健康检查

```bash
curl http://localhost:8000/health
```

预期响应：

```json
{
  "status": "healthy",
  "queue": {
    "running": true,
    "max_concurrent": 2,
    "pending": 0,
    "active": 0
  }
}
```

### 创建测试任务

```bash
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "generate_thumbnail": true,
    "generate_content": true,
    "auto_upload": false
  }'
```

### 查看任务状态

```bash
# 列出所有任务
curl http://localhost:8000/jobs

# 查看特定任务
curl http://localhost:8000/jobs/{job_id}

# 查看系统统计
curl http://localhost:8000/stats
```

---

## 常见问题

### 1. CUDA out of memory

**问题**：GPU 内存不足

**解决方案**：
```env
# 使用较小的模型
WHISPER_MODEL=medium

# 或使用 CPU 处理部分任务
TTS_DEVICE=cpu
```

### 2. pyannote 授权失败

**问题**：`401 Unauthorized` 错误

**解决方案**：
1. 确认已在 HuggingFace 接受模型使用协议
2. 检查 `HF_TOKEN` 是否正确
3. 确认 token 有 "Read" 权限

### 3. FFmpeg NVENC 不可用

**问题**：`Unknown encoder 'h264_nvenc'`

**解决方案**：
```env
# 禁用 GPU 编码
FFMPEG_NVENC=false
```

### 4. Docker GPU 不可用

**问题**：容器无法访问 GPU

**解决方案**：
```bash
# 检查 NVIDIA Container Toolkit
nvidia-container-cli info

# 重启 Docker
sudo systemctl restart docker
```

### 5. 端口被占用

**问题**：`Address already in use`

**解决方案**：
```bash
# 查找占用端口的进程
lsof -i :8000

# 修改端口
PORT=8001 uvicorn app.main:app --port 8001
```

---

## 更多资源

- [API 文档](http://localhost:8000/docs)
- [n8n 工作流指南](../n8n/README.md)
- [项目设计文档](./PROJECT_KICKOFF.md)
