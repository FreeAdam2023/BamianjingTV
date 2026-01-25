# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Hardcore Player** - Learning video factory that transforms English video content into bilingual learning materials with preserved original audio and dual-language subtitles (English + Chinese).

## Architecture

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
│                    Hardcore Player API (FastAPI)                     │
├─────────────────────────────────────────────────────────────────────┤
│  /sources    - Content source management                            │
│  /items      - Content item tracking                                │
│  /pipelines  - Processing configuration                             │
│  /jobs       - Processing task execution                            │
│  /timelines  - Review UI segment management                         │
│  /overview   - Dashboard aggregations                               │
│  /ws         - WebSocket real-time updates                          │
└─────────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────────┐
│                       Processing Workers (GPU)                       │
├─────────────────────────────────────────────────────────────────────┤
│  Download → Whisper → Diarization → Translation → [UI Review] → Export
└─────────────────────────────────────────────────────────────────────┘
```

## Pipeline Flow

```
1. Download     - Download video/audio from URL (yt-dlp)
2. Transcribe   - Speech-to-text with Whisper large-v3
3. Diarize      - Speaker identification with pyannote.audio
4. Translate    - English to Chinese translation (GPT-4o)
5. [PAUSE]      - Job enters AWAITING_REVIEW status
6. UI Review    - User reviews segments (keep/drop) in Next.js frontend
7. Export       - Burn bilingual subtitles, optional YouTube upload
```

## Core Concepts

```
Source Type (来源类型: youtube, rss, podcast, local, api)
   └── Source (具体来源: e.g., "yt_lex" = Lex Fridman's channel)
         └── Item (内容项: single video/article/episode)
               └── Pipeline (处理流水线配置)
                     └── Job → Timeline (审阅 → 导出)
```

**Key Files:**
- `app/models/source.py` - SourceType enum, Source model
- `app/models/item.py` - Item, ItemStatus, PipelineStatus
- `app/models/pipeline.py` - PipelineConfig, TargetConfig
- `app/models/job.py` - Job (processing task)
- `app/models/timeline.py` - Timeline, EditableSegment, SegmentState

**Service Layer:**
- `app/services/source_manager.py` - CRUD for sources (JSON persistence)
- `app/services/item_manager.py` - CRUD for items (directory-based storage)
- `app/services/pipeline_manager.py` - CRUD for pipelines
- `app/services/job_manager.py` - Job lifecycle with retry logic
- `app/services/timeline_manager.py` - Timeline CRUD for review UI

**Workers:**
- `app/workers/download.py` - Video download (yt-dlp)
- `app/workers/whisper.py` - Speech recognition (faster-whisper)
- `app/workers/diarization.py` - Speaker diarization (pyannote.audio)
- `app/workers/translation.py` - Translation (OpenAI GPT)
- `app/workers/export.py` - Subtitle burn-in and video export (ffmpeg)
- `app/workers/youtube.py` - YouTube upload (optional)

## Data Storage Structure

```
data/
├── sources.json           # All sources
├── pipelines.json         # Pipeline configurations
├── timelines/             # Timeline JSON files for review
│   └── {timeline_id}.json
└── items/                 # Item data by source
    └── {source_type}/
        └── {source_id}/
            └── {item_id}.json

jobs/
└── {job_id}/
    ├── meta.json          # Job metadata
    ├── source/
    │   ├── video.mp4
    │   └── audio.wav
    ├── transcript/
    │   ├── raw.json
    │   └── diarized.json
    ├── translation/
    │   └── zh.json
    └── output/
        ├── full.mp4       # Full video with subtitles
        └── essence.mp4    # KEEP segments only
```

## Tech Stack

- **Python 3.10+** with FastAPI
- **yt-dlp** for video download
- **Whisper large-v3** for speech recognition (CUDA)
- **pyannote.audio** for speaker diarization
- **OpenAI GPT-4o** for translation
- **ffmpeg** with NVENC for GPU-accelerated encoding
- **Next.js 14** for review UI frontend
- **n8n** for workflow orchestration
- **YouTube Data API v3** for upload (optional)

## Common Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run frontend
cd frontend && npm run dev

# Run all tests
pytest

# Run specific test module
pytest tests/api/test_timelines.py -v

# Run tests with coverage
pytest --cov=app tests/
```

## API Quick Reference

```bash
# Create a job
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{"url":"https://youtube.com/watch?v=xxx"}'

# List timelines (awaiting review)
curl http://localhost:8000/timelines?unreviewed_only=true

# Get timeline with segments
curl http://localhost:8000/timelines/{timeline_id}

# Update segment state
curl -X PATCH http://localhost:8000/timelines/{timeline_id}/segments/{segment_id} \
  -H "Content-Type: application/json" \
  -d '{"state":"keep"}'

# Trigger export with YouTube upload
curl -X POST http://localhost:8000/timelines/{timeline_id}/export \
  -H "Content-Type: application/json" \
  -d '{"profile":"full","upload_to_youtube":true,"youtube_privacy":"private"}'

# Get stats
curl http://localhost:8000/stats

# WebSocket connection
wscat -c ws://localhost:8000/ws
```

## n8n Workflows

Located in `n8n/workflows/`:

| Workflow | Purpose | Trigger |
|----------|---------|---------|
| `fetchers/youtube_channel.json` | Detect new YouTube videos | Cron 15min |
| `fetchers/rss.json` | Detect new RSS items | Cron 30min |
| `fetchers/podcast.json` | Detect new podcast episodes | Cron 1h |
| `fanout/trigger_pipelines.json` | Fan-out item to pipelines | Webhook |
| `notify/completion.json` | Job completion notification | Webhook |
| `notify/failure.json` | Job failure alert | Webhook |
| `notify/daily_report.json` | Daily statistics | Cron 9AM |

## Environment Variables

```bash
# Required
JOBS_DIR=./jobs
DATA_DIR=./data
OPENAI_API_KEY=sk-xxx
HF_TOKEN=hf_xxx

# Optional (for YouTube upload)
YOUTUBE_CREDENTIALS_FILE=credentials/youtube_oauth.json
YOUTUBE_TOKEN_FILE=credentials/youtube_token.json

# Optional (for n8n integration)
API_URL=http://localhost:8000
FANOUT_WEBHOOK_URL=http://n8n:5678/webhook/fanout/trigger
NOTIFICATION_WEBHOOK=https://hooks.slack.com/xxx
```

## Testing

Test structure mirrors the source code:
- `tests/models/` - Model unit tests
- `tests/services/` - Service layer tests
- `tests/api/` - API endpoint tests

All tests should pass: `pytest` (currently 175 tests)
