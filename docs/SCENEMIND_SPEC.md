# SceneMind 项目启动文档

> 边看剧边提问，把你没看懂的那一半补回来

## 1. 项目概述

### 1.1 问题背景

经典影视作品中包含大量非剧情层面的信息：
- 台词中的俚语、双关、时代用法
- 道具、海报、音乐所指向的文化背景
- 镜头、布景、颜色对人物状态的暗示

普通观众往往只能理解 30-50% 的信息。现有内容形式存在断层：
- 影评偏向剧情复述或八卦
- 学院派分析门槛高
- 语言学习工具与真实影视内容割裂

### 1.2 项目定位

SceneMind 是一套「看剧即创作」的私人工具，核心目标：

1. **不打断沉浸** - 看剧时不累、不割裂、不进入"创作模式"
2. **即时捕捉** - 把当下的疑问、直觉、兴趣点即时记录
3. **自动成稿** - 看完一集后，自动整理为可发布的解说视频素材

**最终产出**：持续、高质量地产出适合 YouTube 的影视解析内容。

---

## 2. 与 SceneMind 的关系

### 2.1 现有系统能力

```
SceneMind 当前流程:
URL → Download → Whisper → Diarization → Translation → Review → Export
```

可复用的基础设施：
| 模块 | 现有能力 | SceneMind 复用 |
|------|---------|---------------|
| FFmpeg | 视频处理、截图、剪辑 | 截图提取、Ken Burns 效果 |
| Whisper | 语音识别 | 解说配音识别（可选） |
| Translation | GPT-4o 翻译 | AI 理解扩展引擎 |
| TTS | XTTS 语音合成 | 解说配音生成 |
| Export | 字幕烧录、视频合成 | 解说视频渲染 |
| n8n | 工作流编排 | 自动化流程 |

### 2.2 功能边界

```
┌─────────────────────────────────────────────────────────────────┐
│                      SceneMind                             │
│   [视频学习材料工厂 - 字幕翻译流水线]                            │
│   Input: 完整视频 → Output: 双语字幕视频                         │
└─────────────────────────────────────────────────────────────────┘
                              ↓ 复用基础设施
┌─────────────────────────────────────────────────────────────────┐
│                        SceneMind                                 │
│   [影视解析创作工具 - 看剧即创作流水线]                          │
│   Input: 观影记录 → Output: YouTube 解说视频                     │
└─────────────────────────────────────────────────────────────────┘
```

### 2.3 整合方式

SceneMind 作为 SceneMind 的**新模块**（而非独立项目）：

```
backend/
├── app/
│   ├── models/
│   │   └── scenemind/           # 新增: SceneMind 数据模型
│   │       ├── observation.py   # 观影记录
│   │       ├── insight.py       # AI 解读
│   │       └── commentary.py    # 解说脚本
│   ├── services/
│   │   └── scenemind/           # 新增: SceneMind 服务层
│   │       ├── capture.py       # 截图 + 记录服务
│   │       ├── analyzer.py      # AI 分析引擎
│   │       └── generator.py     # 视频生成器
│   ├── workers/
│   │   └── scenemind/           # 新增: SceneMind Workers
│   │       ├── frame_capture.py # 截图提取
│   │       ├── ai_expand.py     # AI 理解扩展
│   │       ├── script_gen.py    # 脚本生成
│   │       └── video_render.py  # 视频渲染
│   └── api/
│       └── scenemind.py         # 新增: API 端点
```

---

## 3. UI/UX 设计原则

### 3.1 核心理念

**一句话**：最小干扰，最大产出。

| 原则 | 说明 |
|------|------|
| **零学习成本** | 所有操作一看就懂，不需要教程 |
| **最少点击** | 常用操作 1-2 次点击完成 |
| **不打断心流** | 观影时的操作不超过 3 秒 |
| **渐进式复杂** | 简单场景简单用，高级功能按需展开 |

### 3.2 用户流程总览

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         SceneMind 完整流程                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ① 选择剧集          ② 观影记录           ③ AI 分析           ④ 生成视频  │
│  ┌─────────┐        ┌─────────┐         ┌─────────┐        ┌─────────┐ │
│  │ 选剧集  │   →    │ 看+截图 │    →    │ 一键分析 │   →    │ 预览+导出│ │
│  │ 选视频  │        │ 写备注  │         │ 查看结果 │        │         │ │
│  └─────────┘        └─────────┘         └─────────┘        └─────────┘ │
│      ↓                  ↓                   ↓                  ↓       │
│   30 秒              20-40 分钟           1-2 分钟            3-5 分钟   │
│   (一次性)           (沉浸观影)           (等待 AI)           (微调)     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.3 页面结构

```
/scenemind
├── /                     # 首页 - 剧集列表 + 最近会话
├── /sessions/new         # 新建会话 - 选择剧集/上传视频
├── /sessions/:id/watch   # 观影模式 - 核心页面
├── /sessions/:id/review  # 审阅模式 - 查看记录 + AI 分析
└── /sessions/:id/export  # 导出模式 - 脚本编辑 + 视频生成
```

### 3.4 关键页面设计

#### 页面 1: 观影模式 (`/sessions/:id/watch`)

**目标**：沉浸观影，快速记录

```
┌─────────────────────────────────────────────────────────────────────────┐
│  SceneMind    That '70s Show S01E01                    [记录: 3] [退出] │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │                                                                   │ │
│  │                                                                   │ │
│  │                        视频播放区域                                │ │
│  │                     (点击暂停 / 框选截图)                          │ │
│  │                                                                   │ │
│  │                                                                   │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│   advancement bar ─────────●───────────────────────── 12:34 / 22:00     │
│                                                                         │
│  [◀◀ 10s]  [▶ 播放]  [10s ▶▶]              [截图 📷]  [完成观影 ✓]      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

                              ↓ 点击截图或框选后

┌─────────────────────────────────────────────────────────────────────────┐
│  ┌─────────────────┐                                                    │
│  │                 │    备注 (可选):                                    │
│  │   截图预览      │    ┌─────────────────────────────────────────────┐│
│  │                 │    │ 这个海报好像有意思                          ││
│  │   [重新框选]    │    └─────────────────────────────────────────────┘│
│  └─────────────────┘                                                    │
│                         标签:                                           │
│                         [俚语] [道具✓] [人物] [音乐] [其他]             │
│                                                                         │
│                                    [取消]  [保存并继续 ▶]               │
└─────────────────────────────────────────────────────────────────────────┘
```

**交互细节**：
- `Space` 暂停/播放
- `S` 快捷截图（全帧）
- 鼠标拖拽框选 → 局部截图
- `Enter` 保存记录并继续播放
- `Esc` 取消当前记录

#### 页面 2: 审阅模式 (`/sessions/:id/review`)

**目标**：查看所有记录，触发 AI 分析，审阅结果

```
┌─────────────────────────────────────────────────────────────────────────┐
│  SceneMind    审阅: S01E01                    [← 返回]  [生成解说视频 →]│
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │ [一键 AI 分析]  状态: 已分析 5/7 条                    [重新分析]   ││
│  └─────────────────────────────────────────────────────────────────────┘│
│                                                                         │
│  ┌─ 记录列表 ───────────────────────────────────────────────────────────┐
│  │                                                                     │
│  │  ┌────┐  12:34  "这个海报好像有意思"                    [道具]      │
│  │  │截图│  ──────────────────────────────────────────────────────     │
│  │  └────┘  AI 解读: 这是 Led Zeppelin 的《Houses of the Holy》        │
│  │          专辑海报，1973年发行，暗示 Eric 的音乐品味...              │
│  │          [展开详情]                              [✓ 采用] [✗ 跳过]  │
│  │                                                                     │
│  │  ┌────┐  15:22  "这句话什么意思"                        [俚语]      │
│  │  │截图│  ──────────────────────────────────────────────────────     │
│  │  └────┘  AI 解读: "Burn" 在 70 年代俚语中表示...                    │
│  │          [展开详情]                              [✓ 采用] [✗ 跳过]  │
│  │                                                                     │
│  └─────────────────────────────────────────────────────────────────────┘
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

#### 页面 3: 导出模式 (`/sessions/:id/export`)

**目标**：编辑脚本，预览效果，导出视频

```
┌─────────────────────────────────────────────────────────────────────────┐
│  SceneMind    导出: S01E01                              [← 返回审阅]   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─ 脚本编辑 ──────────────────────┐  ┌─ 视频预览 ──────────────────┐  │
│  │                                 │  │                             │  │
│  │  标题: 你没注意到的 7 个细节    │  │   ┌───────────────────┐    │  │
│  │  ─────────────────────────────  │  │   │                   │    │  │
│  │                                 │  │   │   预览播放器      │    │  │
│  │  1. [道具] Led Zeppelin 海报    │  │   │                   │    │  │
│  │     [编辑解说词...]             │  │   └───────────────────┘    │  │
│  │     特写动画: [缩放到海报 ▼]    │  │                             │  │
│  │                        [↑] [↓]  │  │   [▶ 预览当前段落]         │  │
│  │                                 │  │   [▶ 预览完整视频]         │  │
│  │  2. [俚语] "Burn" 的含义        │  │                             │  │
│  │     [编辑解说词...]             │  └─────────────────────────────┘  │
│  │     特写动画: [慢速缩放 ▼]      │                                   │
│  │                        [↑] [↓]  │  ┌─ 导出设置 ──────────────────┐  │
│  │                                 │  │ 配音: [XTTS ▼]              │  │
│  │  ...                            │  │ 字幕: [中英双语 ▼]          │  │
│  │                                 │  │ 分辨率: [1080p ▼]           │  │
│  └─────────────────────────────────┘  │                             │  │
│                                       │ [导出视频]  预计: ~5 分钟    │  │
│                                       └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.5 快捷键设计

| 快捷键 | 观影模式 | 审阅模式 | 导出模式 |
|--------|----------|----------|----------|
| `Space` | 播放/暂停 | - | 预览播放/暂停 |
| `S` | 全帧截图 | - | - |
| `Enter` | 保存记录 | - | - |
| `Esc` | 取消记录 | - | - |
| `←` / `→` | 快退/快进 5s | 上/下一条记录 | 上/下一段落 |
| `A` | - | 一键 AI 分析 | - |
| `E` | - | - | 导出视频 |

---

## 4. 核心工作流

### 4.1 阶段 A: 观影 + 即时记录

```
[Next.js 前端 - SceneMind 观影模式]
     │
     ├─ 视频播放器 (HTML5 video)
     ├─ 快捷键 [Space]: 暂停 + 打开截图面板
     ├─ 鼠标框选: 局部截图（框选关键区域）
     ├─ 点击全屏截图: 完整帧
     ├─ 快速备注输入框
     └─ 快速标签按钮 (俚语/道具/人物/音乐)
     │
     ↓
[原始记录 JSON]
{
  "episode_id": "that70s_s01e01",
  "observations": [
    {
      "id": "obs_001",
      "timecode": 754.5,
      "frame_path": "frames/obs_001_full.png",
      "crop_path": "frames/obs_001_crop.png",
      "crop_region": {"x": 320, "y": 180, "width": 400, "height": 300},
      "note": "这个海报好像有意思",
      "tag": "prop",
      "created_at": "2026-02-02T20:30:00Z"
    }
  ]
}
```

**前端交互设计**：
```
┌─────────────────────────────────────────────────────────────┐
│  [视频播放区域]                                              │
│  ┌───────────────────────────────────────────────────────┐ │
│  │                                                       │ │
│  │     ┌─────────┐  ← 鼠标框选局部截图                   │ │
│  │     │  道具   │                                       │ │
│  │     └─────────┘                                       │ │
│  │                                                       │ │
│  └───────────────────────────────────────────────────────┘ │
│  [进度条] ─────●────────────────────────── 12:34 / 22:00   │
├─────────────────────────────────────────────────────────────┤
│  [观察记录面板]                                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ [截图预览]  备注: _______________                       ││
│  │             标签: [俚语] [道具] [人物] [音乐] [其他]    ││
│  │                                        [保存] [取消]   ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

**设计原则**：
- 不要求结构化、不要求完整
- 只抓住"当下觉得有意思的点"
- 操作延迟 < 500ms，不打断观影
- 支持局部截图聚焦关键元素

### 4.2 阶段 B: AI 离线整理

```
[原始记录]
     │
     ↓
[AI 分析引擎]
├─ 图像理解 (GPT-4o Vision)
│   └─ 输入: 局部截图 (crop_path) 优先，否则全帧
│   └─ 识别: 道具、海报、服装、表情
├─ 台词获取 (Whisper 局部转录)
│   └─ 提取: 截图前后 10 秒对白
├─ 文化解读 (Grok)
│   └─ 解释: 俚语、双关、时代背景
└─ 叙事分析 (Grok)
    └─ 关联: 与剧情走向的隐含联系
     │
     ↓
[结构化解读 JSON]
{
  "insights": [
    {
      "observation_id": "obs_001",
      "type": "slang",
      "context_en": "You're skating on thin ice, man.",
      "context_zh": "你在玩火，老兄。",
      "explanation": "70 年代常见俚语，表示处境危险...",
      "why_it_matters": "这里暗示 Eric 和 Red 的关系已经紧张到临界点...",
      "visual_elements": ["Red 的表情变化", "背景音乐突然变轻"],
      "edit_hint": "slow_zoom"
    }
  ]
}
```

### 4.3 阶段 C: 解说视频生成

```
[结构化解读]
     │
     ↓
[脚本生成器]
├─ 选择 Top N 有价值的点
├─ 生成解说大纲
└─ 撰写口播稿（可直接朗读）
     │
     ↓
[视频渲染器]
├─ Ken Burns 效果 (平移/缩放)
├─ 低干扰标注 (highlight, arrow)
├─ AI/人工配音
├─ 中英字幕
└─ 背景音乐 + Ducking
     │
     ↓
[YouTube 就绪视频]
```

---

## 5. 数据模型设计

### 5.1 Episode (剧集)

```python
class Episode(BaseModel):
    """一集剧的元数据"""
    episode_id: str          # e.g., "that70s_s01e01"
    show_name: str           # e.g., "That '70s Show"
    season: int
    episode: int
    title: str
    video_path: Optional[str]
    duration: float
    created_at: datetime
```

### 5.2 Observation (观影记录)

```python
class ObservationType(str, Enum):
    SLANG = "slang"           # 俚语/表达
    PROP = "prop"             # 道具/布景
    CHARACTER = "character"   # 人物/表情
    MUSIC = "music"           # 音乐/声音
    VISUAL = "visual"         # 视觉隐喻
    GENERAL = "general"       # 一般好奇

class CropRegion(BaseModel):
    """局部截图的裁剪区域"""
    x: int                    # 左上角 X
    y: int                    # 左上角 Y
    width: int                # 宽度
    height: int               # 高度

class Observation(BaseModel):
    """单次观影记录"""
    id: str
    episode_id: str
    timecode: float           # 秒
    frame_path: str           # 完整帧截图路径
    crop_path: Optional[str]  # 局部截图路径（框选区域）
    crop_region: Optional[CropRegion]  # 裁剪区域坐标
    note: str                 # 原始备注
    voice_note_path: Optional[str]  # 语音备注（可选）
    tag: ObservationType
    created_at: datetime
```

### 5.3 Insight (AI 解读)

```python
class InsightType(str, Enum):
    LANGUAGE = "language"     # 语言解释
    CULTURE = "culture"       # 文化背景
    NARRATIVE = "narrative"   # 叙事分析
    VISUAL = "visual"         # 视觉解读

class Insight(BaseModel):
    """AI 生成的解读"""
    id: str
    observation_id: str
    type: InsightType
    context_en: str           # 相关英文台词
    context_zh: str           # 中文翻译
    explanation: str          # 详细解释
    why_it_matters: str       # 为什么重要
    visual_elements: List[str]  # 视觉元素描述
    confidence: float         # 置信度 0-1
    edit_hint: str            # 剪辑建议
    created_at: datetime
```

### 5.4 Commentary (解说脚本)

```python
class CommentaryStatus(str, Enum):
    DRAFT = "draft"
    READY = "ready"
    RENDERED = "rendered"
    PUBLISHED = "published"

class CommentarySection(BaseModel):
    """解说的一个段落"""
    insight_id: str
    order: int
    script_zh: str            # 中文解说词
    script_en: str            # 英文解说词（可选）
    duration_estimate: float  # 预估时长
    visual_style: str         # 视觉处理方式

class Commentary(BaseModel):
    """完整解说脚本"""
    id: str
    episode_id: str
    title: str                # 视频标题
    hook: str                 # 开场钩子
    sections: List[CommentarySection]
    outro: str                # 结尾
    status: CommentaryStatus
    video_path: Optional[str]
    youtube_id: Optional[str]
    created_at: datetime
    published_at: Optional[datetime]
```

---

## 6. API 设计

### 6.1 观影记录 API

```
# 创建观影会话
POST /scenemind/sessions
{
  "episode_id": "that70s_s01e01",
  "video_path": "/path/to/video.mp4"
}

# 添加观察记录（支持局部截图）
POST /scenemind/sessions/{session_id}/observations
{
  "timecode": 754.5,
  "note": "这个海报好像有意思",
  "tag": "prop",
  "crop_region": {          // 可选，局部截图区域
    "x": 320,
    "y": 180,
    "width": 400,
    "height": 300
  }
}
# 返回:
# {
#   "id": "obs_001",
#   "frame_url": "/api/media/frames/obs_001_full.png",
#   "crop_url": "/api/media/frames/obs_001_crop.png",
#   "crop_region": {...}
# }

# 获取会话所有记录
GET /scenemind/sessions/{session_id}/observations
```

### 6.2 AI 分析 API

```
# 触发 AI 分析
POST /scenemind/sessions/{session_id}/analyze
{
  "text_model": "grok-4-fast-non-reasoning",  // 文化/语言分析
  "vision_model": "gpt-4o",                    // 图像理解
  "include_vision": true,                      // 是否分析截图
  "prefer_crop": true                          // 优先使用局部截图
}

# 获取分析结果
GET /scenemind/sessions/{session_id}/insights

# 单个观察的分析结果
GET /scenemind/observations/{observation_id}/insight
```

### 6.3 解说生成 API

```
# 生成解说脚本
POST /scenemind/sessions/{session_id}/commentary
{
  "max_points": 7,
  "style": "casual",
  "language": "zh"
}

# 获取/编辑脚本
GET /scenemind/commentaries/{commentary_id}
PATCH /scenemind/commentaries/{commentary_id}

# 渲染视频
POST /scenemind/commentaries/{commentary_id}/render
{
  "voice": "xtts",
  "music": true,
  "resolution": "1080p"
}
```

---

## 7. 技术模块

### 7.1 截图捕获

```python
# backend/app/workers/scenemind/frame_capture.py

async def capture_frame(
    video_path: Path,
    timecode: float,
    output_dir: Path,
) -> Path:
    """使用 FFmpeg 提取指定时间点的帧"""
    output_path = output_dir / f"frame_{timecode:.3f}.png"
    cmd = [
        "ffmpeg", "-ss", str(timecode),
        "-i", str(video_path),
        "-frames:v", "1",
        "-q:v", "2",
        str(output_path)
    ]
    # ...
```

### 7.2 AI 分析引擎

```python
# backend/app/workers/scenemind/ai_expand.py

class SceneMindAnalyzer:
    """双模型分析引擎: Grok (文本) + GPT-4o Vision (图像)"""

    def __init__(self):
        # Grok 客户端 (文本分析)
        self.grok_client = AsyncOpenAI(
            api_key=settings.llm_api_key,
            base_url="https://api.x.ai/v1"
        )
        # OpenAI 客户端 (图像理解)
        self.vision_client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url="https://api.openai.com/v1"
        )

    async def analyze_observation(
        self,
        observation: Observation,
        context_window: float = 10.0,
    ) -> Insight:
        """
        分析流程:
        1. 获取截图前后的台词 (Whisper)
        2. 图像理解 (GPT-4o Vision) - 优先使用局部截图
        3. 文化/语言解读 (Grok)
        """
        # 获取上下文台词
        transcript = await self.get_context_transcript(
            observation.video_path,
            observation.timecode - context_window,
            observation.timecode + context_window
        )

        # 选择截图：优先使用局部截图（更聚焦）
        image_path = observation.crop_path or observation.frame_path

        # Step 1: GPT-4o Vision 分析图像
        vision_analysis = await self.analyze_image(image_path, observation.note)

        # Step 2: Grok 综合分析
        insight = await self.generate_insight(
            observation=observation,
            transcript=transcript,
            vision_analysis=vision_analysis,
        )

        return insight

    async def analyze_image(
        self,
        image_path: str,
        user_note: str,
    ) -> str:
        """使用 GPT-4o Vision 分析截图"""
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode()

        # 构建 Vision API prompt
        vision_prompt = (
            f"The user found this frame interesting while watching a TV show. "
            f"User note: '{user_note}'. "
            f"Describe the key visual elements (facial expressions, props, posters, "
            f"costumes, set design, etc.) in detail."
        )

        response = await self.vision_client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": vision_prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_data}"}}
                ]
            }],
            max_tokens=500
        )
        return response.choices[0].message.content

    async def generate_insight(
        self,
        observation: Observation,
        transcript: str,
        vision_analysis: str,
    ) -> Insight:
        """使用 Grok 生成文化/语言解读"""
        # 构建分析 prompt
        prompt = f"""
        While watching {observation.show_name} Season {observation.season} Episode {observation.episode},
        the viewer noted this at {observation.timecode}s: "{observation.note}"

        Visual analysis: {vision_analysis}
        Surrounding dialogue: {transcript}

        Please analyze:
        1. What language/cultural references are present? (slang, puns, period-specific usage)
        2. Why might a typical viewer not understand this?
        3. How does this connect to the plot/character development?
        4. What visual treatment would you recommend for a commentary video?

        Return JSON format:
        {{
            "type": "language|culture|narrative|visual",
            "context_en": "relevant English dialogue",
            "context_zh": "Chinese translation",
            "explanation": "detailed explanation in Chinese",
            "why_it_matters": "significance in Chinese",
            "visual_elements": ["element1", "element2"],
            "edit_hint": "zoom_to_crop|slow_zoom|highlight|split_screen"
        }}
        """

        response = await self.grok_client.chat.completions.create(
            model="grok-4-fast-non-reasoning",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        # ...
```

### 7.3 视频渲染

```python
# backend/app/workers/scenemind/video_render.py

class CommentaryRenderer:
    """解说视频渲染器"""

    async def render(
        self,
        commentary: Commentary,
        output_path: Path,
    ) -> Path:
        """
        渲染流程:
        1. 为每个 section 创建视觉素材（含特写动画）
        2. 生成配音
        3. 组装时间线
        4. 添加字幕
        5. 混音输出
        """

    async def create_focus_animation(
        self,
        frame_path: Path,
        crop_region: CropRegion,
        duration: float,
        hold_time: float = 2.0,
    ) -> Path:
        """
        特写动画效果（基于框选坐标）

        动画流程:
        1. 从全画面开始 (0.5s)
        2. 平滑缩放到框选区域 (0.8s ease-in-out)
        3. 停顿展示特写 (hold_time)
        4. [可选] 缩放回全画面

        FFmpeg filter 示例:
        zoompan=z='if(lt(on,15),1,min(1.5,1+0.033*(on-15)))':
               x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':
               d=1:s=1920x1080:fps=30
        """

    async def create_ken_burns(
        self,
        frame_path: Path,
        duration: float,
        style: str,  # "zoom_in", "zoom_out", "pan_left", "pan_right"
    ) -> Path:
        """简单 Ken Burns 效果（无框选坐标时使用）"""

    async def add_highlight(
        self,
        video_path: Path,
        region: Tuple[int, int, int, int],
        style: str,  # "box", "arrow", "blur_rest", "spotlight"
    ) -> Path:
        """添加视觉标注（高亮/箭头/聚光灯效果）"""
```

**特写动画时序图**：

```
时间:  0s    0.5s   1.3s        3.3s   4s
      ├──────┼──────┼───────────┼──────┤
      │ 全景 │ 缩放 │   特写    │ 恢复 │
      │ 展示 │ 过渡 │   停顿    │ 全景 │
      └──────┴──────┴───────────┴──────┘
             ↑                   ↑
        crop_region          解说播放
        坐标生效              开始点
```

**FFmpeg 实现思路**：

```python
async def create_focus_animation(
    self,
    frame_path: Path,
    crop_region: CropRegion,
    output_path: Path,
    total_duration: float = 4.0,
) -> Path:
    """
    使用 FFmpeg zoompan filter 实现特写动画

    crop_region 坐标转换为 zoompan 参数:
    - 计算目标缩放比例 (原始宽度 / 框选宽度)
    - 计算目标中心点 (框选区域中心)
    - 生成平滑过渡的 zoom 和 pan 表达式
    """
    # 计算缩放参数
    zoom_factor = min(
        1920 / crop_region.width,
        1080 / crop_region.height,
        3.0  # 最大 3x 缩放
    )

    # 计算目标中心点（归一化坐标）
    target_x = (crop_region.x + crop_region.width / 2) / 1920
    target_y = (crop_region.y + crop_region.height / 2) / 1080

    # FFmpeg zoompan 表达式
    # on = 帧序号, fps=30
    # 前 15 帧 (0.5s) 保持全景
    # 15-39 帧 (0.8s) 平滑缩放
    # 39-99 帧 (2s) 保持特写
    # 99-120 帧 (0.7s) 平滑恢复

    filter_expr = f'''
    zoompan=z='if(lt(on,15),1,
                 if(lt(on,39),1+{zoom_factor-1}*(on-15)/24,
                 if(lt(on,99),{zoom_factor},
                 {zoom_factor}-({zoom_factor-1})*(on-99)/21)))':
            x='iw*{target_x}-(iw/zoom/2)':
            y='ih*{target_y}-(ih/zoom/2)':
            d=1:s=1920x1080:fps=30
    '''

    cmd = [
        "ffmpeg", "-loop", "1", "-i", str(frame_path),
        "-vf", filter_expr,
        "-t", str(total_duration),
        "-pix_fmt", "yuv420p",
        str(output_path)
    ]
    # ...
```

---

## 8. MVP 定义

### 8.1 范围

**只实现**：
- [x] Next.js 前端 + 视频播放 + 局部截图 + 快速备注
- [x] AI 自动整理为解说大纲 + 脚本 (Grok + GPT-4o Vision)
- [x] 特写动画 + Ken Burns + XTTS 配音

**不实现**：
- [ ] 自动说话人识别
- [ ] 复杂视觉效果
- [ ] 多平台发布
- [ ] 用户系统

### 8.2 目标输出

**只跑通一集**：That '70s Show - 任意一集（Eric 相关）

预期产出：
- 一条 3-5 分钟的 YouTube 解说视频
- 包含 5-7 个文化/语言解读点
- 中文配音 + 中英字幕

### 8.3 技术栈

| 模块 | 技术选型 | 原因 |
|------|---------|------|
| 前端交互 | **Next.js 前端集成** | 复用现有 Review UI |
| 播放/截图 | FFmpeg + Canvas | 全帧 + 局部框选 |
| 数据存储 | JSON | 复用现有 |
| AI 文本分析 | **Grok** (`grok-4-fast-non-reasoning`) | 已集成，无审查 |
| AI 图像理解 | **GPT-4o Vision** | 最佳效果 |
| 配音 | XTTS | 复用现有 |
| 剪辑 | FFmpeg | 复用现有 |
| 字幕 | ASS 格式 | 复用现有 |

---

## 9. 实现路线图

### Phase 1: 基础捕获 (Week 1)

- [ ] `Observation` 数据模型
- [ ] 截图提取 worker (全帧 + 局部裁剪)
- [ ] Next.js 前端观影组件 (视频播放 + 框选截图)
- [ ] 基础 API 端点

### Phase 2: AI 分析 (Week 2)

- [ ] `Insight` 数据模型
- [ ] GPT-4o + Vision 分析引擎
- [ ] 上下文台词提取
- [ ] 分析结果存储

### Phase 3: 脚本生成 (Week 3)

- [ ] `Commentary` 数据模型
- [ ] 脚本大纲生成
- [ ] 口播稿撰写
- [ ] 脚本编辑 API

### Phase 4: 视频渲染 (Week 4)

- [ ] Ken Burns 效果
- [ ] TTS 配音集成
- [ ] 字幕生成
- [ ] 视频合成输出

### Phase 5: 端到端测试 (Week 5)

- [ ] That '70s Show 一集完整流程
- [ ] 效果评估
- [ ] 迭代优化

---

## 10. 项目护城河

1. **真实观影痕迹** - 内容源自真实观影过程，不可复制
2. **个人注意力轨迹** - 记录的是创作者独特的视角
3. **长期素材积累** - 累积可复用的语义素材库
4. **AI 放大判断** - AI 放大理解，而非替代判断
5. **质量自然提升** - 内容质量随时间自然提升

---

## 11. 附录

### A. 示例输出

**解说视频标题方向**：
- 《你可能没注意到的几句台词，其实改变了这一集的走向》
- 《这张海报为什么会出现在这里？》
- 《这一集里，被忽略的 7 个文化细节》

**视频风格定位**：
- 不做剧情复述
- 不做学院派术语
- 像"有人陪你一起重新看这集剧"

### B. 原始记录示例

```json
{
  "timecode": "00:12:34",
  "snapshot": "frame_1234.png",
  "note": "这句好像不是字面意思"
}
```

### C. AI 整理后示例

```json
{
  "time": "00:12:34",
  "type": "slang",
  "explanation": "70 年代常见俚语，表示关系已经不可挽回",
  "why_it_matters": "这里暗示人物态度已经发生转变",
  "edit_hint": "slow_zoom"
}
```

---

## 12. 技术决策记录

### 2026-02-02 初始决策

| 决策点 | 选择 | 原因 |
|--------|------|------|
| 交互方式 | **集成到 Next.js 前端** | 复用现有 Review UI，视频播放器已有 |
| AI 文本分析 | **Grok** (`grok-4-fast-non-reasoning`) | 项目已集成，无内容审查，成本低 |
| AI 图像理解 | **GPT-4o Vision** | Grok 暂无 Vision API，GPT-4V 效果最好 |
| 配音方案 | **XTTS 自动配音** | 复用现有 TTS worker，全自动 |
| 截图方式 | **支持局部截图（框选区域）** | 聚焦关键道具/表情，提升分析精度 |

---

**文档版本**: v1.1
**创建日期**: 2026-02-02
**更新日期**: 2026-02-02
**项目代号**: SceneMind
