# MirrorFlow v2 升级计划

> **核心理念**: MirrorFlow = 执行引擎 | n8n = Fetcher + Fan-out 编排
>
> 不是"一坨流程"，而是多入口、多出口的内容网络。

## 一、架构演进概览

### 1.1 核心变化

| 维度 | v1 (当前) | v2 (目标) |
|------|-----------|-----------|
| **中心对象** | Video / Job | Source Type → Source → Item → Pipeline |
| **MirrorFlow 职责** | 全流程（下载→上传） | 纯执行引擎（Pipeline 执行 + 状态暴露） |
| **n8n 职责** | 简单触发 + 状态轮询 | Fetcher Layer + Fan-out Layer + Notify Layer |
| **可视化视角** | 单个 Job 进度 | 来源类型 → 来源 → Pipeline → 目标 |

### 1.2 新设计的 4 个一等公民

```
Source Type (来源类型)
   └── Source (具体来源)
         └── Item (内容项)
               └── Pipeline (处理流水线)
                     └── Target (发布目标)
```

---

## 二、数据模型变更

### 2.1 新增模型定义

#### 2.1.1 Source Type 枚举

```python
# app/models/source.py

class SourceType(str, Enum):
    """来源类型 - 系统世界观的入口"""
    YOUTUBE = "youtube"       # YouTube 视频/频道/播放列表
    RSS = "rss"               # 网站/博客 RSS
    PODCAST = "podcast"       # 播客 RSS
    SCRAPER = "scraper"       # 网页抓取
    LOCAL = "local"           # 本地文件
    API = "api"               # 第三方 API
```

#### 2.1.2 Source 模型

```python
class SourceSubType(str, Enum):
    """来源子类型"""
    # YouTube
    CHANNEL = "channel"
    PLAYLIST = "playlist"
    VIDEO = "video"
    # RSS
    WEBSITE = "website"
    BLOG = "blog"
    # Podcast
    SHOW = "show"
    EPISODE = "episode"
    # Local
    FOLDER = "folder"
    FILE = "file"


class Source(BaseModel):
    """具体来源定义"""
    source_id: str                           # 唯一标识，如 "yt_lex"
    source_type: SourceType                  # 来源类型
    sub_type: SourceSubType                  # 子类型
    display_name: str                        # 显示名称，如 "Lex Fridman"
    fetcher: str                             # 使用的 Fetcher，如 "youtube_rss"

    # 来源配置
    config: dict = {}                        # Fetcher 特定配置
    # YouTube: {"channel_id": "xxx", "playlist_id": "xxx"}
    # RSS: {"feed_url": "https://..."}
    # Local: {"watch_path": "/path/to/folder"}

    # 元数据
    enabled: bool = True
    created_at: datetime
    last_fetched_at: Optional[datetime] = None
    item_count: int = 0

    # 默认 Pipeline 配置
    default_pipelines: List[str] = []        # 新 Item 自动触发的 Pipeline IDs
```

#### 2.1.3 Item 模型

```python
class ItemStatus(str, Enum):
    """Item 状态"""
    DISCOVERED = "discovered"    # 刚发现
    QUEUED = "queued"            # 已排队
    PROCESSING = "processing"    # 处理中
    COMPLETED = "completed"      # 全部完成
    PARTIAL = "partial"          # 部分完成
    FAILED = "failed"            # 失败


class Item(BaseModel):
    """内容项 - 一个视频/文章/播客等"""
    item_id: str                             # 唯一标识
    source_type: SourceType                  # 来源类型
    source_id: str                           # 所属来源

    # 原始信息
    original_url: str
    original_title: str
    original_description: Optional[str] = None
    original_thumbnail: Optional[str] = None
    duration: Optional[float] = None
    published_at: Optional[datetime] = None

    # 状态
    status: ItemStatus = ItemStatus.DISCOVERED
    created_at: datetime
    updated_at: datetime

    # Pipeline 状态汇总
    pipelines: Dict[str, "PipelineStatus"] = {}  # pipeline_id -> status
```

#### 2.1.4 Pipeline 模型

```python
class PipelineType(str, Enum):
    """Pipeline 类型"""
    FULL_DUB = "full_dub"           # 完整配音
    SUBTITLE_ONLY = "subtitle"      # 仅字幕
    SHORTS = "shorts"               # 短视频剪辑
    AUDIO_ONLY = "audio"            # 仅音频


class PipelineConfig(BaseModel):
    """Pipeline 配置"""
    pipeline_id: str                         # 如 "zh_main", "ja_channel", "shorts"
    pipeline_type: PipelineType
    display_name: str                        # 如 "中文主频道"

    # 处理配置
    target_language: str = "zh"
    steps: List[str] = ["download", "transcribe", "diarize", "translate", "tts", "mux"]

    # 内容生成配置
    generate_thumbnail: bool = True
    generate_content: bool = True

    # 目标配置
    target: "TargetConfig"

    enabled: bool = True


class TargetConfig(BaseModel):
    """发布目标配置"""
    target_type: str                         # "youtube", "local", "s3", etc.
    target_id: str                           # YouTube channel ID 或路径
    display_name: str                        # "中文频道"

    # YouTube 特定
    privacy_status: str = "private"
    playlist_id: Optional[str] = None

    # 通用
    auto_publish: bool = False
    config: dict = {}
```

### 2.2 Job Schema 升级

```python
# app/models/job.py - 升级版

class Job(BaseModel):
    """Job 数据模型 - v2"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])

    # ========== v2 新增：来源追溯 ==========
    source_type: SourceType                  # 必填：来源类型
    source_id: str                           # 必填：来源 ID
    item_id: str                             # 必填：Item ID
    pipeline_id: str                         # 必填：Pipeline ID

    # ========== 原有字段保留 ==========
    url: str
    target_language: str = "zh"
    status: JobStatus = JobStatus.PENDING
    progress: float = 0.0
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # ... (其余字段保持不变)
```

---

## 三、API 变更计划

### 3.1 新增 API 端点

#### 3.1.1 Source 管理 API

```
# Source CRUD
POST   /sources                    创建来源
GET    /sources                    列出来源（支持 source_type 过滤）
GET    /sources/{source_id}        获取来源详情
PUT    /sources/{source_id}        更新来源
DELETE /sources/{source_id}        删除来源

# Source 操作
POST   /sources/{source_id}/fetch  立即触发 Fetch
GET    /sources/{source_id}/items  获取该来源的所有 Items
```

#### 3.1.2 Item 管理 API

```
# Item CRUD
GET    /items                      列出 Items（支持 source_type/source_id/status 过滤）
GET    /items/{item_id}            获取 Item 详情（含所有 Pipeline 状态）
DELETE /items/{item_id}            删除 Item

# Item 操作
POST   /items/{item_id}/trigger    为 Item 触发指定 Pipeline
GET    /items/{item_id}/pipelines  获取 Item 的所有 Pipeline 执行状态
```

#### 3.1.3 Pipeline 配置 API

```
# Pipeline CRUD
POST   /pipelines                  创建 Pipeline 配置
GET    /pipelines                  列出所有 Pipeline 配置
GET    /pipelines/{pipeline_id}    获取 Pipeline 配置
PUT    /pipelines/{pipeline_id}    更新 Pipeline 配置
DELETE /pipelines/{pipeline_id}    删除 Pipeline 配置
```

#### 3.1.4 聚合视图 API（为可视化服务）

```
# 运营视图
GET    /overview                   总览（按 source_type 分组的统计）
GET    /overview/{source_type}     指定类型的详情

# 示例响应
{
  "youtube": {
    "source_count": 5,
    "new_items_24h": 3,
    "active_pipelines": 7
  },
  "rss": {
    "source_count": 2,
    "new_items_24h": 5,
    "active_pipelines": 2
  }
}

# Fan-out 视图
GET    /items/{item_id}/fanout     获取 Item 的分发状态
# 响应
{
  "item": {...},
  "pipelines": {
    "zh_channel": {"status": "completed", "target": "YouTube ZH"},
    "ja_channel": {"status": "processing", "progress": 0.6},
    "shorts": {"status": "pending"}
  }
}
```

### 3.2 Job API 兼容性保持

```
# 原有 API 保持不变，但 Job 创建增加必填字段
POST /jobs
{
  "url": "...",
  "source_type": "youtube",        # 新增：必填
  "source_id": "yt_lex",           # 新增：必填
  "item_id": "item_abc123",        # 新增：必填
  "pipeline_id": "zh_main",        # 新增：必填
  "target_language": "zh"
}
```

---

## 四、n8n 工作流重构

### 4.1 新架构：三层分离

```
┌─────────────────────────────────────────────────────────┐
│                    Fetcher Layer                        │
├─────────────────────────────────────────────────────────┤
│  yt_channel_fetcher    ─┐                               │
│  yt_playlist_fetcher   ─┼─► 检测新内容 → 创建 Item      │
│  rss_fetcher           ─┤                               │
│  podcast_fetcher       ─┤                               │
│  local_watcher         ─┘                               │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│                    Fan-out Layer                        │
├─────────────────────────────────────────────────────────┤
│  新 Item 触发 → 根据 Source 配置 → 触发多个 Pipeline    │
│                                                         │
│  Item (source=yt_lex)                                   │
│   ├── Pipeline → zh_channel                             │
│   ├── Pipeline → ja_channel                             │
│   └── Pipeline → shorts_channel                         │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│                   Notify/Ops Layer                      │
├─────────────────────────────────────────────────────────┤
│  • Pipeline 完成通知                                    │
│  • 失败告警                                             │
│  • 日报/周报                                            │
│  • 手动重试触发                                         │
└─────────────────────────────────────────────────────────┘
```

### 4.2 Fetcher 工作流设计

每个 Fetcher 只做 3 件事：
1. 检测更新
2. 生成 Item
3. 触发 MirrorFlow Job

#### 4.2.1 YouTube Channel Fetcher

```json
{
  "name": "Fetcher: YouTube Channel",
  "trigger": "Cron (每 15 分钟)",
  "steps": [
    {
      "node": "HTTP Request",
      "action": "GET /sources?source_type=youtube&sub_type=channel&enabled=true"
    },
    {
      "node": "Loop",
      "for_each": "source",
      "steps": [
        {
          "node": "HTTP Request",
          "action": "Fetch YouTube RSS: https://www.youtube.com/feeds/videos.xml?channel_id={{channel_id}}"
        },
        {
          "node": "Filter",
          "condition": "published_at > last_fetched_at"
        },
        {
          "node": "HTTP Request",
          "action": "POST /items",
          "body": {
            "source_type": "youtube",
            "source_id": "{{source_id}}",
            "original_url": "{{video_url}}",
            "original_title": "{{title}}"
          }
        }
      ]
    }
  ]
}
```

#### 4.2.2 RSS Fetcher

```json
{
  "name": "Fetcher: RSS",
  "trigger": "Cron (每 30 分钟)",
  "steps": [
    "GET /sources?source_type=rss&enabled=true",
    "Loop: for each source",
    "  Fetch RSS feed",
    "  Filter: new items since last_fetched_at",
    "  POST /items for each new item"
  ]
}
```

### 4.3 Fan-out 工作流设计

```json
{
  "name": "Fan-out: Trigger Pipelines",
  "trigger": "Webhook (Item 创建时触发)",
  "steps": [
    {
      "node": "Get Item",
      "action": "GET /items/{{item_id}}"
    },
    {
      "node": "Get Source",
      "action": "GET /sources/{{source_id}}"
    },
    {
      "node": "Loop Pipelines",
      "for_each": "source.default_pipelines",
      "steps": [
        {
          "node": "Create Job",
          "action": "POST /jobs",
          "body": {
            "url": "{{item.original_url}}",
            "source_type": "{{item.source_type}}",
            "source_id": "{{item.source_id}}",
            "item_id": "{{item.item_id}}",
            "pipeline_id": "{{pipeline_id}}",
            "target_language": "{{pipeline.target_language}}"
          }
        }
      ]
    }
  ]
}
```

### 4.4 要删除的旧工作流

- ❌ `mirrorflow_pipeline.json` - 单视频全流程（将被拆分）
- ❌ `mirrorflow_batch.json` - 简单批量处理（被 Fetcher 替代）

### 4.5 要创建的新工作流

| 工作流名称 | 类型 | 触发方式 | 说明 |
|-----------|------|---------|------|
| `fetcher_youtube_channel.json` | Fetcher | Cron 15min | YouTube 频道检测 |
| `fetcher_youtube_playlist.json` | Fetcher | Cron 30min | YouTube 播放列表检测 |
| `fetcher_rss.json` | Fetcher | Cron 30min | RSS 订阅检测 |
| `fetcher_podcast.json` | Fetcher | Cron 1h | 播客检测 |
| `fetcher_local.json` | Fetcher | Filesystem watch | 本地文件夹监控 |
| `fanout_pipelines.json` | Fan-out | Webhook | Item 创建后触发 Pipeline |
| `notify_completion.json` | Notify | Webhook | 完成通知 |
| `notify_failure.json` | Notify | Webhook | 失败告警 |
| `ops_daily_report.json` | Ops | Cron daily | 每日报告 |

---

## 五、文件结构变更

### 5.1 新增文件

```
app/
├── models/
│   ├── source.py          # 新增：Source, SourceType
│   ├── item.py            # 新增：Item, ItemStatus
│   └── pipeline.py        # 新增：Pipeline, Target 配置
├── api/
│   ├── sources.py         # 新增：Source CRUD API
│   ├── items.py           # 新增：Item 管理 API
│   ├── pipelines.py       # 新增：Pipeline 配置 API
│   └── overview.py        # 新增：聚合视图 API
├── services/
│   ├── source_manager.py  # 新增：Source 生命周期管理
│   ├── item_manager.py    # 新增：Item 生命周期管理
│   └── pipeline_manager.py # 新增：Pipeline 配置管理

n8n/
└── workflows/
    ├── fetchers/
    │   ├── youtube_channel.json
    │   ├── youtube_playlist.json
    │   ├── rss.json
    │   └── podcast.json
    ├── fanout/
    │   └── trigger_pipelines.json
    └── notify/
        ├── completion.json
        ├── failure.json
        └── daily_report.json

data/
├── sources.json           # Source 配置持久化
├── items/                 # Item 数据存储
│   └── {source_type}/
│       └── {source_id}/
│           └── {item_id}.json
└── pipelines.json         # Pipeline 配置持久化
```

### 5.2 修改文件

| 文件 | 变更内容 |
|------|---------|
| `app/models/job.py` | 新增 source_type, source_id, item_id, pipeline_id 字段 |
| `app/main.py` | 注册新路由，初始化新 Manager |
| `app/services/job_manager.py` | 支持按 source/item/pipeline 过滤 |
| `app/config.py` | 新增 data_dir, items_dir 配置 |

---

## 六、实施阶段

### Phase 1: 数据模型扩展（向后兼容） ✅ COMPLETED

**目标**: 在不破坏现有功能的情况下，扩展数据模型

**任务清单**:

- [x] 1.1 创建 `app/models/source.py`
  - 定义 SourceType, SourceSubType 枚举
  - 定义 Source 模型

- [x] 1.2 创建 `app/models/item.py`
  - 定义 ItemStatus 枚举
  - 定义 Item 模型

- [x] 1.3 创建 `app/models/pipeline.py`
  - 定义 PipelineType 枚举
  - 定义 PipelineConfig, TargetConfig 模型

- [x] 1.4 更新 `app/models/job.py`
  - 添加 source_type, source_id, item_id, pipeline_id（设为 Optional 保持兼容）

- [x] 1.5 编写模型单元测试 (39 tests passing)

**验收标准**: 所有现有 API 正常工作，新字段为 Optional

---

### Phase 2: 服务层实现 ✅ COMPLETED

**目标**: 实现 Source/Item/Pipeline 管理逻辑

**任务清单**:

- [x] 2.1 创建 `app/services/source_manager.py`
  - CRUD 操作
  - JSON 文件持久化
  - last_fetched_at 更新

- [x] 2.2 创建 `app/services/item_manager.py`
  - CRUD 操作
  - 按目录结构存储
  - Pipeline 状态聚合

- [x] 2.3 创建 `app/services/pipeline_manager.py`
  - Pipeline 配置管理
  - 默认 Pipeline 模板

- [x] 2.4 更新 JobManager
  - 支持关联更新 Item 状态
  - 支持按 source/item/pipeline 查询

- [x] 2.5 编写服务层测试 (40 tests passing)

**验收标准**: 服务层单元测试通过，可以在 Python Shell 中操作

---

### Phase 3: API 层实现 ✅ COMPLETED

**目标**: 暴露 RESTful API

**任务清单**:

- [x] 3.1 创建 `app/api/sources.py`
  - Source CRUD 端点
  - Fetch 触发端点

- [x] 3.2 创建 `app/api/items.py`
  - Item 查询端点
  - Pipeline 触发端点

- [x] 3.3 创建 `app/api/pipelines.py`
  - Pipeline 配置端点

- [x] 3.4 创建 `app/api/overview.py`
  - 聚合统计端点
  - Fan-out 状态端点

- [x] 3.5 更新 `app/main.py`
  - 注册新路由
  - 初始化新 Manager

- [x] 3.6 编写 API 集成测试 (30 tests passing)
- [x] 3.7 更新 OpenAPI 文档 (auto-generated by FastAPI)

**验收标准**: Swagger UI 可以操作所有新端点

---

### Phase 4: n8n 工作流重构 ✅ COMPLETED

**目标**: 按新架构重建 n8n 工作流

**任务清单**:

- [x] 4.1 创建 Fetcher: YouTube Channel (`n8n/workflows/fetchers/youtube_channel.json`)
- [x] 4.2 创建 Fetcher: RSS (`n8n/workflows/fetchers/rss.json`)
- [x] 4.3 创建 Fetcher: Podcast (`n8n/workflows/fetchers/podcast.json`)
- [x] 4.4 创建 Fan-out: Trigger Pipelines (`n8n/workflows/fanout/trigger_pipelines.json`)
- [x] 4.5 创建 Notify: Completion (`n8n/workflows/notify/completion.json`)
- [x] 4.6 创建 Notify: Failure (`n8n/workflows/notify/failure.json`)
- [x] 4.7 创建 Ops: Daily Report (`n8n/workflows/notify/daily_report.json`)
- [x] 4.8 创建 n8n workflows README (`n8n/workflows/README.md`)
- [ ] 4.9 配置 Webhook 连接 (部署时配置)
- [ ] 4.10 测试端到端流程 (部署时验证)
- [ ] 4.11 迁移现有 Source 配置 (部署时迁移)

**验收标准**: 新建 Source 后，自动检测 → 创建 Item → 触发 Pipeline

---

### Phase 5: 可视化准备（数据层） ✅ COMPLETED

**目标**: 为前端可视化提供完整数据支持

**任务清单**:

- [x] 5.1 实现 `/overview` 聚合 API (`app/api/overview.py`)
  - 系统总览统计
  - 按 source_type 分组统计
  - 最近活动查询
  - 健康检查端点
- [x] 5.2 实现 `/items/{id}/fanout` 分发状态 API (`app/api/items.py`)
  - Item 详情含所有 Pipeline 状态
  - Fan-out 视图展示分发状态
- [x] 5.3 添加 WebSocket 实时状态推送 (`app/api/websocket.py`)
  - 主 WebSocket 端点 `/ws`
  - Job 订阅 `/ws/jobs/{job_id}`
  - Source 订阅 `/ws/sources/{source_id}`
  - Topic 订阅 (jobs, items, sources, overview, all)
  - ConnectionManager 管理连接与广播
  - 19 个 WebSocket 测试 (`tests/api/test_websocket.py`)
- [x] 5.4 编写 API 文档 (`docs/API_REFERENCE.md`)
  - 完整 REST API 参考
  - WebSocket API 文档
  - 请求/响应示例
  - 错误处理说明

**验收标准**: 前端可以渲染三层视图

---

### Phase 6: 清理与文档 ✅ COMPLETED

**目标**: 清理旧代码，完善文档

**任务清单**:

- [x] 6.1 将 Job 的 source_type 等字段改为自动填充 (`app/models/job.py`)
  - 添加 `infer_source_type_from_url()` 函数
  - JobCreate 和 Job 模型添加 `@model_validator` 自动迁移 v1 数据
- [x] 6.2 归档旧 n8n 工作流 (`n8n/workflows/_archive_v1/`)
  - mirrorflow_pipeline.json
  - mirrorflow_batch.json
  - mirrorflow_monitor.json
- [x] 6.3 更新 README.md
  - 添加 v2 架构说明
  - 更新 API 概览表
  - 更新项目结构
- [x] 6.4 更新 CLAUDE.md
  - 添加 v2 核心概念
  - 更新数据存储结构
  - 添加 n8n 工作流参考
- [x] 6.5 编写迁移指南 (`docs/MIGRATION_V2.md`)
  - v1 到 v2 迁移步骤
  - API 变更说明
  - WebSocket 集成指南
- [x] 6.6 更新部署文档 (`docs/DEPLOYMENT.md`)
  - 添加 v2 n8n 工作流配置
  - 添加 v2 环境变量
  - 添加 v2 验证步骤

---

## 七、数据迁移策略

### 7.1 现有 Job 迁移

对于已存在的 Job，自动填充默认值：

```python
def migrate_job_v1_to_v2(job: Job) -> Job:
    """迁移 v1 Job 到 v2"""
    if not job.source_type:
        # 根据 URL 推断来源类型
        if "youtube.com" in job.url or "youtu.be" in job.url:
            job.source_type = SourceType.YOUTUBE
        else:
            job.source_type = SourceType.API

    if not job.source_id:
        job.source_id = "legacy"

    if not job.item_id:
        job.item_id = f"item_{job.id}"

    if not job.pipeline_id:
        job.pipeline_id = "default_zh"

    return job
```

### 7.2 默认 Source 创建

```python
# 为现有 Job 创建 Legacy Source
legacy_source = Source(
    source_id="legacy",
    source_type=SourceType.API,
    sub_type=SourceSubType.VIDEO,
    display_name="Legacy Jobs",
    fetcher="manual",
    default_pipelines=["default_zh"],
)
```

### 7.3 默认 Pipeline 创建

```python
default_pipeline = PipelineConfig(
    pipeline_id="default_zh",
    pipeline_type=PipelineType.FULL_DUB,
    display_name="Default Chinese",
    target_language="zh",
    target=TargetConfig(
        target_type="local",
        target_id="output",
        display_name="Local Output",
    ),
)
```

---

## 八、风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| API 兼容性破坏 | 中 | 高 | Phase 1-3 保持新字段 Optional |
| n8n 工作流迁移复杂 | 中 | 中 | 逐个迁移，保留旧工作流备份 |
| 数据迁移失败 | 低 | 高 | 迁移脚本先在测试环境验证 |
| 性能下降（多层查询） | 低 | 中 | 使用缓存，索引优化 |

---

## 九、成功指标

### 9.1 技术指标

- [ ] 所有新 API 响应 < 200ms
- [ ] Job 创建必须包含 source_type, source_id, item_id, pipeline_id
- [ ] n8n 工作流按 Fetcher 类型分离

### 9.2 业务指标

- [ ] 可以从"来源类型"视角看到全局状态
- [ ] 可以追踪单个 Item 的所有 Pipeline 分发
- [ ] 添加新 Source 后自动开始抓取

---

## 十、时间线建议

| Phase | 预计工作量 | 依赖 |
|-------|-----------|------|
| Phase 1: 数据模型 | 1-2 天 | 无 |
| Phase 2: 服务层 | 2-3 天 | Phase 1 |
| Phase 3: API 层 | 2-3 天 | Phase 2 |
| Phase 4: n8n 重构 | 3-4 天 | Phase 3 |
| Phase 5: 可视化 | 2-3 天 | Phase 3 |
| Phase 6: 清理文档 | 1-2 天 | Phase 4, 5 |

**总计**: 约 2-3 周

---

## 附录 A: 新设计本质总结

> 系统升级为：
>
> **一个多来源（Source Type）、多入口（Fetcher）、多分发（Pipeline Fan-out）的内容自动化工厂**
>
> 而不是一个"视频处理脚本"。

核心理念变化：

| 旧问题 | 新问题 |
|--------|--------|
| 这个视频跑到哪一步了？ | 这个内容是从哪一类入口进来的，现在流向哪里？ |

---

## 附录 B: 快速验证清单

Phase 1 完成后验证：
```bash
# 模型测试
pytest tests/models/test_source.py
pytest tests/models/test_item.py
pytest tests/models/test_pipeline.py
```

Phase 3 完成后验证：
```bash
# API 测试
curl http://localhost:8000/sources
curl http://localhost:8000/items
curl http://localhost:8000/pipelines
curl http://localhost:8000/overview
```

Phase 4 完成后验证：
```
# n8n 端到端
1. 创建 YouTube Source
2. 等待 Fetcher 运行
3. 检查 Item 是否创建
4. 检查 Job 是否触发
5. 检查 Item fanout 状态
```

---

*文档版本: 1.0*
*创建日期: 2026-01-24*
*基于: MirrorFlow v1.0.0 → v2.0.0 升级*
