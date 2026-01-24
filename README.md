# MirrorFlow

**自动化视频语言转换流水线** - 将英文视频内容（访谈、演讲、播客）自动转换为中文配音视频。

## v2.0 新特性

MirrorFlow v2 将系统从"视频处理脚本"升级为**多来源、多入口、多分发的内容自动化工厂**。

### 核心概念

```
Source Type (来源类型)
   └── Source (具体来源: YouTube 频道、RSS 订阅、播客)
         └── Item (内容项: 单个视频、文章、剧集)
               └── Pipeline (处理流水线: 中文配音、日文配音、短视频)
                     └── Target (发布目标: YouTube 频道、本地存储)
```

### v2 vs v1

| 维度 | v1 | v2 |
|------|----|----|
| 中心对象 | Video / Job | Source → Item → Pipeline |
| 内容发现 | 手动输入 URL | 自动从来源拉取 |
| 分发模式 | 单一流水线 | Fan-out 多目标分发 |
| 状态视角 | 单个 Job 进度 | 全局内容流向追踪 |
| 实时更新 | Webhook 轮询 | WebSocket 推送 |

## 功能特性

- **多来源支持**：YouTube 频道、RSS、播客、本地文件
- **自动内容发现**：定时检测新内容，自动创建处理任务
- **Fan-out 分发**：一个内容自动分发到多个目标平台
- **实时状态推送**：WebSocket 实时更新处理状态
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
# 编辑 .env，填写必要的 API 密钥
```

### 3. 运行

```bash
make dev
```

### 4. 使用

```bash
# 创建来源
curl -X POST http://localhost:8000/sources \
  -H "Content-Type: application/json" \
  -d '{
    "source_id": "yt_lex",
    "source_type": "youtube",
    "sub_type": "channel",
    "display_name": "Lex Fridman",
    "fetcher": "youtube_rss",
    "config": {"channel_id": "UCSHZKyawb77ixDdsGog4iWA"},
    "default_pipelines": ["default_zh"]
  }'

# 或直接创建任务（兼容 v1）
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{"url": "https://youtube.com/watch?v=xxx"}'
```

访问 http://localhost:8000/docs 查看完整 API 文档。

## 系统架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                         n8n Orchestration                            │
├─────────────────────────────────────────────────────────────────────┤
│  Fetcher Layer          Fan-out Layer         Notify Layer          │
│  ├── YouTube Fetcher    ├── Trigger Pipelines  ├── Completion       │
│  ├── RSS Fetcher        └── Create Jobs        ├── Failure Alert    │
│  └── Podcast Fetcher                           └── Daily Report     │
└─────────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│                      MirrorFlow API (FastAPI)                        │
├─────────────────────────────────────────────────────────────────────┤
│  /sources    - Content source management                            │
│  /items      - Content item tracking                                │
│  /pipelines  - Processing configuration                             │
│  /jobs       - Processing task execution                            │
│  /overview   - Dashboard aggregations                               │
│  /ws         - WebSocket real-time updates                          │
└─────────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│                       Processing Workers (GPU)                       │
├─────────────────────────────────────────────────────────────────────┤
│  Download → Whisper → Diarization → Translation → TTS → Mux         │
│                         ↓                                            │
│              Content Generation → Thumbnail → YouTube Upload         │
└─────────────────────────────────────────────────────────────────────┘
```

## 项目结构

```
BamianjingTV/
├── app/
│   ├── main.py              # FastAPI 主应用
│   ├── config.py            # 配置管理
│   ├── api/                 # API 路由
│   │   ├── sources.py       # v2: 来源管理
│   │   ├── items.py         # v2: 内容项管理
│   │   ├── pipelines.py     # v2: 流水线配置
│   │   ├── overview.py      # v2: 仪表盘聚合
│   │   └── websocket.py     # v2: 实时推送
│   ├── models/              # 数据模型
│   │   ├── source.py        # v2: Source, SourceType
│   │   ├── item.py          # v2: Item, ItemStatus
│   │   ├── pipeline.py      # v2: Pipeline, Target
│   │   └── job.py           # Job 数据模型
│   ├── services/            # 业务服务
│   │   ├── source_manager.py
│   │   ├── item_manager.py
│   │   ├── pipeline_manager.py
│   │   └── job_manager.py
│   └── workers/             # 处理模块
├── n8n/workflows/           # n8n 工作流
│   ├── fetchers/            # 内容获取器
│   ├── fanout/              # 分发触发
│   └── notify/              # 通知与运营
├── docs/                    # 文档
│   ├── API_REFERENCE.md     # API 参考文档
│   ├── DEPLOYMENT.md        # 部署指南
│   └── MIGRATION_V2.md      # v2 迁移指南
├── docker-compose.yml       # Docker 配置
└── requirements.txt         # Python 依赖
```

## API 概览

### v2 核心 API

| 端点 | 方法 | 描述 |
|------|------|------|
| `/sources` | GET/POST | 来源管理 |
| `/sources/{id}/fetch` | POST | 触发内容拉取 |
| `/items` | GET/POST | 内容项管理 |
| `/items/{id}/fanout` | GET | 查看分发状态 |
| `/pipelines` | GET/POST | 流水线配置 |
| `/overview` | GET | 系统总览 |
| `/ws` | WebSocket | 实时状态推送 |

### Job API（兼容 v1）

| 端点 | 方法 | 描述 |
|------|------|------|
| `/jobs` | POST | 创建处理任务 |
| `/jobs` | GET | 列出所有任务 |
| `/jobs/{id}` | GET | 获取任务详情 |
| `/jobs/batch` | POST | 批量创建任务 |
| `/jobs/{id}/retry` | POST | 重试失败任务 |

## Docker 部署

```bash
# 启动完整服务栈（API + n8n + Redis）
docker-compose up -d

# 服务地址
# - API: http://localhost:8000
# - n8n: http://localhost:5678
# - API 文档: http://localhost:8000/docs
```

## 文档

- [API 参考文档](docs/API_REFERENCE.md)
- [部署指南](docs/DEPLOYMENT.md)
- [v2 迁移指南](docs/MIGRATION_V2.md)
- [n8n 工作流](n8n/workflows/README.md)

## 环境要求

- Python 3.10+
- NVIDIA GPU (推荐 RTX 3080+)
- FFmpeg
- 32GB+ RAM

## 许可证

MIT License
