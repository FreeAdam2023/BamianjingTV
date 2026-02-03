# Unified Video Factory Architecture

> 统一视频处理架构：学习、观影、配音三种模式

## 概述

Hardcore Player 演进为统一视频处理平台，支持三种核心工作流：

| 模式 | 目标用户 | 核心功能 | 输出 |
|------|---------|---------|------|
| **Learning** | 语言学习者 | 原音 + 双语字幕 + 单词卡片 | 学习视频 |
| **Watching** | 影视爱好者 | 原音 + 透明字幕 + 场景截图 | 解说/精华视频 |
| **Dubbing** | 内容创作者 | 克隆配音 + 口型同步 | 本地化成片 |

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Unified Video Factory                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │                    Shared Pipeline                          │     │
│  │  Download → Transcribe → Diarize → Translate → NER/Cards   │     │
│  └────────────────────────────────────────────────────────────┘     │
│                              ↓                                       │
│  ┌─────────────────┬─────────────────┬─────────────────────────┐    │
│  │  Learning Mode  │  Watching Mode  │     Dubbing Mode        │    │
│  │    学习模式      │    观影模式      │       配音模式          │    │
│  ├─────────────────┼─────────────────┼─────────────────────────┤    │
│  │ • 原音保留       │ • 原音保留       │ • 音色克隆/相似配音     │    │
│  │ • 半屏双语字幕   │ • 透明悬浮字幕   │ • 可选口型同步          │    │
│  │ • 可点击卡片     │ • 可点击卡片     │ • 背景音保留            │    │
│  │ • 单词/实体学习  │ • 场景截图备注   │ • 字幕样式可选          │    │
│  └─────────────────┴─────────────────┴─────────────────────────┘    │
│                              ↓                                       │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │                    Shared Features                          │     │
│  │  可点击字幕 · 单词/实体卡片 · 记忆本 · Anki导出 · 审阅UI     │     │
│  └────────────────────────────────────────────────────────────┘     │
│                              ↓                                       │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │                    Export Profiles                          │     │
│  │  full_subtitled · essence_clips · dubbed_video · anki_deck │     │
│  └────────────────────────────────────────────────────────────┘     │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Pipeline 详解

### 1. 共享 Pipeline (所有模式)

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ Download │ →  │Transcribe│ →  │ Diarize  │ →  │Translate │ →  │ NER/Card │
│ yt-dlp   │    │ Whisper  │    │ pyannote │    │ GPT-4o   │    │ Optional │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
     ↓               ↓               ↓               ↓               ↓
  video.mp4      raw.json      diarized.json    zh.json       cards.json
  audio.wav
```

### 2. Learning Mode Pipeline

```
共享 Pipeline
     ↓
┌─────────────────────────────────────┐
│         Learning Specific           │
├─────────────────────────────────────┤
│ • 生成单词/实体卡片数据              │
│ • 词典查询 + 维基百科实体解析         │
│ • 字幕分段优化 (适合学习)            │
└─────────────────────────────────────┘
     ↓
┌─────────────────────────────────────┐
│         Export: Learning            │
├─────────────────────────────────────┤
│ • 半屏字幕渲染 (上英下中)            │
│ • 保留原音轨                         │
│ • 可选: 导出 Anki 卡片组             │
└─────────────────────────────────────┘
```

### 3. Watching Mode Pipeline

```
共享 Pipeline
     ↓
┌─────────────────────────────────────┐
│         Watching Specific           │
├─────────────────────────────────────┤
│ • 场景截图 + 备注 (Observations)     │
│ • 精华片段标记 (Keep/Drop)           │
│ • 解说脚本生成 (可选)                │
└─────────────────────────────────────┘
     ↓
┌─────────────────────────────────────┐
│         Export: Watching            │
├─────────────────────────────────────┤
│ • 透明悬浮字幕渲染                   │
│ • 精华剪辑 (Essence)                │
│ • 解说配音叠加 (可选)                │
└─────────────────────────────────────┘
```

### 4. Dubbing Mode Pipeline

```
共享 Pipeline
     ↓
┌─────────────────────────────────────┐
│     Audio Separation (Demucs)       │
├─────────────────────────────────────┤
│ • 分离人声 (vocals)                  │
│ • 分离背景音乐 (bgm)                 │
│ • 分离环境音 (sfx)                   │
└─────────────────────────────────────┘
     ↓
┌─────────────────────────────────────┐
│     Voice Clone / TTS               │
├─────────────────────────────────────┤
│ • 提取说话人音色样本                  │
│ • 克隆音色 (XTTS v2 / GPT-SoVITS)   │
│ • 或选择相似预设音色 (规避法律风险)   │
│ • 按说话人分别合成配音                │
│ • 时长对齐 (语速调整)                │
└─────────────────────────────────────┘
     ↓
┌─────────────────────────────────────┐
│     Lip Sync (Optional)             │
├─────────────────────────────────────┤
│ • 人脸检测 + 追踪                    │
│ • 音频驱动口型生成 (Wav2Lip)         │
│ • 或 3D 面部重建 (SadTalker)        │
│ • 视频帧替换                         │
└─────────────────────────────────────┘
     ↓
┌─────────────────────────────────────┐
│     Audio Mixing                    │
├─────────────────────────────────────┤
│ • 配音 + BGM + SFX 混合             │
│ • 音量平衡 + 淡入淡出                │
│ • 可选: 保留部分原音                 │
└─────────────────────────────────────┘
     ↓
┌─────────────────────────────────────┐
│         Export: Dubbed              │
├─────────────────────────────────────┤
│ • 配音视频 (替换音轨)                │
│ • 可选字幕 (无/单语/双语)            │
│ • 可选口型同步版本                   │
└─────────────────────────────────────┘
```

---

## 数据模型

### Job 模型

```python
class JobMode(str, Enum):
    """视频处理模式"""
    LEARNING = "learning"    # 学习模式: 原音 + 双语字幕
    WATCHING = "watching"    # 观影模式: 原音 + 透明字幕 + 截图
    DUBBING = "dubbing"      # 配音模式: 克隆配音 + 口型同步

class Job(BaseModel):
    id: str
    url: str
    mode: JobMode = JobMode.LEARNING
    status: JobStatus

    # 共享配置
    target_language: str = "zh"
    skip_diarization: bool = False

    # 模式特定配置
    learning_config: Optional[LearningConfig] = None
    watching_config: Optional[WatchingConfig] = None
    dubbing_config: Optional[DubbingConfig] = None
```

### 模式配置

```python
class LearningConfig(BaseModel):
    """学习模式配置"""
    subtitle_style: str = "half_screen"    # half_screen, floating
    generate_cards: bool = True             # 生成单词/实体卡片
    card_types: List[str] = ["word", "entity"]
    use_traditional_chinese: bool = True

class WatchingConfig(BaseModel):
    """观影模式配置"""
    subtitle_style: str = "floating"        # floating, none
    enable_observations: bool = True        # 启用场景截图
    generate_commentary: bool = False       # 生成解说脚本

class DubbingConfig(BaseModel):
    """配音模式配置"""
    # 音色设置
    voice_clone: bool = True                # 克隆原音色
    voice_model: str = "xtts_v2"            # xtts_v2, gpt_sovits, preset
    voice_preset: Optional[str] = None      # 预设音色 ID
    voice_similarity: float = 0.8           # 音色相似度 (0-1, 越低越安全)

    # 口型同步
    lip_sync: bool = False                  # 启用口型同步
    lip_sync_model: str = "wav2lip"         # wav2lip, sadtalker

    # 音频混合
    keep_bgm: bool = True                   # 保留背景音乐
    keep_sfx: bool = True                   # 保留环境音效
    bgm_volume: float = 0.3                 # 背景音量 (0-1)

    # 字幕
    subtitle_style: str = "none"            # none, floating, half_screen
    subtitle_language: str = "target"       # source, target, both
```

### Timeline 模型扩展

```python
class Timeline(BaseModel):
    timeline_id: str
    job_id: str
    mode: JobMode

    # 共享字段
    source_url: str
    source_title: str
    source_duration: float
    segments: List[EditableSegment]

    # 卡片数据 (Learning + Watching)
    cards_generated: bool = False
    word_cards: Dict[str, WordCard] = {}      # word -> card data
    entity_cards: Dict[str, EntityCard] = {}  # entity_id -> card data

    # 观察记录 (Watching)
    observations: List[Observation] = []

    # 配音数据 (Dubbing)
    dubbing_config: Optional[DubbingConfig] = None
    speaker_voices: Dict[str, SpeakerVoice] = {}  # speaker_id -> voice config
    dubbed_segments: List[DubbedSegment] = []

    # 导出状态
    export_status: ExportStatus
    export_outputs: Dict[str, str] = {}       # profile -> output_path
```

### 卡片模型 (参考 TomTrovePlayer)

```python
class WordCard(BaseModel):
    """单词卡片"""
    word: str
    lemma: str                              # 词根
    pronunciations: List[Pronunciation]     # IPA + 音频
    senses: List[WordSense]                 # 词义列表
    examples: List[Example]                 # 例句
    images: List[str]                       # 图片 URL

class EntityCard(BaseModel):
    """实体卡片 (人物/地点/组织/概念)"""
    entity_id: str                          # Wikidata QID
    entity_type: str                        # person, place, organization, concept
    name: str
    description: str
    wikipedia_url: Optional[str]
    image_url: Optional[str]
    localizations: Dict[str, EntityLocalization]  # 多语言数据

class Observation(BaseModel):
    """场景观察记录"""
    id: str
    session_id: str
    timecode: float
    frame_path: str
    crop_path: Optional[str]
    crop_region: Optional[CropRegion]
    note: str
    tag: ObservationType                    # slang, prop, character, music, visual
    linked_cards: List[str] = []            # 关联的卡片 ID

class MemoryItem(BaseModel):
    """记忆本项目"""
    item_id: str
    target_type: str                        # word, entity, observation
    target_id: str
    source_video_id: str
    source_timecode: float
    user_notes: str
    tags: List[str]
    created_at: datetime
```

### 配音相关模型

```python
class SpeakerVoice(BaseModel):
    """说话人音色配置"""
    speaker_id: str
    speaker_name: str
    original_sample_path: str               # 原音色样本
    cloned_voice_id: Optional[str]          # 克隆后的音色 ID
    preset_voice_id: Optional[str]          # 预设音色 ID
    use_clone: bool = True

class DubbedSegment(BaseModel):
    """配音片段"""
    segment_id: int
    speaker_id: str
    original_text: str
    translated_text: str
    original_duration: float
    dubbed_audio_path: str
    dubbed_duration: float
    speed_ratio: float                      # 语速调整比例
    lip_synced: bool = False
```

---

## Workers

### 现有 Workers

| Worker | 功能 | 技术栈 | GPU |
|--------|------|--------|-----|
| `DownloadWorker` | 视频下载 | yt-dlp | No |
| `WhisperWorker` | 语音转录 | faster-whisper | Yes |
| `DiarizationWorker` | 说话人分离 | pyannote.audio | Yes |
| `TranslationWorker` | 翻译 | OpenAI GPT-4o | No |
| `ExportWorker` | 字幕渲染导出 | FFmpeg NVENC | Yes |

### 新增 Workers

| Worker | 功能 | 技术栈 | GPU |
|--------|------|--------|-----|
| `NERWorker` | 命名实体识别 | spaCy / OpenAI | No |
| `CardGeneratorWorker` | 卡片数据生成 | Dictionary API + Wikidata | No |
| `AudioSeparationWorker` | 音频分离 | Demucs | Yes |
| `VoiceCloneWorker` | 音色克隆 + TTS | XTTS v2 / GPT-SoVITS | Yes |
| `LipSyncWorker` | 口型同步 | Wav2Lip / SadTalker | Yes |
| `AudioMixerWorker` | 音轨混合 | FFmpeg | No |

---

## API 端点

### Job API (扩展)

```
POST   /jobs                              # 创建任务 (指定 mode)
GET    /jobs/{id}                         # 获取任务详情
PATCH  /jobs/{id}/config                  # 更新模式配置
```

### Timeline API (扩展)

```
# 卡片相关
GET    /timelines/{id}/cards              # 获取所有卡片
GET    /timelines/{id}/cards/word/{word}  # 获取单词卡片
GET    /timelines/{id}/cards/entity/{id}  # 获取实体卡片
POST   /timelines/{id}/cards/generate     # 触发卡片生成

# 观察记录
GET    /timelines/{id}/observations       # 获取观察列表
POST   /timelines/{id}/observations       # 添加观察 (自动截图)
DELETE /timelines/{id}/observations/{id}  # 删除观察

# 配音相关
GET    /timelines/{id}/dubbing/speakers   # 获取说话人列表
POST   /timelines/{id}/dubbing/preview    # 预览配音片段
POST   /timelines/{id}/dubbing/generate   # 生成完整配音
```

### 记忆本 API

```
GET    /memory-books                      # 获取记忆本列表
POST   /memory-books                      # 创建记忆本
GET    /memory-books/{id}/items           # 获取记忆项
POST   /memory-books/{id}/items           # 添加记忆项
DELETE /memory-books/{id}/items/{item_id} # 删除记忆项
GET    /memory-books/{id}/export/anki     # 导出 Anki 卡片组
```

### 导出 API (扩展)

```
POST   /timelines/{id}/export
Body: {
  "profile": "full_subtitled" | "essence_clips" | "dubbed_video" | "anki_deck",
  "options": { ... }
}
```

---

## 前端组件

### 共享组件

```
components/
├── VideoPlayer/
│   ├── index.tsx                    # 主播放器
│   ├── SubtitleOverlay.tsx          # 字幕叠加层
│   ├── ClickableSubtitle.tsx        # 可点击字幕 (NEW)
│   └── VideoControls.tsx            # 控制栏
├── Cards/
│   ├── WordCard.tsx                 # 单词卡片弹窗 (NEW)
│   ├── EntityCard.tsx               # 实体卡片弹窗 (NEW)
│   └── CardCache.ts                 # 卡片缓存逻辑 (NEW)
├── Timeline/
│   ├── SegmentList.tsx              # 片段列表
│   ├── WaveformTrack.tsx            # 波形轨道
│   └── ObservationMarkers.tsx       # 观察点标记 (NEW)
└── MemoryBook/
    ├── MemoryBookList.tsx           # 记忆本列表 (NEW)
    ├── MemoryItemCard.tsx           # 记忆项卡片 (NEW)
    └── AnkiExportDialog.tsx         # Anki导出对话框 (NEW)
```

### 模式特定页面

```
app/
├── review/[timelineId]/
│   └── page.tsx                     # Learning 模式审阅页
├── watch/[timelineId]/
│   └── page.tsx                     # Watching 模式观影页
└── dub/[timelineId]/
    ├── page.tsx                     # Dubbing 模式主页
    ├── VoiceConfig.tsx              # 音色配置面板
    └── LipSyncPreview.tsx           # 口型同步预览
```

---

## 数据存储

```
data/
├── timelines/
│   └── {timeline_id}.json           # Timeline 数据 (含 mode)
├── cards/
│   ├── words/
│   │   └── {word}.json              # 单词卡片缓存
│   └── entities/
│       └── {entity_id}.json         # 实体卡片缓存
├── observations/
│   └── {timeline_id}/
│       ├── obs_{id}_full.png        # 全帧截图
│       └── obs_{id}_crop.png        # 裁剪截图
├── memory_books/
│   └── {book_id}.json               # 记忆本数据
└── voices/
    └── {timeline_id}/
        ├── speaker_{id}_sample.wav  # 原音色样本
        └── speaker_{id}_dubbed/     # 配音音频
            └── seg_{id}.wav

jobs/
└── {job_id}/
    ├── meta.json
    ├── source/
    │   ├── video.mp4
    │   └── audio.wav
    ├── separated/                   # 音频分离结果 (Dubbing)
    │   ├── vocals.wav
    │   ├── bgm.wav
    │   └── sfx.wav
    ├── dubbed/                      # 配音结果 (Dubbing)
    │   ├── full_dubbed.wav
    │   └── mixed.wav
    ├── lip_synced/                  # 口型同步结果 (Dubbing)
    │   └── video_lip_synced.mp4
    └── output/
        ├── learning_full.mp4        # 学习模式输出
        ├── watching_essence.mp4     # 观影模式输出
        └── dubbed_final.mp4         # 配音模式输出
```

---

## 实施计划

### Phase 1: 统一模型 + 观影模式合并
- [ ] 扩展 Job 模型支持 mode 字段
- [ ] 扩展 Timeline 模型支持 observations
- [ ] 合并 SceneMind 功能到 Timeline
- [ ] 添加透明字幕渲染选项

### Phase 2: 卡片系统
- [ ] 实现 NERWorker (命名实体识别)
- [ ] 实现 CardGeneratorWorker
- [ ] 前端: ClickableSubtitle 组件
- [ ] 前端: WordCard + EntityCard 弹窗

### Phase 3: 记忆本
- [ ] 实现 MemoryBook 模型和 API
- [ ] 前端: 记忆本 UI
- [ ] Anki 导出功能

### Phase 4: 配音模式基础
- [ ] 实现 AudioSeparationWorker (Demucs)
- [ ] 实现 VoiceCloneWorker (XTTS v2)
- [ ] 实现 AudioMixerWorker
- [ ] 前端: 配音模式 UI

### Phase 5: 口型同步 (可选)
- [ ] 实现 LipSyncWorker (Wav2Lip)
- [ ] 人脸检测 + 追踪
- [ ] 前端: 口型同步预览

---

## 技术栈

| 组件 | 技术 | 用途 |
|------|------|------|
| 后端框架 | FastAPI | API 服务 |
| 语音识别 | faster-whisper (large-v3) | 转录 |
| 说话人分离 | pyannote.audio | 多人对话 |
| 翻译 | OpenAI GPT-4o | 中英翻译 |
| 实体识别 | spaCy + Wikidata | NER |
| 音频分离 | Demucs | 人声/背景分离 |
| 音色克隆 | XTTS v2 / GPT-SoVITS | TTS |
| 口型同步 | Wav2Lip / SadTalker | 视频处理 |
| 视频处理 | FFmpeg (NVENC) | 编码/渲染 |
| 前端框架 | Next.js 14 | React UI |
| 状态管理 | React Hooks | 客户端状态 |

---

## 法律风险规避 (配音模式)

1. **音色相似度控制**: 提供 `voice_similarity` 参数 (0-1)，值越低与原音色差异越大
2. **预设音色库**: 提供通用 TTS 音色选项，不使用克隆
3. **水印/声明**: 导出视频自动添加 "AI 配音" 标识
4. **用户协议**: 明确用户需对内容版权负责
5. **仅供个人学习**: 默认设置为私有/不公开

---

## 参考项目

- **TomTrovePlayer**: 单词/实体卡片实现、记忆本、Anki 导出
- **Hardcore Player**: 双语字幕、审阅 UI、导出流程
- **SceneMind**: 场景截图、观察备注

---

*最后更新: 2024-02*
