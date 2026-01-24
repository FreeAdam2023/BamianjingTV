# MirrorFlow v2 Migration Guide

This guide helps you migrate from MirrorFlow v1 to v2.

## Overview

MirrorFlow v2 introduces a new source-centric architecture while maintaining backward compatibility with v1 APIs.

### What's Changed

| Aspect | v1 | v2 |
|--------|----|----|
| Data Model | Job-centric | Source → Item → Pipeline |
| Content Discovery | Manual URL input | Automatic fetching |
| Distribution | Single pipeline | Fan-out to multiple targets |
| Real-time Updates | Webhook polling | WebSocket push |
| n8n Workflows | Single pipeline | Layered (Fetcher/Fan-out/Notify) |

### What's Backward Compatible

- `POST /jobs` still works with just a URL
- Existing job files are automatically migrated on load
- All v1 API endpoints remain functional

## Migration Steps

### 1. Update the Codebase

```bash
git pull origin main
pip install -r requirements.txt
```

### 2. Create Data Directories

v2 uses a new data directory structure:

```bash
mkdir -p data/items
```

The system will auto-create `data/sources.json` and `data/pipelines.json` on first run.

### 3. Existing Jobs

Existing jobs are automatically migrated when loaded. The system adds:

- `source_type`: Inferred from URL (youtube, rss, etc.)
- `source_id`: Set to "legacy"
- `item_id`: Generated as `item_{job_id}`
- `pipeline_id`: Set to "default_zh"

No manual migration is required for existing jobs.

### 4. Update n8n Workflows

Old workflows have been archived to `n8n/workflows/_archive_v1/`. Import the new workflows:

1. **Fetchers** (choose based on your sources):
   - `fetchers/youtube_channel.json` - YouTube channel monitoring
   - `fetchers/rss.json` - RSS feed monitoring
   - `fetchers/podcast.json` - Podcast feed monitoring

2. **Fan-out** (required):
   - `fanout/trigger_pipelines.json` - Triggers pipelines for new items

3. **Notifications** (optional):
   - `notify/completion.json` - Success notifications
   - `notify/failure.json` - Failure alerts
   - `notify/daily_report.json` - Daily statistics

### 5. Configure Environment Variables

Add new environment variables for n8n integration:

```bash
# .env file
MIRRORFLOW_API_URL=http://localhost:8000
FANOUT_WEBHOOK_URL=http://n8n:5678/webhook/fanout/trigger
NOTIFICATION_WEBHOOK=https://hooks.slack.com/your-webhook
```

### 6. Create Sources (Optional)

To use automatic content discovery, create sources:

```bash
# Create a YouTube channel source
curl -X POST http://localhost:8000/sources \
  -H "Content-Type: application/json" \
  -d '{
    "source_id": "yt_lex",
    "source_type": "youtube",
    "sub_type": "channel",
    "display_name": "Lex Fridman",
    "fetcher": "youtube_rss",
    "config": {
      "channel_id": "UCSHZKyawb77ixDdsGog4iWA"
    },
    "default_pipelines": ["default_zh"]
  }'
```

### 7. Create Custom Pipelines (Optional)

The default pipeline `default_zh` is created automatically. Create custom pipelines for multi-target distribution:

```bash
# Create a Japanese pipeline
curl -X POST http://localhost:8000/pipelines \
  -H "Content-Type: application/json" \
  -d '{
    "pipeline_id": "ja_main",
    "pipeline_type": "full_dub",
    "display_name": "Japanese Main",
    "target_language": "ja",
    "target": {
      "target_type": "youtube",
      "target_id": "UC_your_ja_channel",
      "display_name": "Japanese Channel"
    }
  }'
```

## API Changes

### New Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/sources` | GET/POST/PUT/DELETE | Manage content sources |
| `/items` | GET/POST/DELETE | Manage content items |
| `/items/{id}/fanout` | GET | View fan-out status |
| `/pipelines` | GET/POST/PUT/DELETE | Configure pipelines |
| `/overview` | GET | Dashboard statistics |
| `/overview/health` | GET | System health check |
| `/ws` | WebSocket | Real-time updates |

### Modified Endpoints

#### POST /jobs

The `/jobs` endpoint now accepts optional v2 fields:

```json
{
  "url": "https://youtube.com/watch?v=xxx",
  "target_language": "zh",
  "source_type": "youtube",      // NEW: optional
  "source_id": "yt_lex",         // NEW: optional
  "item_id": "item_abc123",      // NEW: optional
  "pipeline_id": "default_zh"    // NEW: optional
}
```

If v2 fields are omitted, they are auto-populated for backward compatibility.

## WebSocket Integration

Replace webhook polling with WebSocket for real-time updates:

```javascript
// Connect to WebSocket
const ws = new WebSocket('ws://localhost:8000/ws');

// Subscribe to job updates
ws.send(JSON.stringify({
  action: 'subscribe',
  topic: 'jobs'
}));

// Or subscribe to a specific job
ws.send(JSON.stringify({
  action: 'subscribe',
  job_id: 'abc12345'
}));

// Handle updates
ws.onmessage = (event) => {
  const update = JSON.parse(event.data);
  console.log('Job update:', update);
};
```

## Data Model Reference

### Source

```json
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
  "default_pipelines": ["default_zh", "ja_main"]
}
```

### Item

```json
{
  "item_id": "item_abc123",
  "source_type": "youtube",
  "source_id": "yt_lex",
  "original_url": "https://youtube.com/watch?v=xxx",
  "original_title": "Interview Title",
  "status": "processing",
  "pipelines": {
    "default_zh": {
      "status": "completed",
      "job_id": "job123"
    },
    "ja_main": {
      "status": "processing",
      "progress": 0.5
    }
  }
}
```

### Pipeline

```json
{
  "pipeline_id": "default_zh",
  "pipeline_type": "full_dub",
  "display_name": "Default Chinese",
  "target_language": "zh",
  "steps": ["download", "transcribe", "diarize", "translate", "tts", "mux"],
  "generate_thumbnail": true,
  "generate_content": true,
  "target": {
    "target_type": "local",
    "target_id": "output",
    "display_name": "Local Output"
  }
}
```

## Troubleshooting

### Jobs Not Tracking Source

If jobs created via v1 API don't show source tracking:

1. Jobs created before migration will have `source_id: "legacy"`
2. This is expected behavior - they are still fully functional
3. New jobs will have proper source tracking if created via n8n fetchers

### n8n Workflows Not Working

1. Verify environment variables are set in n8n
2. Check that MirrorFlow API is accessible from n8n container
3. Verify webhook URLs are correct

### WebSocket Connection Fails

1. Ensure the API server is running
2. Check firewall rules for WebSocket connections
3. Verify the client is using `ws://` (not `wss://` unless SSL is configured)

## Rollback

If you need to rollback to v1:

1. The v1 API endpoints still work
2. Old n8n workflows are archived in `n8n/workflows/_archive_v1/`
3. Existing job data is unchanged

Note: v2-specific data (sources, items, pipelines) will remain but won't be used by v1 workflows.

## Support

- [API Reference](API_REFERENCE.md)
- [Deployment Guide](DEPLOYMENT.md)
- [n8n Workflows](../n8n/workflows/README.md)
