# Hardcore Player n8n Workflows

This directory contains pre-configured n8n workflows for Hardcore Player automation.

## Available Workflows

### 1. hardcore-player_pipeline.json
Basic video processing pipeline with webhook trigger.

**Webhook URL:** `POST /webhook/process-video`

**Request Body:**
```json
{
  "url": "https://youtube.com/watch?v=xxx",
  "target_language": "zh"
}
```

### 2. hardcore-player_batch.json
Batch processing workflow for multiple videos.

**Webhook URL:** `POST /webhook/batch-process`

**Request Body:**
```json
{
  "urls": [
    "https://youtube.com/watch?v=xxx",
    "https://youtube.com/watch?v=yyy"
  ],
  "target_language": "zh",
  "priority": 0
}
```

### 3. hardcore-player_monitor.json
Scheduled monitoring workflow that runs every 5 minutes.

- Checks system stats
- Alerts on failed jobs
- Logs queue status

## Setup Instructions

### Import Workflows

1. Open n8n at http://localhost:5678
2. Go to **Workflows** → **Import from File**
3. Import each JSON file

### Configure Credentials

No additional credentials needed - workflows use internal Docker network.

### Activate Workflows

1. Open each imported workflow
2. Click **Active** toggle in top-right
3. Save workflow

## API Reference

### Endpoints used by workflows:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/jobs` | POST | Create single job |
| `/jobs/batch` | POST | Create batch jobs |
| `/jobs/{id}` | GET | Get job status |
| `/stats` | GET | Get system stats |
| `/jobs?status=failed` | GET | List failed jobs |

### Webhook Callbacks

Hardcore Player sends callbacks to registered URLs:

```json
{
  "event": "job_completed",
  "timestamp": "2024-01-15T10:30:00Z",
  "job": {
    "id": "abc123",
    "status": "completed",
    "output_video": "/app/jobs/abc123/output/final_video.mp4"
  }
}
```

Event types: `status_update`, `job_completed`, `job_failed`

## Example: Process Video via n8n

```bash
# Trigger the pipeline workflow
curl -X POST http://localhost:5678/webhook/process-video \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'
```
