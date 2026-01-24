# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**MirrorFlow v2** - Automated video language conversion pipeline that transforms English video content (interviews, talks, podcasts) into Chinese dubbed videos. The system has evolved from a single-video processor into a multi-source content automation factory.

## v2 Architecture

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
└─────────────────────────────────────────────────────────────────────┘
```

## Core Concepts (v2)

```
Source Type (来源类型: youtube, rss, podcast, local, api)
   └── Source (具体来源: e.g., "yt_lex" = Lex Fridman's channel)
         └── Item (内容项: single video/article/episode)
               └── Pipeline (处理流水线: zh_main, ja_channel, shorts)
                     └── Target (发布目标: YouTube channel, local storage)
```

**Key Files:**
- `app/models/source.py` - SourceType enum, Source model
- `app/models/item.py` - Item, ItemStatus, PipelineStatus
- `app/models/pipeline.py` - PipelineConfig, TargetConfig
- `app/models/job.py` - Job (processing task)

**Service Layer:**
- `app/services/source_manager.py` - CRUD for sources (JSON persistence)
- `app/services/item_manager.py` - CRUD for items (directory-based storage)
- `app/services/pipeline_manager.py` - CRUD for pipelines
- `app/services/job_manager.py` - Job lifecycle with retry logic

## Data Storage Structure

```
data/
├── sources.json           # All sources
├── pipelines.json         # Pipeline configurations
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
    ├── tts/
    │   └── aligned.wav
    ├── content/
    │   └── metadata.json
    └── output/
        ├── final_video.mp4
        └── thumbnail.jpg
```

## Tech Stack

- **Python 3.10+** with FastAPI
- **yt-dlp** for video download
- **Whisper large-v3** for speech recognition (CUDA)
- **pyannote.audio** for speaker diarization
- **XTTS v2** for Chinese TTS
- **ffmpeg** with NVENC for GPU-accelerated encoding
- **n8n** for workflow orchestration
- **YouTube Data API v3** for upload

## Common Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run all tests
pytest

# Run specific test module
pytest tests/api/test_websocket.py -v

# Run tests with coverage
pytest --cov=app tests/
```

## API Quick Reference

```bash
# Create a source
curl -X POST http://localhost:8000/sources \
  -H "Content-Type: application/json" \
  -d '{"source_id":"yt_lex","source_type":"youtube","sub_type":"channel","display_name":"Lex Fridman","fetcher":"youtube_rss","config":{"channel_id":"xxx"}}'

# Create an item
curl -X POST http://localhost:8000/items \
  -H "Content-Type: application/json" \
  -d '{"source_type":"youtube","source_id":"yt_lex","original_url":"https://youtube.com/watch?v=xxx","original_title":"Title"}'

# Create a job (v1 compatible)
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{"url":"https://youtube.com/watch?v=xxx"}'

# Get overview
curl http://localhost:8000/overview

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
MIRRORFLOW_JOBS_DIR=./data/jobs
MIRRORFLOW_DATA_DIR=./data
OPENAI_API_KEY=sk-xxx
HF_TOKEN=hf_xxx

# Optional (for n8n integration)
MIRRORFLOW_API_URL=http://localhost:8000
FANOUT_WEBHOOK_URL=http://n8n:5678/webhook/fanout/trigger
NOTIFICATION_WEBHOOK=https://hooks.slack.com/xxx
```

## Content Guidelines

- Only process interview/talk/podcast content (no movies, music, or live streams)
- Use "similar style" voices, not precise voice cloning
- Generate distinct thumbnails and titles (not copies of original)
- Prioritize voice stability over similarity to original speaker

## Testing

Test structure mirrors the source code:
- `tests/models/` - Model unit tests
- `tests/services/` - Service layer tests
- `tests/api/` - API endpoint tests

All tests should pass: `pytest` (currently 128 tests)
