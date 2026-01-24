# MirrorFlow

**自动化视频语言转换流水线** - 将英文视频内容（访谈、演讲、播客）自动转换为中文配音视频。

## 功能特性

- **语音识别**：Whisper large-v3 高精度转写
- **说话人分离**：pyannote.audio 多人对话识别
- **智能翻译**：口语化中文翻译，适合配音
- **多音色配音**：XTTS v2 为每个说话人生成独立音色
- **视频合成**：FFmpeg + NVENC GPU 加速编码
- **AI 封面生成**：SDXL 自动生成吸引眼球的缩略图
- **内容生成**：自动生成标题、描述、标签和章节目录
- **YouTube 上传**：一键上传，支持定时发布

## 快速开始

### 1. 安装

```bash
git clone <repository_url>
cd BamianjingTV
pip install -r requirements.txt
```

### 2. 配置

```bash
cp .env.example .env
# 编辑 .env，填写 HF_TOKEN 和 OPENAI_API_KEY
```

### 3. 运行

```bash
make dev
```

### 4. 使用

```bash
# 创建任务
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{"url": "https://youtube.com/watch?v=xxx"}'
```

访问 http://localhost:8000/docs 查看完整 API 文档。

## Docker 部署

```bash
# 启动完整服务栈（API + n8n + Redis）
docker-compose up -d

# 服务地址
# - API: http://localhost:8000
# - n8n: http://localhost:5678
```

## 处理流程

```
YouTube URL
    ↓
1. 下载视频 (yt-dlp)
    ↓
2. 语音识别 (Whisper)
    ↓
3. 说话人分离 (pyannote)
    ↓
4. 翻译 (OpenAI API)
    ↓
5. 语音合成 (XTTS v2)
    ↓
6. 视频合成 (FFmpeg)
    ↓
7. 内容生成（标题/描述/标签）
    ↓
8. 封面生成 (SDXL)
    ↓
9. YouTube 上传（可选）
    ↓
中文配音视频
```

## 项目结构

```
BamianjingTV/
├── app/
│   ├── main.py              # FastAPI 主应用
│   ├── config.py            # 配置管理
│   ├── api/                 # API 路由
│   ├── models/              # 数据模型
│   ├── services/            # 业务服务
│   └── workers/             # 处理模块
├── n8n/                     # n8n 工作流
├── docs/                    # 文档
├── docker-compose.yml       # Docker 配置
└── requirements.txt         # Python 依赖
```

## API 概览

| 端点 | 方法 | 描述 |
|------|------|------|
| `/jobs` | POST | 创建处理任务 |
| `/jobs` | GET | 列出所有任务 |
| `/jobs/{id}` | GET | 获取任务详情 |
| `/jobs/batch` | POST | 批量创建任务 |
| `/jobs/{id}/retry` | POST | 重试失败任务 |
| `/content/generate` | POST | 生成标题描述 |
| `/youtube/upload` | POST | 上传到 YouTube |

## 文档

- [部署指南](docs/DEPLOYMENT.md)
- [项目设计](docs/PROJECT_KICKOFF.md)
- [n8n 工作流](n8n/README.md)

## 环境要求

- Python 3.10+
- NVIDIA GPU (推荐 RTX 3080+)
- FFmpeg
- 32GB+ RAM

## 许可证

MIT License
