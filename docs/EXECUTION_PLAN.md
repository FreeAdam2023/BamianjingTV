# Unified Video Factory 执行计划

> 基于 UNIFIED_ARCHITECTURE.md 的详细实施路线图

---

## 现状分析

| 模块 | 状态 | 完成度 |
|------|------|--------|
| **Learning Mode** (原 Hardcore Player) | ✅ 生产可用 | 95% |
| **Watching Mode** (SceneMind) | ✅ Phase 1A 完成 | 90% |
| **Dubbing Mode** | ✅ Phase 2 完成 | 100% |
| **卡片系统** | ✅ Phase 1B 完成 | 100% |
| **透明字幕渲染** | ✅ Phase 1C 完成 | 100% |
| **记忆本** | ✅ Phase 1D 完成 | 100% |

---

## 执行顺序

```
                    ┌─────────────────────────────────┐
                    │   Phase 0: 统一基础设施 (必须)    │
                    │   Job.mode + Timeline 扩展       │
                    └─────────────────┬───────────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              ▼                       ▼                       ▼
    ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
    │  Phase 1A       │     │  Phase 1B       │     │  Phase 2        │
    │  合并 SceneMind │     │  卡片系统        │     │  配音模式       │
    │  (中优先级)      │     │  (高优先级)      │     │  (低优先级)     │
    └────────┬────────┘     └────────┬────────┘     └────────┬────────┘
             │                       │                       │
             ▼                       ▼                       │
    ┌─────────────────┐     ┌─────────────────┐              │
    │  Phase 1C       │     │  Phase 1D       │              │
    │  透明字幕渲染    │     │  记忆本 + Anki  │              │
    └─────────────────┘     └─────────────────┘              │
                                                             ▼
                                                   ┌─────────────────┐
                                                   │  Phase 3        │
                                                   │  口型同步 (可选) │
                                                   └─────────────────┘
```

**推荐执行顺序**: `0 → 1B → 1A → 1C → 1D → 2 → 3`

**理由**:
1. **卡片系统 (1B)** 是三种模式的共享功能，ROI 最高
2. **SceneMind 合并 (1A)** 相对简单，且已有代码
3. **配音模式 (2)** 技术复杂度高，可延后

---

## Phase 0: 统一基础设施

> **目标**: 为三种模式提供统一的数据模型基础
> **预估工时**: 6.5h
> **优先级**: 🔴 必须

### 任务列表

| ID | 任务 | 文件 | 工时 | 状态 |
|----|------|------|------|------|
| 0.1 | 添加 `JobMode` 枚举 | `backend/app/models/job.py` | 0.5h | ✅ |
| 0.2 | 添加模式配置类 `LearningConfig/WatchingConfig/DubbingConfig` | `backend/app/models/job.py` | 1h | ✅ |
| 0.3 | Job 模型添加 `mode` 和 `config` 字段 | `backend/app/models/job.py` | 0.5h | ✅ |
| 0.4 | Timeline 模型添加 `mode` 字段 | `backend/app/models/timeline.py` | 0.5h | ✅ |
| 0.5 | 更新 Job API 支持 `mode` 参数 | `backend/app/api/jobs.py` | 1h | ✅ |
| 0.6 | 更新前端创建 Job 时选择模式 | `frontend/src/app/jobs/page.tsx` | 2h | ✅ |
| 0.7 | 迁移脚本: 现有数据标记为 LEARNING | `scripts/migrate_to_unified.py` | 1h | ✅ |

### 验收标准

- [x] 创建 Job 时可选 mode (默认 LEARNING)
- [x] 现有功能无回归 (30 tests passed)
- [x] 数据迁移脚本可重复执行

### 代码示例

```python
# backend/app/models/job.py

class JobMode(str, Enum):
    """视频处理模式"""
    LEARNING = "learning"    # 学习模式: 原音 + 双语字幕
    WATCHING = "watching"    # 观影模式: 原音 + 透明字幕 + 截图
    DUBBING = "dubbing"      # 配音模式: 克隆配音 + 口型同步

class LearningConfig(BaseModel):
    """学习模式配置"""
    subtitle_style: str = "half_screen"
    generate_cards: bool = True
    card_types: List[str] = ["word", "entity"]

class WatchingConfig(BaseModel):
    """观影模式配置"""
    subtitle_style: str = "floating"
    enable_observations: bool = True

class DubbingConfig(BaseModel):
    """配音模式配置"""
    voice_clone: bool = True
    voice_model: str = "xtts_v2"
    lip_sync: bool = False
    keep_bgm: bool = True

class Job(BaseModel):
    # ... existing fields ...
    mode: JobMode = JobMode.LEARNING
    learning_config: Optional[LearningConfig] = None
    watching_config: Optional[WatchingConfig] = None
    dubbing_config: Optional[DubbingConfig] = None
```

---

## Phase 1B: 卡片系统

> **目标**: 实现可点击字幕 + 单词/实体卡片弹窗
> **预估工时**: 40h
> **优先级**: 🔴 高

### 1B.1 后端 - NER Worker

| ID | 任务 | 文件 | 工时 | 状态 |
|----|------|------|------|------|
| 1B.1.1 | 创建 NERWorker 基础结构 | `backend/app/workers/ner.py` | 1h | ✅ |
| 1B.1.2 | 集成 spaCy 或 OpenAI NER | `backend/app/workers/ner.py` | 2h | ✅ |
| 1B.1.3 | 提取单词 (生词检测逻辑) | `backend/app/workers/ner.py` | 2h | ✅ |
| 1B.1.4 | 提取实体 (人名/地名/组织/概念) | `backend/app/workers/ner.py` | 2h | ✅ |
| 1B.1.5 | 输出格式: segment 级别标注 | `backend/app/workers/ner.py` | 1h | ✅ |

### 1B.2 后端 - Card Generator Worker

| ID | 任务 | 文件 | 工时 | 状态 |
|----|------|------|------|------|
| 1B.2.1 | 创建 CardGeneratorWorker | `backend/app/workers/card_generator.py` | 1h | ✅ |
| 1B.2.2 | 词典 API 集成 (WordsAPI/Free Dictionary) | `backend/app/workers/card_generator.py` | 3h | ✅ |
| 1B.2.3 | Wikidata API 集成 (实体信息) | `backend/app/workers/card_generator.py` | 3h | ✅ |
| 1B.2.4 | 卡片缓存机制 (避免重复查询) | `backend/app/services/card_cache.py` | 2h | ✅ |
| 1B.2.5 | WordCard 模型 | `backend/app/models/card.py` | 1h | ✅ |
| 1B.2.6 | EntityCard 模型 | `backend/app/models/card.py` | 1h | ✅ |

### 1B.3 后端 - API 端点

| ID | 任务 | 文件 | 工时 | 状态 |
|----|------|------|------|------|
| 1B.3.1 | `GET /cards/words/{word}` | `backend/app/api/cards.py` | 1h | ✅ |
| 1B.3.2 | `GET /cards/entities/{entity_id}` | `backend/app/api/cards.py` | 1h | ✅ |
| 1B.3.3 | `GET /cards/entities/search/{query}` | `backend/app/api/cards.py` | 1h | ✅ |
| 1B.3.4 | `POST /cards/timelines/{id}/generate` | `backend/app/api/cards.py` | 1h | ✅ |

### 1B.4 前端 - 可点击字幕

| ID | 任务 | 文件 | 工时 | 状态 |
|----|------|------|------|------|
| 1B.4.1 | ClickableSubtitle 组件 | `frontend/src/components/Cards/ClickableSubtitle.tsx` | 3h | ✅ |
| 1B.4.2 | 字幕文本解析 (单词边界检测) | (集成在 ClickableSubtitle 中) | 2h | ✅ |
| 1B.4.3 | 点击事件处理 + 卡片预加载 | `frontend/src/hooks/useCardPopup.ts` | 2h | ✅ |

### 1B.5 前端 - 卡片弹窗

| ID | 任务 | 文件 | 工时 | 状态 |
|----|------|------|------|------|
| 1B.5.1 | WordCard 弹窗组件 | `frontend/src/components/Cards/WordCard.tsx` | 4h | ✅ |
| 1B.5.2 | EntityCard 弹窗组件 | `frontend/src/components/Cards/EntityCard.tsx` | 4h | ✅ |
| 1B.5.3 | CardPopupContainer (位置计算) | `frontend/src/components/Cards/CardPopupContainer.tsx` | 2h | ✅ |
| 1B.5.4 | 卡片缓存 Hook | `frontend/src/hooks/useCardPopup.ts` | 2h | ✅ |
| 1B.5.5 | 集成到 SegmentList 组件 | `frontend/src/components/SegmentList.tsx` | 2h | ✅ |

### 验收标准

- [x] 字幕中单词可点击
- [x] 点击后显示卡片弹窗 (发音、词义、例句、图片)
- [x] 实体可点击显示维基百科摘要
- [x] 卡片数据有缓存，避免重复 API 调用

### 数据模型

```python
# backend/app/models/card.py

class Pronunciation(BaseModel):
    ipa: str
    audio_url: Optional[str] = None

class WordSense(BaseModel):
    part_of_speech: str      # noun, verb, adj, etc.
    definition: str
    examples: List[str] = []
    synonyms: List[str] = []

class WordCard(BaseModel):
    word: str
    lemma: str                              # 词根
    pronunciations: List[Pronunciation]
    senses: List[WordSense]
    images: List[str] = []
    frequency_rank: Optional[int] = None    # 词频排名

class EntityCard(BaseModel):
    entity_id: str                          # Wikidata QID (e.g., Q42)
    entity_type: str                        # person, place, organization, concept
    name: str
    description: str
    wikipedia_url: Optional[str] = None
    image_url: Optional[str] = None
    birth_date: Optional[str] = None        # for persons
    location: Optional[str] = None          # for places
```

---

## Phase 1A: 合并 SceneMind

> **目标**: 将 SceneMind 观察功能整合到 Timeline 中
> **预估工时**: 13h
> **优先级**: 🟡 中
> **状态**: ✅ 已完成 (核心功能)

### 任务列表

| ID | 任务 | 文件 | 工时 | 状态 |
|----|------|------|------|------|
| 1A.1 | Timeline 模型添加 `observations` 字段 | `backend/app/models/timeline.py` | 1h | ✅ |
| 1A.2 | 迁移 Observation 模型到 timeline 模块 | `backend/app/models/timeline.py` | 1h | ✅ |
| 1A.3 | TimelineManager 添加 observation CRUD | `backend/app/services/timeline_manager.py` | 2h | ✅ |
| 1A.4 | 合并 SceneMind API 到 Timeline API | `backend/app/api/timelines.py` | 2h | ✅ |
| 1A.5 | 迁移 FrameCaptureWorker 到通用 workers | `backend/app/workers/frame_capture.py` | 1h | ✅ |
| 1A.6 | 前端: types + API 函数 | `frontend/src/lib/types.ts, api.ts` | 1h | ✅ |
| 1A.7 | 前端: ObservationCapture + ObservationList | `frontend/src/app/review/[timelineId]/` | 3h | ✅ |
| 1A.8 | 前端: ObservationMarkers 时间轴组件 | `frontend/src/components/timeline/ObservationMarkers.tsx` | 2h | ✅ |
| 1A.9 | 前端: Review 页面集成 | `frontend/src/app/review/[timelineId]/page.tsx` | 1h | ✅ |

### 验收标准

- [x] WATCHING 模式 Timeline 可添加 observations (API ready)
- [x] Review 页面支持截图功能 (快捷键 S)
- [x] Observation 列表显示在侧边栏
- [ ] 时间轴上显示观察点标记 (组件已创建，待集成到 TimelineEditor)
- [ ] 旧 SceneMind 数据可迁移

### API 变更

```
# 删除独立 SceneMind API
DELETE /scenemind/sessions
DELETE /scenemind/sessions/{id}/observations

# 合并到 Timeline API
POST   /timelines/{id}/observations           # 添加观察 (自动截图)
GET    /timelines/{id}/observations           # 获取观察列表
DELETE /timelines/{id}/observations/{obs_id}  # 删除观察
GET    /timelines/{id}/observations/{obs_id}/frame  # 获取截图
```

---

## Phase 1C: 透明字幕渲染

> **目标**: 支持 WATCHING 模式的透明悬浮字幕样式
> **预估工时**: 8.5h
> **优先级**: 🟡 中
> **状态**: ✅ 已完成

### 任务列表

| ID | 任务 | 文件 | 工时 | 状态 |
|----|------|------|------|------|
| 1C.1 | 字幕样式枚举 `SubtitleStyleMode` | `backend/app/models/timeline.py` | 0.5h | ✅ |
| 1C.2 | ExportWorker 支持透明字幕渲染 | `backend/app/workers/export.py` | 4h | ✅ |
| 1C.3 | FFmpeg ASS 样式模板 (透明背景) | `backend/app/workers/subtitle_styles.py` | 2h | ✅ |
| 1C.4 | 后端: subtitle-style-mode API | `backend/app/api/timelines.py` | 0.5h | ✅ |
| 1C.5 | 前端: types + API 函数 | `frontend/src/lib/types.ts, api.ts` | 1h | ✅ |
| 1C.6 | 前端: 字幕样式选择器 UI | `frontend/src/components/ExportDialog.tsx` | 2h | ⬜ |

### 验收标准

- [x] 导出时可选字幕样式: `half_screen` (学习) / `floating` (观影) / `none` (配音)
- [x] 透明字幕不遮挡画面 (floating 模式使用文字描边而非背景框)
- [x] API 支持设置和获取字幕样式模式
- [ ] 前端 UI 选择器 (可通过 API 调用，UI 待完成)

### 字幕样式对比

| 样式 | 位置 | 背景 | 适用模式 |
|------|------|------|----------|
| `half_screen` | 底部 1/3 | 半透明黑色 | Learning |
| `floating` | 底部居中 | 透明/轻微阴影 | Watching |
| `none` | - | - | Dubbing (可选) |

---

## Phase 1D: 记忆本 + Anki 导出

> **目标**: 用户收藏单词/实体，导出 Anki 卡片组
> **预估工时**: 19h
> **优先级**: 🟡 中
> **状态**: ✅ 已完成

### 任务列表

| ID | 任务 | 文件 | 工时 | 状态 |
|----|------|------|------|------|
| 1D.1 | MemoryBook 模型 | `backend/app/models/memory_book.py` | 1h | ✅ |
| 1D.2 | MemoryItem 模型 | `backend/app/models/memory_book.py` | 1h | ✅ |
| 1D.3 | MemoryBookManager 服务 | `backend/app/services/memory_book_manager.py` | 3h | ✅ |
| 1D.4 | 记忆本 API 端点 | `backend/app/api/memory_books.py` | 2h | ✅ |
| 1D.5 | Anki 导出 Worker (genanki) | `backend/app/workers/anki_export.py` | 4h | ✅ |
| 1D.6 | 前端: MemoryBookList | `frontend/src/components/MemoryBook/MemoryBookList.tsx` | 3h | ✅ |
| 1D.7 | 前端: MemoryItemCard | `frontend/src/components/MemoryBook/MemoryItemCard.tsx` | 2h | ✅ |
| 1D.8 | 前端: AnkiExportDialog | `frontend/src/components/MemoryBook/AnkiExportDialog.tsx` | 2h | ✅ |
| 1D.9 | 前端: 卡片弹窗添加 "收藏" 按钮 | `frontend/src/components/Cards/*.tsx` | 1h | ✅ |

### 验收标准

- [x] 点击单词/实体卡片可收藏到记忆本
- [x] 记忆本页面展示所有收藏
- [x] 可导出 `.apkg` 文件导入 Anki
- [x] Anki 卡片包含: 单词、发音、释义、例句、来源视频截图

### API 端点

```
GET    /memory-books                      # 获取记忆本列表
POST   /memory-books                      # 创建记忆本
GET    /memory-books/{id}                 # 获取记忆本详情
DELETE /memory-books/{id}                 # 删除记忆本

GET    /memory-books/{id}/items           # 获取记忆项列表
POST   /memory-books/{id}/items           # 添加记忆项
DELETE /memory-books/{id}/items/{item_id} # 删除记忆项

GET    /memory-books/{id}/export/anki     # 导出 Anki 卡片组 (.apkg)
```

### 数据模型

```python
# backend/app/models/memory_book.py

class MemoryBook(BaseModel):
    book_id: str
    name: str
    description: str = ""
    item_count: int = 0
    created_at: datetime
    updated_at: datetime

class MemoryItem(BaseModel):
    item_id: str
    book_id: str
    target_type: str                # "word" | "entity" | "observation"
    target_id: str                  # word string / entity QID / observation ID
    source_video_id: str            # Timeline ID
    source_timecode: float
    user_notes: str = ""
    tags: List[str] = []
    created_at: datetime
```

---

## Phase 2: 配音模式

> **目标**: 实现音色克隆 + 背景音保留 + 音轨混合
> **预估工时**: 44h
> **优先级**: 🟢 低
> **状态**: ✅ 已完成

### 2.1 音频分离 (Demucs)

| ID | 任务 | 文件 | 工时 | 状态 |
|----|------|------|------|------|
| 2.1.1 | Demucs 环境配置 | `requirements-dubbing.txt` | 1h | ✅ |
| 2.1.2 | AudioSeparationWorker | `backend/app/workers/audio_separation.py` | 4h | ✅ |
| 2.1.3 | 输出: vocals/bgm/sfx 分离 | `backend/app/workers/audio_separation.py` | 2h | ✅ |

### 2.2 音色克隆 (XTTS v2)

| ID | 任务 | 文件 | 工时 | 状态 |
|----|------|------|------|------|
| 2.2.1 | XTTS v2 环境配置 | `requirements-dubbing.txt` | 2h | ✅ |
| 2.2.2 | VoiceCloneWorker 基础 | `backend/app/workers/voice_clone.py` | 3h | ✅ |
| 2.2.3 | 说话人音色样本提取 | `backend/app/workers/voice_clone.py` | 2h | ✅ |
| 2.2.4 | 按说话人分别合成配音 | `backend/app/workers/voice_clone.py` | 4h | ✅ |
| 2.2.5 | 语速调整 (时长对齐) | `backend/app/workers/voice_clone.py` | 3h | ✅ |

### 2.3 音轨混合

| ID | 任务 | 文件 | 工时 | 状态 |
|----|------|------|------|------|
| 2.3.1 | AudioMixerWorker | `backend/app/workers/audio_mixer.py` | 3h | ✅ |
| 2.3.2 | 配音 + BGM + SFX 混合 | `backend/app/workers/audio_mixer.py` | 2h | ✅ |
| 2.3.3 | 音量平衡 + 淡入淡出 | `backend/app/workers/audio_mixer.py` | 2h | ✅ |

### 2.4 API 和前端

| ID | 任务 | 文件 | 工时 | 状态 |
|----|------|------|------|------|
| 2.4.1 | Dubbing API 端点 | `backend/app/api/dubbing.py` | 3h | ✅ |
| 2.4.2 | 前端: 配音模式页面 | `frontend/src/app/dub/[timelineId]/page.tsx` | 6h | ✅ |
| 2.4.3 | 前端: 音色配置面板 | `frontend/src/components/Dubbing/VoiceConfig.tsx` | 4h | ✅ |
| 2.4.4 | 前端: 配音预览播放器 | `frontend/src/components/Dubbing/DubbedPreview.tsx` | 3h | ✅ |

### 验收标准

- [x] 视频自动分离人声/背景音
- [x] 可克隆说话人音色进行配音
- [x] 配音与原视频时长对齐 (语速自动调整)
- [x] 导出完整配音视频 (配音 + BGM + SFX)

### API 端点

```
# 配音 API
GET    /timelines/{id}/dubbing/config       # 获取配音配置
PATCH  /timelines/{id}/dubbing/config       # 更新配音配置
GET    /timelines/{id}/dubbing/speakers     # 获取说话人列表 + 音色设置
PATCH  /timelines/{id}/dubbing/speakers/{speaker_id}  # 更新说话人音色设置

POST   /timelines/{id}/dubbing/separate     # 触发音频分离
POST   /timelines/{id}/dubbing/preview      # 预览单个片段配音
POST   /timelines/{id}/dubbing/generate     # 生成完整配音

GET    /timelines/{id}/dubbing/audio/{type} # 获取音频 (vocals/bgm/sfx/dubbed/mixed)
```

### Pipeline 流程

```
原视频
   │
   ▼
┌─────────────────┐
│ Audio Separation │  ← Demucs
│ (vocals/bgm/sfx) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Voice Clone    │  ← XTTS v2 / GPT-SoVITS
│  (per speaker)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Audio Mixing   │  ← FFmpeg
│ dubbed+bgm+sfx  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Video Export   │
│ (replace audio) │
└─────────────────┘
```

---

## Phase 3: 口型同步 (可选)

> **目标**: 使用 Wav2Lip 实现配音口型同步
> **预估工时**: 21h
> **优先级**: ⚪ 可选/实验性

### 任务列表

| ID | 任务 | 文件 | 工时 | 状态 |
|----|------|------|------|------|
| 3.1 | Wav2Lip 环境配置 | `requirements.txt` | 3h | ⬜ |
| 3.2 | 人脸检测 + 追踪 | `backend/app/workers/lip_sync.py` | 4h | ⬜ |
| 3.3 | LipSyncWorker (Wav2Lip) | `backend/app/workers/lip_sync.py` | 6h | ⬜ |
| 3.4 | 视频帧替换 + 合成 | `backend/app/workers/lip_sync.py` | 4h | ⬜ |
| 3.5 | 前端: 口型同步预览 | `frontend/src/components/Dubbing/LipSyncPreview.tsx` | 4h | ⬜ |

### 验收标准

- [ ] 配音视频口型与音频同步
- [ ] 无明显伪影/闪烁
- [ ] 支持多人场景

### 技术选型

| 方案 | 优点 | 缺点 | 推荐场景 |
|------|------|------|----------|
| Wav2Lip | 效果好，速度快 | 需要 GPU | 通用 |
| SadTalker | 支持头部运动 | 计算量大 | 单人特写 |
| DINet | 高清输出 | 资源消耗高 | 高质量要求 |

---

## 工时汇总

| Phase | 描述 | 工时 | 优先级 | 依赖 | 状态 |
|-------|------|------|--------|------|------|
| **0** | 统一基础设施 | 6.5h | 🔴 必须 | - | ✅ 完成 |
| **1B** | 卡片系统 | 40h | 🔴 高 | Phase 0 | ✅ 完成 |
| **1A** | 合并 SceneMind | 13h | 🟡 中 | Phase 0 | ✅ 完成 |
| **1C** | 透明字幕渲染 | 8.5h | 🟡 中 | Phase 0 | ✅ 完成 |
| **1D** | 记忆本 + Anki | 19h | 🟡 中 | Phase 1B | ✅ 完成 |
| **2** | 配音模式 | 44h | 🟢 低 | Phase 0 | ✅ 完成 |
| **3** | 口型同步 | 21h | ⚪ 可选 | Phase 2 | ⬜ 未开始 |
| | **总计** | **152h** | | | |

---

## 里程碑规划

| 里程碑 | 包含 Phase | 预计周期 | 交付物 | 状态 |
|--------|-----------|----------|--------|------|
| **M1** | Phase 0 | 1 周 | 统一数据模型，Job/Timeline 支持 mode | ✅ 完成 |
| **M2** | Phase 1B | 2 周 | 可点击字幕，单词/实体卡片弹窗 | ✅ 完成 |
| **M3** | Phase 1A + 1C | 1.5 周 | 观影模式完整，透明字幕导出 | ✅ 完成 |
| **M4** | Phase 1D | 1.5 周 | 记忆本功能，Anki 导出 | ✅ 完成 |
| **M5** | Phase 2 | 3 周 | 配音模式 MVP | ✅ 完成 |
| **M6** | Phase 3 | 2 周 | 口型同步 (实验性) | ⬜ 未开始 |

---

## 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 词典 API 配额/成本超支 | 中 | 高 | 本地缓存 + 批量查询 + 备选免费 API |
| XTTS v2 GPU 显存不足 | 低 | 中 | 16GB 显存足够; 各 Worker 串行执行 |
| Wav2Lip 效果不稳定 | 高 | 低 | 设为可选功能 / 提供预览 / 人工审核 |
| 实体识别准确率不足 | 中 | 低 | 人工纠错 UI / 用户反馈机制 |
| 音色克隆法律风险 | 低 | 高 | 相似度控制 / 水印 / 用户协议 |

### GPU 显存参考 (16GB)

| 模型/Worker | 显存占用 | 说明 |
|-------------|----------|------|
| Whisper large-v3 | ~4GB | 转录 |
| pyannote.audio | ~2GB | 说话人分离 |
| XTTS v2 | ~4-6GB | 音色克隆 |
| Wav2Lip | ~4GB | 口型同步 |
| Demucs | ~2GB | 音频分离 |

> 注: 各 Worker 串行执行，不会同时占用显存。16GB 显卡完全满足需求。

---

## 技术依赖

### Python 依赖 (新增)

```txt
# NER
spacy>=3.7.0
en_core_web_lg  # spacy model

# Cards
httpx>=0.25.0   # async HTTP client for APIs

# Dubbing
demucs>=4.0.0   # audio separation
TTS>=0.22.0     # XTTS v2

# Lip Sync (optional)
opencv-python>=4.8.0
mediapipe>=0.10.0

# Anki Export
genanki>=0.13.0
```

### 外部 API

| API | 用途 | 免费额度 | 备选 |
|-----|------|----------|------|
| Free Dictionary API | 单词查询 | 无限 | WordsAPI ($10/mo) |
| Wikidata API | 实体信息 | 无限 | DBpedia |
| OpenAI API | NER (可选) | 付费 | spaCy (本地) |

---

## 验收清单

### Phase 0 完成标准
- [x] `JobMode` 枚举定义
- [x] 三种模式配置类
- [x] Job API 支持 mode 参数
- [x] 前端模式选择器
- [x] 数据迁移脚本
- [x] 单元测试通过 (30 tests)

### Phase 1B 完成标准
- [x] NER Worker 可提取单词和实体
- [x] 卡片生成 Worker 可查询词典/Wikidata
- [x] 卡片缓存机制
- [x] 前端可点击字幕
- [x] 单词卡片弹窗 (发音/释义/例句)
- [x] 实体卡片弹窗 (摘要/图片/链接)
- [x] TypeScript 编译通过

### Phase 1A 完成标准
- [x] Timeline 模型添加 observations 字段
- [x] Timeline API 支持 observation CRUD
- [x] FrameCaptureWorker 截图功能
- [x] 前端 types + API 函数
- [x] Review 页面截图功能 (快捷键 S)
- [x] 时间轴观察点标记组件 (ObservationMarkers.tsx)
- [ ] ObservationMarkers 集成到 TimelineEditor (可选)
- [ ] 旧 SceneMind 数据迁移脚本 (可选)

### Phase 1C 完成标准
- [x] SubtitleStyleMode 枚举 (half_screen/floating/none)
- [x] ExportWorker 支持三种字幕渲染模式
- [x] subtitle_styles.py ASS 样式生成器
- [x] GET/POST /timelines/{id}/subtitle-style-mode API
- [x] 前端 types + API 函数
- [ ] 前端字幕样式选择器 UI (可选)

### Phase 1D 完成标准
- [x] 记忆本 CRUD API
- [x] 卡片收藏功能 (CollectButton)
- [x] 记忆本列表页面 (/memory-books)
- [x] Anki 导出功能 (AnkiExportWorker)
- [x] 导出的 .apkg 可正常导入 Anki

### Phase 2 完成标准
- [x] 音频分离 (vocals/bgm/sfx) - AudioSeparationWorker
- [x] 音色克隆功能 - VoiceCloneWorker (XTTS v2)
- [x] 语速自动对齐 - synthesize_segment()
- [x] 音轨混合 - AudioMixerWorker
- [x] 配音预览 - /timelines/{id}/dubbing/preview
- [x] 完整配音视频导出 - /timelines/{id}/dubbing/output

---

*最后更新: 2026-02-03 (Phase 0/1A/1B/1C/1D/2 已完成，仅剩 Phase 3 口型同步)*
