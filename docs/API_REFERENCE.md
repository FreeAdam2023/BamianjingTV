# MirrorFlow API Reference

> Version: 2.0.0
> Base URL: `http://localhost:8000`

## Overview

MirrorFlow v2 provides a RESTful API for managing video language conversion workflows. The API is organized around four core resources:

- **Sources** - Content sources (YouTube channels, RSS feeds, podcasts)
- **Items** - Individual content items (videos, articles, episodes)
- **Pipelines** - Processing configurations (language, target platform)
- **Jobs** - Processing tasks

## Authentication

Currently, the API does not require authentication. For production deployments, configure authentication via reverse proxy (nginx, Traefik) or implement API key authentication.

---

## Sources API

Sources represent content feeds that are periodically checked for new content.

### List Sources

```http
GET /sources
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `source_type` | string | Filter by type: `youtube`, `rss`, `podcast`, `scraper`, `local`, `api` |
| `enabled_only` | boolean | Only return enabled sources (default: false) |

**Response:**

```json
[
  {
    "source_id": "yt_lex",
    "source_type": "youtube",
    "sub_type": "channel",
    "display_name": "Lex Fridman",
    "fetcher": "youtube_rss",
    "config": {
      "channel_id": "UCSHZKyawb77ixDdsGog4iWA"
    },
    "enabled": true,
    "created_at": "2024-01-01T00:00:00",
    "last_fetched_at": "2024-01-15T12:00:00",
    "item_count": 42,
    "default_pipelines": ["zh_main", "ja_channel"]
  }
]
```

### Create Source

```http
POST /sources
```

**Request Body:**

```json
{
  "source_id": "yt_huberman",
  "source_type": "youtube",
  "sub_type": "channel",
  "display_name": "Andrew Huberman",
  "fetcher": "youtube_rss",
  "config": {
    "channel_id": "UC2D2CMWXMOVWx7giW1n3LIg"
  },
  "default_pipelines": ["zh_main"]
}
```

### Get Source

```http
GET /sources/{source_id}
```

### Update Source

```http
PUT /sources/{source_id}
```

### Delete Source

```http
DELETE /sources/{source_id}
```

### Trigger Fetch

Manually trigger a fetch for a source.

```http
POST /sources/{source_id}/fetch
```

**Response:**

```json
{
  "source_id": "yt_lex",
  "last_fetched_at": "2024-01-15T12:30:00"
}
```

### Get Source Items

```http
GET /sources/{source_id}/items
```

---

## Items API

Items represent individual pieces of content discovered from sources.

### List Items

```http
GET /items
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `source_type` | string | Filter by source type |
| `source_id` | string | Filter by source ID |
| `status` | string | Filter by status: `discovered`, `queued`, `processing`, `completed`, `partial`, `failed` |
| `limit` | integer | Max items to return (default: 100, max: 500) |
| `offset` | integer | Items to skip (default: 0) |

**Response:**

```json
[
  {
    "item_id": "item_abc123",
    "source_type": "youtube",
    "source_id": "yt_lex",
    "original_url": "https://youtube.com/watch?v=...",
    "original_title": "Interview with Sam Altman",
    "original_description": "...",
    "original_thumbnail": "https://...",
    "duration": 7200.0,
    "published_at": "2024-01-15T10:00:00",
    "status": "processing",
    "created_at": "2024-01-15T12:00:00",
    "updated_at": "2024-01-15T12:30:00",
    "pipelines": {
      "zh_main": {
        "status": "processing",
        "progress": 0.6,
        "job_id": "job_xyz789",
        "started_at": "2024-01-15T12:05:00"
      },
      "ja_channel": {
        "status": "pending"
      }
    }
  }
]
```

### Create Item

```http
POST /items
```

**Request Body:**

```json
{
  "source_type": "youtube",
  "source_id": "yt_lex",
  "original_url": "https://youtube.com/watch?v=...",
  "original_title": "Interview with Sam Altman",
  "original_description": "...",
  "duration": 7200.0,
  "published_at": "2024-01-15T10:00:00"
}
```

**Response:**

```json
{
  "item": { ... },
  "is_new": true
}
```

If an item with the same URL already exists for the source, `is_new` will be `false`.

### Get Item

```http
GET /items/{item_id}
```

### Delete Item

```http
DELETE /items/{item_id}
```

### Get Recent Items

```http
GET /items/recent?hours=24
```

### Trigger Pipelines

Trigger specified pipelines for an item.

```http
POST /items/{item_id}/trigger
```

**Request Body:**

```json
{
  "pipeline_ids": ["zh_main", "ja_channel"]
}
```

### Get Item Pipelines

```http
GET /items/{item_id}/pipelines
```

**Response:**

```json
{
  "item_id": "item_abc123",
  "status": "processing",
  "pipelines": {
    "zh_main": {
      "status": "completed",
      "progress": 1.0,
      "job_id": "job_xyz789",
      "completed_at": "2024-01-15T14:00:00"
    }
  }
}
```

### Get Fan-out Status

Get the distribution status for an item across all pipelines.

```http
GET /items/{item_id}/fanout
```

**Response:**

```json
{
  "item": {
    "item_id": "item_abc123",
    "original_title": "Interview with Sam Altman",
    "source_id": "yt_lex"
  },
  "pipelines": {
    "zh_main": {
      "status": "completed",
      "display_name": "Chinese Main Channel",
      "target": "YouTube ZH"
    },
    "ja_channel": {
      "status": "processing",
      "progress": 0.3,
      "display_name": "Japanese Channel",
      "target": "YouTube JA"
    }
  }
}
```

---

## Pipelines API

Pipelines define how content should be processed and where it should be published.

### List Pipelines

```http
GET /pipelines
```

**Response:**

```json
[
  {
    "pipeline_id": "zh_main",
    "pipeline_type": "full_dub",
    "display_name": "Chinese Main Channel",
    "target_language": "zh",
    "steps": ["download", "transcribe", "diarize", "translate", "tts", "mux"],
    "generate_thumbnail": true,
    "generate_content": true,
    "target": {
      "target_type": "youtube",
      "target_id": "UCxxxxxx",
      "display_name": "Chinese Tech Channel",
      "privacy_status": "public",
      "auto_publish": true
    },
    "enabled": true
  }
]
```

### Create Pipeline

```http
POST /pipelines
```

**Request Body:**

```json
{
  "pipeline_id": "shorts_zh",
  "pipeline_type": "shorts",
  "display_name": "Chinese Shorts",
  "target_language": "zh",
  "steps": ["download", "clip", "translate", "tts", "mux"],
  "target": {
    "target_type": "youtube",
    "target_id": "UCxxxxxx",
    "display_name": "Chinese Shorts Channel",
    "privacy_status": "public"
  }
}
```

### Get Pipeline

```http
GET /pipelines/{pipeline_id}
```

### Update Pipeline

```http
PUT /pipelines/{pipeline_id}
```

### Delete Pipeline

```http
DELETE /pipelines/{pipeline_id}
```

---

## Jobs API

Jobs represent individual processing tasks.

### List Jobs

```http
GET /jobs
```

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter by status |
| `limit` | integer | Max jobs to return (default: 100) |

### Create Job

```http
POST /jobs
```

**Request Body:**

```json
{
  "url": "https://youtube.com/watch?v=...",
  "target_language": "zh",
  "source_type": "youtube",
  "source_id": "yt_lex",
  "item_id": "item_abc123",
  "pipeline_id": "zh_main",
  "generate_thumbnail": true,
  "generate_content": true,
  "auto_upload": false,
  "upload_privacy": "private"
}
```

**Response:**

```json
{
  "id": "a1b2c3d4",
  "url": "https://youtube.com/watch?v=...",
  "target_language": "zh",
  "source_type": "youtube",
  "source_id": "yt_lex",
  "item_id": "item_abc123",
  "pipeline_id": "zh_main",
  "status": "pending",
  "progress": 0.0,
  "created_at": "2024-01-15T12:00:00",
  "updated_at": "2024-01-15T12:00:00"
}
```

### Get Job

```http
GET /jobs/{job_id}
```

### Delete Job

```http
DELETE /jobs/{job_id}?delete_files=true
```

### Retry Job

Retry a failed job.

```http
POST /jobs/{job_id}/retry
```

### Batch Create Jobs

```http
POST /jobs/batch
```

**Request Body:**

```json
{
  "urls": [
    "https://youtube.com/watch?v=abc",
    "https://youtube.com/watch?v=def"
  ],
  "target_language": "zh",
  "priority": 0,
  "callback_url": "https://your-webhook.com/callback"
}
```

---

## Overview API

Aggregated views for dashboards and monitoring.

### System Overview

```http
GET /overview
```

**Response:**

```json
{
  "total_sources": 10,
  "total_items": 150,
  "total_pipelines": 4,
  "active_jobs": 3,
  "by_source_type": {
    "youtube": {
      "source_count": 5,
      "item_count": 100,
      "new_items_24h": 8,
      "active_pipelines": 2
    },
    "podcast": {
      "source_count": 3,
      "item_count": 40,
      "new_items_24h": 2,
      "active_pipelines": 1
    }
  }
}
```

### Source Type Overview

```http
GET /overview/{source_type}
```

### Combined Statistics

```http
GET /overview/stats/combined
```

### Recent Activity

```http
GET /overview/activity/recent?hours=24
```

**Response:**

```json
{
  "hours": 24,
  "new_items": 15,
  "items_by_status": {
    "discovered": 5,
    "processing": 3,
    "completed": 7
  },
  "items": [
    {
      "item_id": "item_abc123",
      "source_id": "yt_lex",
      "title": "Interview with...",
      "status": "completed",
      "created_at": "2024-01-15T12:00:00"
    }
  ]
}
```

### Health Check

```http
GET /overview/health
```

**Response:**

```json
{
  "status": "healthy",
  "components": {
    "source_manager": true,
    "item_manager": true,
    "pipeline_manager": true,
    "job_manager": true
  }
}
```

---

## Queue API

Job queue management.

### Queue Statistics

```http
GET /queue/stats
```

**Response:**

```json
{
  "running": true,
  "max_concurrent": 2,
  "pending": 5,
  "active": 2,
  "active_jobs": ["a1b2c3d4", "e5f6g7h8"],
  "processed": 100,
  "failed": 3
}
```

### Pause Queue

```http
POST /queue/pause
```

### Resume Queue

```http
POST /queue/resume
```

---

## WebSocket API

Real-time status updates via WebSocket.

### Main WebSocket Endpoint

```
ws://localhost:8000/ws
```

**Subscription Commands:**

```json
// Subscribe to all updates
{"action": "subscribe", "topic": "all"}

// Subscribe to job updates
{"action": "subscribe", "topic": "jobs"}

// Subscribe to item updates
{"action": "subscribe", "topic": "items"}

// Subscribe to specific job
{"action": "subscribe", "job_id": "a1b2c3d4"}

// Subscribe to specific source
{"action": "subscribe", "source_id": "yt_lex"}

// Unsubscribe
{"action": "unsubscribe", "topic": "jobs"}

// Ping (keep-alive)
{"action": "ping"}
```

**Update Messages:**

```json
// Job update
{
  "type": "job_update",
  "job_id": "a1b2c3d4",
  "timestamp": "2024-01-15T12:30:00Z",
  "data": {
    "status": "transcribing",
    "progress": 0.25,
    "title": "Interview with Sam Altman"
  }
}

// Item update
{
  "type": "item_update",
  "item_id": "item_abc123",
  "source_id": "yt_lex",
  "timestamp": "2024-01-15T12:30:00Z",
  "data": {
    "status": "processing"
  }
}

// Overview update
{
  "type": "overview_update",
  "timestamp": "2024-01-15T12:30:00Z",
  "data": {
    "total_sources": 10,
    "active_jobs": 3
  }
}
```

### Job-Specific WebSocket

```
ws://localhost:8000/ws/jobs/{job_id}
```

Automatically subscribes to updates for the specified job.

### Source-Specific WebSocket

```
ws://localhost:8000/ws/sources/{source_id}
```

Automatically subscribes to updates for the specified source and its items.

### WebSocket Statistics

```http
GET /ws/stats
```

**Response:**

```json
{
  "total_connections": 5,
  "job_subscriptions": 3,
  "source_subscriptions": 2,
  "topic_subscriptions": {
    "jobs": 2,
    "items": 1,
    "sources": 0,
    "overview": 1,
    "all": 1
  }
}
```

---

## Webhook Callbacks

Register webhooks to receive job status updates.

### Register Webhook

```http
POST /webhooks/register
```

**Request Body:**

```json
{
  "job_id": "a1b2c3d4",
  "callback_url": "https://your-server.com/webhook"
}
```

### Unregister Webhook

```http
DELETE /webhooks/{job_id}
```

### Webhook Payload

When a job status changes, MirrorFlow sends a POST request to your callback URL:

```json
{
  "job_id": "a1b2c3d4",
  "status": "completed",
  "progress": 1.0,
  "url": "https://youtube.com/watch?v=...",
  "title": "Interview with Sam Altman",
  "output_video": "/data/jobs/a1b2c3d4/output/final_video.mp4",
  "youtube_url": "https://youtube.com/watch?v=newvideo",
  "updated_at": "2024-01-15T14:00:00"
}
```

---

## Error Responses

All endpoints return errors in a consistent format:

```json
{
  "detail": "Source 'yt_invalid' not found"
}
```

### HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request - Invalid parameters |
| 404 | Not Found - Resource doesn't exist |
| 422 | Validation Error - Invalid request body |
| 500 | Internal Server Error |

---

## Rate Limits

No rate limits are enforced by default. For production deployments, consider implementing rate limiting at the reverse proxy level.

---

## Pagination

List endpoints support pagination via `limit` and `offset` parameters:

```http
GET /items?limit=50&offset=100
```

---

## Job Statuses

| Status | Description |
|--------|-------------|
| `pending` | Job created, waiting to be processed |
| `downloading` | Downloading source video |
| `transcribing` | Running speech-to-text |
| `diarizing` | Separating speakers |
| `translating` | Translating transcript |
| `synthesizing` | Generating TTS audio |
| `muxing` | Combining video and audio |
| `generating_content` | Creating titles/descriptions |
| `generating_thumbnail` | Creating thumbnail |
| `uploading` | Uploading to YouTube |
| `completed` | Successfully finished |
| `failed` | Failed with error |

---

## Environment Variables

Configure the API via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `MIRRORFLOW_JOBS_DIR` | `./data/jobs` | Job data storage |
| `MIRRORFLOW_DATA_DIR` | `./data` | Sources/pipelines storage |
| `MIRRORFLOW_API_URL` | `http://localhost:8000` | API base URL for n8n |
| `FANOUT_WEBHOOK_URL` | - | n8n fan-out webhook URL |
| `NOTIFICATION_WEBHOOK` | - | Slack/Discord webhook URL |

---

## OpenAPI Documentation

Interactive API documentation is available at:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`
